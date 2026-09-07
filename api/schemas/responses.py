from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
from bot.utils.validators import is_prompt_injection

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
    text: str = Field(..., min_length=1, max_length=15000)
    action: str
    language: str = 'uz'

    @field_validator('text')
    @classmethod
    def validate_text(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Matn bo'sh yoki faqat bo'shliqlardan iborat bo'lishi mumkin emas")
        if len(clean) > 15000:
            raise ValueError("Matn uzunligi 15000 belgidan oshmasligi kerak")
        if is_prompt_injection(clean):
            raise ValueError("Xavfsizlik qoidalariga zid bo'lgan so'rov aniqlandi")
        return clean

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
