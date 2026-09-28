from typing import TypedDict


class AgentState(TypedDict):
    pdf_path: str
    output_dir: str
    num_questions: int
    difficulty: str
    language: str
    pdf_images: list[dict]
    draft_questions: list[dict]
    final_questions: list[dict]
    iteration: int
