import os
import gc
import torch
import time
from qwen_vl_utils import process_vision_info
from transformers import Qwen2_5_VLProcessor

def find_files(dirs,path="data/sft"):
    files = []
    for dir in dirs:
        base_path = os.path.join(path, dir)
        for dirpath, _, filenames in os.walk(base_path):
            for filename in filenames:
                if filename.endswith(".parquet"):
                    full_path = os.path.join(dirpath, filename)
                    files.append(full_path)
    return files

def collate_func_deprecated(examples, processor):
    import IPython;IPython.embed();
    texts = [processor.apply_chat_template(example, tokenize=False) for example in examples]
    image_inputs = [process_vision_info(example)[0] for example in examples]
    batch = processor(text=texts, images=image_inputs, return_tensors="pt", padding=True)
    labels = batch["input_ids"].clone()
    labels[labels == processor.tokenizer.pad_token_id] = -100
    if isinstance(processor, Qwen2_5_VLProcessor):
        image_tokens = [151652, 151653, 151655]
    else:
        image_tokens = [processor.tokenizer.convert_tokens_to_ids(processor.image_token)]
    
    for image_token_id in image_tokens:
        labels[labels == image_token_id] = -100
        
    batch["labels"] = labels  
    return batch 

def format_data_chartqa(sample):
    system_message = """You are a Vision Language Model specialized in interpreting visual data from chart images.
    Your task is to analyze the provided chart image and respond to queries with concise answers, usually a single word, number, or short phrase.
    The charts include a variety of types (e.g., line charts, bar charts) and contain colors, labels, and text.
    Focus on delivering accurate, succinct answers based on the visual information. Avoid additional explanation unless absolutely necessary."""
    return [
        {
            "role": "system",
            "content": [{"type": "text","text": system_message}],
        },
        {
            "role": "user",
            "content": [{"type": "image","image": sample["image"],},
                        {"type": "text","text": sample['query'],}],
        },
        {
            "role": "assistant",
            "content": [{"type": "text","text": sample["label"][0]}],
        },
    ]

def collate_func(examples, processor):
    IGNORE_TOKEN_ID = -100
    texts = [
        processor.apply_chat_template(example, tokenize=False) 
        for example in examples
    ]
    image_inputs = [
        process_vision_info(example)[0] 
        for example in examples
    ]
    batch = processor(
        text=texts,
        images=image_inputs,
        return_tensors="pt",
        padding=True
    )

    input_ids = batch["input_ids"]
    labels = input_ids.clone() 
    pad_id = processor.tokenizer.pad_token_id
    labels[labels == pad_id] = IGNORE_TOKEN_ID
    if isinstance(processor, Qwen2_5_VLProcessor):
        image_tokens = [151652, 151653, 151655]
    else:
        image_tokens = [
            processor.tokenizer.convert_tokens_to_ids(processor.image_token)
        ]
    for tok_id in image_tokens:
        labels[labels == tok_id] = IGNORE_TOKEN_ID

    im_start_id = processor.tokenizer("<|im_start|>").input_ids[0]
    im_end_id   = processor.tokenizer("<|im_end|>").input_ids[0]
    system_ids    = processor.tokenizer("system\n").input_ids
    user_ids      = processor.tokenizer("user\n").input_ids
    assistant_ids = processor.tokenizer("assistant\n").input_ids
    newline_id = processor.tokenizer("\n").input_ids[0]

    batch_size, seq_len = input_ids.shape
    for b_idx in range(batch_size):
        ids = input_ids[b_idx]
        labs = labels[b_idx]

        i = 0
        while i < seq_len:
            if ids[i] != im_start_id:
                if ids[i] == im_end_id:
                    i += 1
                elif ids[i]==newline_id:
                    i += 1
                else:
                    labs[i] = IGNORE_TOKEN_ID
                    i += 1
                continue

            i_next = i + 1  
            seg_role = None

            def match_subseq(main_ids, start_idx, pattern):
                end_idx = start_idx + len(pattern)
                if end_idx > len(main_ids):
                    return False
                return list(main_ids[start_idx:end_idx].cpu().numpy()) == pattern

            if match_subseq(ids, i_next, system_ids):
                seg_role = "system"
                seg_role_len = len(system_ids)
            elif match_subseq(ids, i_next, user_ids):
                seg_role = "user"
                seg_role_len = len(user_ids)
            elif match_subseq(ids, i_next, assistant_ids):
                seg_role = "assistant"
                seg_role_len = len(assistant_ids)
                
            i += 1
            if seg_role is None:
                while i < seq_len and ids[i] != im_end_id:
                    labs[i] = IGNORE_TOKEN_ID
                    i += 1
                if i < seq_len and ids[i] == im_end_id:
                    i += 1
                continue

            if seg_role in ["system", "user"]:
                for _ in range(seg_role_len):
                    if i >= seq_len:
                        break
                    labs[i] = IGNORE_TOKEN_ID
                    i += 1
                while i < seq_len and ids[i] != im_end_id:
                    labs[i] = IGNORE_TOKEN_ID
                    i += 1
                if i < seq_len and ids[i] == im_end_id:
                    i += 1
                while i < seq_len and ids[i]==newline_id:
                    i += 1
                continue

            for _ in range(seg_role_len):
                if i >= seq_len:
                    break
                labs[i] = IGNORE_TOKEN_ID
                i += 1
            while i < seq_len and ids[i] != im_end_id:
                i += 1
            if i < seq_len and ids[i] == im_end_id:
                i += 1
            while i < seq_len and ids[i]==newline_id:
                i += 1

    batch["labels"] = labels
    return batch


def clear_memory():
    # Delete variables if they exist in the current global scope
    if 'inputs' in globals(): del globals()['inputs']
    if 'model' in globals(): del globals()['model']
    if 'processor' in globals(): del globals()['processor']
    if 'trainer' in globals(): del globals()['trainer']
    if 'peft_model' in globals(): del globals()['peft_model']
    if 'bnb_config' in globals(): del globals()['bnb_config']
    time.sleep(2)

    # Garbage collection and clearing CUDA memory
    gc.collect()
    time.sleep(2)
    torch.cuda.empty_cache()
    torch.cuda.synchronize()
    time.sleep(2)
    gc.collect()
    time.sleep(2)

    print(f"GPU allocated memory: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
    print(f"GPU reserved memory: {torch.cuda.memory_reserved() / 1024**3:.2f} GB")