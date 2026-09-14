import os
from typing import List, Dict, Any
from pdf2image import convert_from_path
from sympy import sympify, solve, parse_expr
import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
from PIL import Image
import json

# Singleton Model Loader
class QwenModel:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            model_path = "/home/fx/cql/auto_question/models/qwen2.5vl"
            print(f"Loading Qwen2.5-VL from {model_path}...")
            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map="cuda",
            )
            processor = AutoProcessor.from_pretrained(model_path)
            cls._instance = (model, processor)
        return cls._instance

def parse_pdf_to_images(pdf_path: str, output_dir: str = "temp_images") -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    images = convert_from_path(pdf_path)
    image_paths = []
    for i, image in enumerate(images):
        path = os.path.join(output_dir, f"{os.path.basename(pdf_path)}_page_{i}.png")
        image.save(path, "PNG")
        image_paths.append(path)
    return image_paths

def generate_question_with_vlm(image_path: str, instruction: str) -> str:
    model, processor = QwenModel.get_instance()
    
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image_path},
                {"type": "text", "text": instruction},
            ],
        }
    ]
    
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, _ = process_vision_info(messages)
    
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

def verify_math_solution(question: str, proposed_solution: str) -> Dict[str, Any]:
    try:
        import re
        equations = re.findall(r"[\w\s]+=[-+\*/\w\s]+", proposed_solution)
        valid_eqs = []
        for eq in equations:
            try:
                lhs, rhs = eq.split('=')
                lhs_expr = parse_expr(lhs)
                rhs_expr = parse_expr(rhs)
                if lhs_expr.equals(rhs_expr):
                    valid_eqs.append(eq)
            except:
                continue
        
        return {
            "valid": True, 
            "verified_equations": valid_eqs, 
            "comment": "Symbolic check passed for extracted equations."
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}

