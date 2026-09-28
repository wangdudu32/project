from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]
Difficulty = Literal["easy", "medium", "hard"]
Language = Literal["zh", "en"]


class QuestionRequest(BaseModel):
    document_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    num_questions: int = Field(default=3, ge=1, le=10)
    difficulty: Difficulty = "medium"
    language: Language = "zh"


class QuestionContent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: Text
    answer: Text
    analysis: Text


class Review(BaseModel):
    status: Literal["PASS", "FAIL"]
    feedback: Text


class AnswerRequest(BaseModel):
    answer: Text


class Evaluation(BaseModel):
    correctness: int = Field(ge=0, le=100, strict=True)
    depth: int = Field(ge=0, le=100, strict=True)
    clarity: int = Field(ge=0, le=100, strict=True)
    feedback: Text
    strengths: list[Text] = Field(max_length=5)
    improvements: list[Text] = Field(min_length=1, max_length=5)
