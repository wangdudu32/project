from typing import TypedDict, List, Annotated, Any, Dict
import operator

class QuestionItem(TypedDict):
    question: str
    answer: str
    analysis: str
    difficulty: str
    type: str
    image_path: str
    feedback: str
    status: str

class AgentState(TypedDict):
    pdf_path: str
    num_questions: int
    pdf_images: List[str]
    draft_questions: List[QuestionItem]
    final_questions: List[QuestionItem]
    iteration: int
