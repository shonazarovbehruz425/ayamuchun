from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class FileResponse(BaseModel):
    id: int
    file_name: str
    file_type: str
    file_size: int
    uploaded_at: datetime

class QuizResponse(BaseModel):
    id: int
    title: str
    subject: str
    questions_count: int
    created_at: datetime

class AIRequest(BaseModel):
    text: str
    action: str
    language: str = 'uz'

class AIResponse(BaseModel):
    result: str
    action: str

class QuizCreateRequest(BaseModel):
    topic: str
    num_questions: int
    quiz_type: str

class QuizDetailResponse(BaseModel):
    id: int
    title: str
    questions: List[dict]

class StatsResponse(BaseModel):
    file_count: int
    quiz_count: int
    last_active: datetime

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
