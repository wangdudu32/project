import os
import json
import asyncio
from datasets import load_dataset
from openai import OpenAI
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
import torch
from PIL import Image
import pandas as pd
from tqdm import tqdm

# Configuration
DATA_DIR = "data/sft"
OUTPUT_FILE = "data/sft_generated_qgen.jsonl"
MODEL_PATH = "/home/fx/cql/auto_question/models/qwen2.5vl"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Initialize Qwen Model
print(f"Loading Qwen2.5-VL from {MODEL_PATH}...")
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    MODEL_PATH,
    torch_dtype=torch.float16,
    device_map="cuda",
)
processor = AutoProcessor.from_pretrained(MODEL_PATH)

# Initialize OpenRouter Client
if not OPENROUTER_API_KEY:
    print("Warning: OPENROUTER_API_KEY not found. Verification step will be skipped.")
    client = None
else:
    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )

def generate_question_qwen(image, instruction):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": instruction},
            ],
        }
    ]
    
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    
    inputs = processor(
        text=[text],
        images=image_inputs,
        padding=True,
        return_tensors="pt",
    ).to(model.device)
    
    generated_ids = model.generate(**inputs, max_new_tokens=1024)
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    return output_text[0]

def verify_with_claude(question, answer):
    prompt = f"""
    You are a Principal Engineer and Bar Raiser for LLM hiring.
    Review the following interview question and answer generated from a chart image.
    
    Question: {question}
    Answer: {answer}
    
    Checklist:
    1. Is the question suitable for a Senior Algorithm Engineer? (Technical depth)
    2. Is the answer accurate and comprehensive?
    3. Is the answer in first-person perspective ("I")?
    4. Is it in English?
    
    If it meets all criteria, return exactly: PASS
    If not, rewrite the Question and Answer to meet the criteria.
    
    Return format (JSON only):
    {{
        "status": "PASS" or "REVISED",
        "question": "Final Question text",
        "answer": "Final Answer text"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="anthropic/claude-3.5-sonnet", # Or similar high-quality model
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content.strip()
        # Clean JSON
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content)
    except Exception as e:
        print(f"Claude Verification Failed: {e}")
        return {"status": "FAIL", "question": question, "answer": answer}

def main():
    # Load ChartQA Dataset
    # Since we downloaded it locally to 'data/sft', we load from there
    # The structure might be parquet or arrow. Let's try loading.
    try:
        dataset = load_dataset("parquet", data_files={'train': f"{DATA_DIR}/data/train-*.parquet"})
    except:
        # Fallback if structure is different (Modelscope download format)
        # It seems modelscope downloads as 'data/train-...'
        print("Trying fallback loading...")
        import glob
        files = glob.glob(f"{DATA_DIR}/**/*.parquet", recursive=True)
        dataset = load_dataset("parquet", data_files={'train': files})

    print(f"Loaded {len(dataset['train'])} samples. Generating SFT data...")
    
    generated_data = []
    
    # Process a subset for demonstration/time (e.g., 50 samples)
    # User can increase this
    subset = dataset['train'].select(range(min(20, len(dataset['train'])))) 
    
    for item in tqdm(subset):
        image = item['image'] # PIL Image
        
        # 1. Generate Draft with Qwen
        prompt = """
        You are an expert interviewer for Large Language Model (LLM) engineer positions.
        Analyze this chart.
        Generate 1 high-quality, open-ended interview question that tests the candidate's understanding of the key technical concepts presented here.
        The question should be suitable for a Senior Algorithm Engineer interview.
        
        Requirements:
        1. The answer must be written from the candidate's perspective (first-person "I").
        2. The language must be ENGLISH.
        3. For specific technical terms (e.g., GRPO, PPO, RLHF), provide the abbreviation.
        4. Return ONLY valid JSON with no markdown formatting.
        
        Format:
        {
            "question": "The interview question text",
            "answer": "Comprehensive answer from first-person perspective",
            "analysis": "Why this question is important and what it tests",
            "difficulty": "hard",
            "type": "open_ended"
        }
        """
        
        try:
            draft_resp = generate_question_qwen(image, prompt)
            
            # Clean JSON
            draft_resp = draft_resp.strip()
            if draft_resp.startswith("```json"):
                draft_resp = draft_resp[7:]
            if draft_resp.endswith("```"):
                draft_resp = draft_resp[:-3]
            
            draft_json = json.loads(draft_resp)
            
            q_draft = draft_json.get('question')
            a_draft = draft_json.get('answer')
            
            if not q_draft or not a_draft:
                continue
                
            # 2. Verify/Refine with Claude
            if OPENROUTER_API_KEY:
                verified_json = verify_with_claude(q_draft, a_draft)
                final_q = verified_json.get('question', q_draft)
                final_a = verified_json.get('answer', a_draft)
            else:
                final_q = q_draft
                final_a = a_draft
            
            # 3. Format for SFT
            # We want to train the model to generate the JSON structure given the prompt
            # Input: Image + Prompt
            # Output: JSON with Question, Answer, Analysis etc.
            
            # Actually, usually for QGen task, we want:
            # User: <Image> Generate a question...
            # Assistant: JSON...
            
            # Or maybe the user wants the model to be an Interviewer?
            # "The question should be suitable for a Senior Algorithm Engineer interview."
            # So the model output IS the JSON.
            
            # Let's save the refined JSON as the target output
            draft_json['question'] = final_q
            draft_json['answer'] = final_a
            
            generated_data.append({
                "image": image, # We might need to save image path or bytes? 
                # For simplicity in this script, let's just save the text data and we might need to handle images for training separately.
                # But `train_qgen.py` expects "image" column.
                # We can save to a new HF dataset or Parquet.
                "text": prompt, # The instruction
                "label": json.dumps(draft_json, ensure_ascii=False) # The target JSON
            })
            
        except Exception as e:
            print(f"Error processing item: {e}")
            continue

    # Save to Parquet
    print(f"Saving {len(generated_data)} samples to {OUTPUT_FILE}...")
    
    # Convert list of dicts to HF Dataset
    # Handle images: define features
    from datasets import Dataset, Features, Image as ImageFeature, Value
    
    features = Features({
        "image": ImageFeature(),
        "text": Value("string"),
        "label": Value("string")
    })
    
    # Create dataset
    # We need to make sure 'image' is PIL object
    ds = Dataset.from_list(generated_data, features=features)
    ds.to_parquet(OUTPUT_FILE.replace('.jsonl', '.parquet'))
    print("Done!")

if __name__ == "__main__":
    main()
