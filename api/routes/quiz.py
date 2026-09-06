import os
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse as FastFileResponse

from .auth import get_current_user
from ..schemas.responses import QuizResponse, QuizCreateRequest, QuizDetailResponse
from bot.services.ai_service import AIService
from bot.services.quiz_service import QuizService
from bot.config import get_settings
from bot.database.engine import get_session
from bot.database import crud

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

ai_service = AIService(api_key=settings.GEMINI_API_KEY)
quiz_service = QuizService(ai_service=ai_service)

@router.get("/list", response_model=List[QuizResponse])
async def list_quizzes(user: dict = Depends(get_current_user)):
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        quizzes = await crud.get_user_quizzes(session, db_user.id)
        return [
            QuizResponse(
                id=q.id,
                title=q.title,
                subject=q.subject,
                questions_count=q.questions_count,
                created_at=q.created_at
            ) for q in quizzes
        ]

@router.post("/create", response_model=QuizResponse)
async def create_quiz(req: QuizCreateRequest, user: dict = Depends(get_current_user)):
    try:
        questions = await ai_service.generate_quiz(
            text=req.topic,
            num_questions=req.num_questions,
            quiz_type=req.quiz_type
        )
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            quiz = await crud.create_quiz(
                session=session,
                user_id=db_user.id,
                title=req.topic[:60],
                subject="Ta'lim",
                questions_count=len(questions),
                questions_data=questions
            )
            await crud.log_usage(session, db_user.id, "create_quiz", req.topic[:50])
            
            return QuizResponse(
                id=quiz.id,
                title=quiz.title,
                subject=quiz.subject,
                questions_count=quiz.questions_count,
                created_at=quiz.created_at
            )
    except Exception as e:
        logger.error(f"Quiz creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{quiz_id}", response_model=QuizDetailResponse)
async def get_quiz(quiz_id: int, user: dict = Depends(get_current_user)):
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        quizzes = await crud.get_user_quizzes(session, db_user.id)
        target = next((q for q in quizzes if q.id == quiz_id), None)
        
        if not target:
            raise HTTPException(status_code=404, detail="Test topilmadi")
            
        return QuizDetailResponse(
            id=target.id,
            title=target.title,
            questions=target.questions_data if isinstance(target.questions_data, list) else []
        )

@router.get("/{quiz_id}/export/{format}")
async def export_quiz(quiz_id: int, format: str, user: dict = Depends(get_current_user)):
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        quizzes = await crud.get_user_quizzes(session, db_user.id)
        target = next((q for q in quizzes if q.id == quiz_id), None)
        
        if not target:
            raise HTTPException(status_code=404, detail="Test topilmadi")
            
        questions = target.questions_data if isinstance(target.questions_data, list) else []
        
        if format.lower() in ("word", "docx"):
            out_file = os.path.join(settings.exports_dir, f"quiz_{target.id}.docx")
            await quiz_service.export_to_word(questions, out_file)
            return FastFileResponse(path=out_file, filename=f"Test_{target.title}.docx", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        elif format.lower() == "pdf":
            out_file = os.path.join(settings.exports_dir, f"quiz_{target.id}.pdf")
            await quiz_service.export_to_pdf(questions, out_file)
            return FastFileResponse(path=out_file, filename=f"Test_{target.title}.pdf", media_type="application/pdf")
        else:
            raise HTTPException(status_code=400, detail=f"Noma'lum format: {format}")
