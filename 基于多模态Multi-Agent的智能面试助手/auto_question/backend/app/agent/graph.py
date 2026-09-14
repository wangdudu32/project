from langgraph.graph import StateGraph, END
from app.agent.state import AgentState, QuestionItem
from app.agent.tools import parse_pdf_to_images, generate_question_with_vlm
import json
import os

MAX_ITERATIONS = 3

def parse_pdf_node(state: AgentState):
    print("--- Parsing PDF ---")
    pdf_path = state['pdf_path']
    images = parse_pdf_to_images(pdf_path)
    return {"pdf_images": images, "iteration": 0}

def generate_questions_node(state: AgentState):
    print("--- Generating Questions (Draft) ---")
    images = state['pdf_images']
    questions = []
    
    # Limit to first few images for demo/speed
    max_pages = min(len(images), 3) 
    
    for i in range(max_pages):
        img_path = images[i]
        prompt = """
        You are an expert interviewer for Large Language Model (LLM) engineer positions.
        Analyze this academic paper content.
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
            response = generate_question_with_vlm(img_path, prompt)
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            q_data = json.loads(response)
            q_data['image_path'] = img_path
            q_data['status'] = 'draft'
            q_data['feedback'] = ''
            questions.append(q_data)
        except Exception as e:
            recovery_success = False
            if "control character" in str(e):
                try:
                     import re
                     clean_response = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response)
                     q_data = json.loads(clean_response)
                     q_data['image_path'] = img_path
                     q_data['status'] = 'draft'
                     q_data['feedback'] = ''
                     questions.append(q_data)
                     recovery_success = True
                except:
                     pass
            
            if not recovery_success:
                try:
                    q_data = json.loads(response, strict=False)
                    q_data['image_path'] = img_path
                    q_data['status'] = 'draft'
                    q_data['feedback'] = ''
                    questions.append(q_data)
                    recovery_success = True
                except:
                    pass

            if not recovery_success:
                 print(f"Error generating for page {i}: {e}")
            
            continue
            
    return {"draft_questions": questions}

def verify_questions_node(state: AgentState):
    drafts = state['draft_questions']
    verified_list = []
    
    all_passed = True
    
    for q in drafts:
        if q['status'] == 'verified':
            verified_list.append(q)
            continue
            
        prompt = f"""
        You are a Principal Engineer and Bar Raiser for LLM hiring.
        Review the following interview question and answer generated from a paper.
        
        Question: {q['question']}
        Answer: {q['answer']}
        
        Checklist:
        1. Is the question suitable for a Senior Algorithm Engineer? (Not too simple)
        2. Is the answer accurate and comprehensive?
        3. Is the answer in first-person perspective ("I")?
        4. Is it in English?
        
        Return ONLY valid JSON.
        Format:
        {{
            "status": "PASS" or "FAIL",
            "feedback": "Specific instructions on how to improve if FAIL, or 'Good' if PASS"
        }}
        """
        try:
            response = generate_question_with_vlm(q['image_path'], prompt)
            
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
                
            res_json = json.loads(response)
            
            if res_json.get('status') == 'PASS':
                q['status'] = 'verified'
                q['feedback'] = res_json.get('feedback', 'Good')
            else:
                q['status'] = 'needs_revision'
                q['feedback'] = res_json.get('feedback', 'Needs improvement')
                all_passed = False
                
        except Exception as e:
            print(f"Verification error: {e}")
            q['status'] = 'needs_revision' 
            q['feedback'] = f"Verification failed: {str(e)}"
            all_passed = False
            
        verified_list.append(q)

    return {"draft_questions": verified_list, "iteration": state['iteration'] + 1}

def revise_questions_node(state: AgentState):
    drafts = state['draft_questions']
    revised_list = []
    
    for q in drafts:
        if q['status'] == 'verified':
            revised_list.append(q)
            continue
            
        prompt = f"""
        You are an expert interviewer. Improve the previous interview question and answer based on the feedback.
        
        Original Question: {q['question']}
        Original Answer: {q['answer']}
        Feedback: {q['feedback']}
        
        Requirements:
        1. Improve technical depth.
        2. Ensure first-person perspective in answer.
        3. English only.
        4. Return ONLY valid JSON.
        
        Format:
        {{
            "question": "The improved interview question",
            "answer": "The improved answer",
            "analysis": "{q['analysis']}",
            "difficulty": "hard",
            "type": "open_ended"
        }}
        """
        try:
            response = generate_question_with_vlm(q['image_path'], prompt)
            
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            q_new = json.loads(response)
            q['question'] = q_new.get('question', q['question'])
            q['answer'] = q_new.get('answer', q['answer'])
            q['status'] = 'draft'
            q['feedback'] = ''
            
        except Exception as e:
            print(f"Revision error: {e}")
            
        revised_list.append(q)
        
    return {"draft_questions": revised_list}

def should_continue(state: AgentState):
    drafts = state['draft_questions']
    iteration = state['iteration']
    
    all_verified = all(q['status'] == 'verified' for q in drafts)
    
    if all_verified or iteration >= MAX_ITERATIONS:
        return "end"
    else:
        return "revise"

def finalize_node(state: AgentState):
    return {"final_questions": state['draft_questions']}

workflow = StateGraph(AgentState)

workflow.add_node("parse_pdf", parse_pdf_node)
workflow.add_node("generate", generate_questions_node)
workflow.add_node("verify", verify_questions_node)
workflow.add_node("revise", revise_questions_node)
workflow.add_node("finalize", finalize_node)

workflow.set_entry_point("parse_pdf")
workflow.add_edge("parse_pdf", "generate")
workflow.add_edge("generate", "verify")

workflow.add_conditional_edges(
    "verify",
    should_continue,
    {
        "revise": "revise",
        "end": "finalize"
    }
)

workflow.add_edge("revise", "verify")
workflow.add_edge("finalize", END)

app = workflow.compile()
