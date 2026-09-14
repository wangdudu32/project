from pydantic import BaseModel
from typing import List, Optional

class QuestionRequest(BaseModel):
    pdf_path: str
    num_questions: int = 5
    difficulty: str = "medium"

class QuestionResponse(BaseModel):
    questions: List[dict]
