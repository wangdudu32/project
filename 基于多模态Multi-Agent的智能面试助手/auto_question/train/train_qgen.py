import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import wandb
from trl import SFTConfig, SFTTrainer
from functools import partial
from peft import LoraConfig, get_peft_model
from datasets import load_dataset
from utils.utils import find_files, collate_func, clear_memory
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

# Configuration
MODEL_PATH = "/home/fx/cql/auto_question/models/qwen2.5vl"
DATA_PATH = "data/sft_generated_qgen.parquet" 
OUTPUT_PATH = "results/qgen-sft"

def format_data_qgen(sample):
    system_message = """You are an expert interviewer for Large Language Model (LLM) engineer positions.
    Your task is to analyze the provided educational material (image and text) and generate a high-quality open-ended interview question in JSON format.
    
    Requirements:
    1. The answer must be written from the candidate's perspective (first-person "I").
    2. The language must be ENGLISH.
    3. For specific technical terms (e.g., GRPO, PPO, RLHF), provide the abbreviation.
    """
    
    user_content = []
    if "image" in sample and sample["image"]:
        img = sample["image"]
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img = img.resize((448, 448))
        user_content.append({"type": "image", "image": img})
    
    text_content = sample.get("text") or sample.get("query") or ""
    user_content.append({"type": "text", "text": f"Content: {text_content}\nGenerate a question based on this."})
        
    target_text = sample.get("label") or sample.get("answer") or ""
    if isinstance(target_text, list):
        target_text = target_text[0]
        
    return [
        {
            "role": "system",
            "content": [{"type": "text", "text": system_message}],
        },
        {
            "role": "user",
            "content": user_content,
        },
        {
            "role": "assistant",
            "content": [{"type": "text", "text": target_text}], 
        },
    ]

def main():
    try:
        if DATA_PATH.endswith(".parquet"):
             dataset = load_dataset("parquet", data_files=DATA_PATH, split='train')
        else:
            directories = ['data'] 
            data_files = find_files(directories, DATA_PATH)
            if not data_files:
                print(f"No data files found in {DATA_PATH}. Please check your data path.")
                return
            dataset = load_dataset("parquet", data_files=data_files, split='train')
        
        train_val_dataset, test_dataset = dataset.train_test_split(test_size=0.1, seed=42).values()
        train_dataset, eval_dataset = train_val_dataset.train_test_split(test_size=0.1, seed=42).values()
        
        # Format
        train_dataset = [m for s in train_dataset if (m:=format_data_qgen(s)) and m[2]["content"][0]["text"].strip()]
        eval_dataset = [m for s in eval_dataset if (m:=format_data_qgen(s)) and m[2]["content"][0]["text"].strip()]
        
        clear_memory()
        
        print(f"Loading model from {MODEL_PATH}...")
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.bfloat16,
        )
        processor = AutoProcessor.from_pretrained(
            MODEL_PATH,
            use_fast=False,
            min_pixels=256*28*28,
            max_pixels=1280*28*28
        )
        collate_fn = partial(collate_func, processor=processor)
        
        # LoRA Config
        peft_config = LoraConfig(
            lora_alpha=16,
            lora_dropout=0.05,
            r=4,
            bias="none",
            target_modules=["q_proj", "v_proj"],
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()
        
        # Training Args
        training_args = SFTConfig(
            output_dir=OUTPUT_PATH,
            num_train_epochs=3,
            per_device_train_batch_size=1,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=4,
            gradient_checkpointing=True,
            gradient_checkpointing_kwargs={"use_reentrant": False},
            optim="adamw_torch_fused",
            learning_rate=2e-4,
            lr_scheduler_type="constant",
            logging_steps=10,
            eval_steps=100,
            eval_strategy="steps",
            save_strategy="steps",
            save_steps=100,
            bf16=True,
            dataset_text_field="", 
            dataset_kwargs={"skip_prepare_dataset": True},
            max_seq_length=1024,
            remove_unused_columns=False
        )
        
        wandb.init(project="mini-qwen-qgen", name="qgen-run-1")
        
        trainer = SFTTrainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=collate_fn,
            peft_config=peft_config,
            tokenizer=processor.tokenizer,
        )
        
        print("Starting training...")
        trainer.train()
        trainer.save_model()
        print(f"Model saved to {OUTPUT_PATH}")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
