import logging
from fastapi import APIRouter, Depends, HTTPException
from .auth import get_current_user
from ..schemas.responses import AIRequest, AIResponse
from bot.services.ai_service import AIService
from bot.config import get_settings
from bot.database.engine import get_session
from bot.database import crud

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
ai_service = AIService(api_key=settings.GEMINI_API_KEY)

@router.post("/summarize", response_model=AIResponse)
async def summarize(req: AIRequest, user: dict = Depends(get_current_user)):
    try:
        result = await ai_service.summarize_text(req.text, req.language)
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            await crud.log_usage(session, db_user.id, "ai_summarize", req.text[:50])
        return AIResponse(result=result, action="summarize")
    except Exception as e:
        logger.error(f"AI summarize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/translate", response_model=AIResponse)
async def translate(req: AIRequest, user: dict = Depends(get_current_user)):
    try:
        target_lang = req.language or "uz"
        result = await ai_service.translate_text(req.text, target_lang)
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            await crud.log_usage(session, db_user.id, "ai_translate", f"Lang: {target_lang}")
        return AIResponse(result=result, action="translate")
    except Exception as e:
        logger.error(f"AI translate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/lesson-plan", response_model=AIResponse)
async def lesson_plan(req: AIRequest, user: dict = Depends(get_current_user)):
    try:
        subject = "Umumiy"
        topic = req.text
        if "—" in req.text:
            parts = req.text.split("—", 1)
            subject, topic = parts[0].strip(), parts[1].strip()
        elif "-" in req.text:
            parts = req.text.split("-", 1)
            subject, topic = parts[0].strip(), parts[1].strip()
            
        result = await ai_service.generate_lesson_plan(subject, topic, language=req.language)
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            await crud.log_usage(session, db_user.id, "ai_lesson_plan", topic[:50])
        return AIResponse(result=result, action="lesson-plan")
    except Exception as e:
        logger.error(f"AI lesson plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/grammar", response_model=AIResponse)
async def grammar(req: AIRequest, user: dict = Depends(get_current_user)):
    try:
        result = await ai_service.check_grammar(req.text)
        return AIResponse(result=result, action="grammar")
    except Exception as e:
        logger.error(f"AI grammar error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/improve", response_model=AIResponse)
async def improve(req: AIRequest, user: dict = Depends(get_current_user)):
    try:
        result = await ai_service.improve_text(req.text, req.language)
        return AIResponse(result=result, action="improve")
    except Exception as e:
        logger.error(f"AI improve error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/explain", response_model=AIResponse)
async def explain(req: AIRequest, user: dict = Depends(get_current_user)):
    try:
        result = await ai_service.explain_topic(req.text, req.language)
        return AIResponse(result=result, action="explain")
    except Exception as e:
        logger.error(f"AI explain error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
