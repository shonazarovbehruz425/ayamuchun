import os
import re
import time
import logging
from typing import List, Optional, Dict, Any
import docx
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .auth import get_current_user
from ..schemas.responses import AIRequest, AIResponse
from bot.services.ai_service import get_ai_service
from bot.config import get_settings
from bot.database.engine import get_session
from bot.database import crud
from .files import send_file_to_telegram

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
ai_service = get_ai_service()


@router.get("/config")
async def get_ai_config():
    """Foydalanuvchilarga ko'rinadigan AI tizim nomi va holati (hech qanday xorijiy brendsiz)."""
    return {
        "display_name": settings.AI_DISPLAY_NAME or "EduBot AI",
        "is_configured": ai_service.is_configured
    }


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class AIChatRequest(BaseModel):
    messages: List[ChatMessage]
    system_prompt: Optional[str] = None


class AIChatResponse(BaseModel):
    message: str
    role: str = "assistant"
    model: Optional[str] = None


@router.post("/chat", response_model=AIChatResponse)
async def chat_with_ai(req: AIChatRequest, user: dict = Depends(get_current_user)):
    """To'liq interaktiv AI Chat (ChatGPT / Gemini kabi jonli muloqot va suhbat xotirasi)."""
    try:
        dict_messages = [{"role": m.role, "content": m.content} for m in req.messages]
        reply_text = await ai_service.generate_chat(dict_messages, system_prompt=req.system_prompt)
        
        # Log usage in database asynchronously
        try:
            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
                last_user_msg = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
                await crud.log_usage(session, db_user.id, "ai_chat", last_user_msg[:60])
        except Exception as log_err:
            logger.warning(f"Could not log AI chat usage: {log_err}")

        return AIChatResponse(
            message=reply_text,
            role="assistant",
            model=getattr(ai_service, "model_name", "ai")
        )
    except Exception as e:
        logger.error(f"AI chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ActionTelegramRequest(BaseModel):
    title: str = "EduBot AI Natijasi"
    text: str
    action_type: str = "text"


class ExportDocxRequest(BaseModel):
    title: str = "EduBot AI Natijasi"
    text: str


def create_clean_docx(title: str, text: str, output_path: str) -> str:
    """Creates a cleanly formatted Word document from Markdown/text."""
    doc = docx.Document()
    h = doc.add_heading(title, level=1)
    h.paragraph_format.space_after = docx.shared.Pt(14)
    
    for line in text.split("\n"):
        line_str = line.strip()
        if not line_str:
            continue
        if line_str.startswith("### "):
            p = doc.add_heading(line_str[4:].strip(), level=3)
        elif line_str.startswith("## "):
            p = doc.add_heading(line_str[3:].strip(), level=2)
        elif line_str.startswith("# "):
            p = doc.add_heading(line_str[2:].strip(), level=1)
        elif line_str.startswith("- ") or line_str.startswith("* ") or line_str.startswith("• "):
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(line_str[2:].strip())
        elif len(line_str) > 2 and line_str[0].isdigit() and (line_str[1:3] in (". ", ") ") or line_str[2:4] in (". ", ") ")):
            parts = line_str.split(" ", 1)
            p = doc.add_paragraph(style="List Number")
            p.add_run(parts[1] if len(parts) > 1 else line_str)
        else:
            p = doc.add_paragraph()
            parts = re.split(r'(\*\*.*?\*\*)', line_str)
            for part in parts:
                if part.startswith("**") and part.endswith("**") and len(part) > 4:
                    r = p.add_run(part[2:-2])
                    r.bold = True
                else:
                    p.add_run(part)
    doc.save(output_path)
    return output_path


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


@router.post("/quiz", response_model=AIResponse)
async def create_quiz_ai(req: AIRequest, user: dict = Depends(get_current_user)):
    """Generate structured quiz questions with multiple choice options."""
    try:
        topic = req.text
        count = 5
        # Check if question count is specified in text
        m = re.search(r'(\d+)\s*ta\s*savol', topic, re.IGNORECASE)
        if m:
            count = int(m.group(1))
            topic = re.sub(r'(\d+)\s*ta\s*savol[:—\s]*', '', topic, flags=re.IGNORECASE).strip()
            
        quiz_data = await ai_service.generate_quiz(topic, num_questions=min(20, max(3, count)), language=req.language or "uz")
        
        lines = [f"📋 **{topic}** mavzusi bo'yicha test savollari\n"]
        for idx, q in enumerate(quiz_data, 1):
            lines.append(f"**{idx}. {q.get('question')}**")
            for opt in q.get('options', []):
                lines.append(f"  • {opt}")
            lines.append(f"  ✅ *To'g'ri javob:* {q.get('correct_answer')}")
            if q.get('explanation'):
                lines.append(f"  💡 *Izoh:* {q.get('explanation')}")
            lines.append("")
            
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            await crud.log_usage(session, db_user.id, "ai_quiz", topic[:50])
            
        return AIResponse(result="\n".join(lines), action="quiz")
    except Exception as e:
        logger.error(f"AI quiz error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-docx")
async def export_ai_docx(req: ExportDocxRequest, user: dict = Depends(get_current_user)):
    """Export AI result to a clean formatted Word (.docx) document."""
    try:
        timestamp = int(time.time())
        clean_title = re.sub(r'[^\w\s-]', '', req.title).strip().replace(' ', '_')[:30] or "AI_Natijasi"
        file_name = f"{clean_title}_{timestamp}.docx"
        output_path = os.path.join(settings.processed_dir, file_name)
        
        create_clean_docx(req.title, req.text, output_path)
        
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            record = await crud.save_file_record(
                session=session,
                user_id=db_user.id,
                file_name=file_name,
                file_type="docx",
                telegram_file_id="",
                local_path=output_path,
                file_size=os.path.getsize(output_path)
            )
            
        return {
            "success": True,
            "file_id": record.id,
            "file_name": file_name,
            "download_url": f"/api/files/{record.id}/download"
        }
    except Exception as e:
        logger.error(f"Export docx error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-to-telegram")
async def send_ai_to_telegram(req: ActionTelegramRequest, user: dict = Depends(get_current_user)):
    """Send AI generated text or Word document directly to user's Telegram chat."""
    tg_id = user.get("telegram_id")
    if not tg_id:
        raise HTTPException(status_code=400, detail="Telegram ID aniqlanmadi")
        
    try:
        # If user wants as file or text is long, generate Word docx and send
        if req.action_type == "file" or len(req.text) > 3000:
            timestamp = int(time.time())
            clean_title = re.sub(r'[^\w\s-]', '', req.title).strip().replace(' ', '_')[:30] or "AI_Hujjati"
            file_name = f"{clean_title}_{timestamp}.docx"
            output_path = os.path.join(settings.processed_dir, file_name)
            create_clean_docx(req.title, req.text, output_path)
            
            caption = f"📄 **{req.title}**\n\nEduBot AI yordamida tayyorlandi."
            await send_file_to_telegram(tg_id, output_path, caption)
            return {"success": True, "message": "Word hujjati Telegramingizga yuborildi!"}
            
        # Otherwise send as formatted message
        bot_token = settings.BOT_TOKEN
        if not bot_token:
            raise HTTPException(status_code=500, detail="Bot token sozlanmagan")
            
        clean_text = req.text.replace('**', '*').replace('###', '📌').replace('##', '📌')
        msg_text = f"🧠 *{req.title}*\n\n{clean_text}\n\n_EduBot AI Pedagogik Yordamchi_"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": tg_id,
                    "text": msg_text[:4096],
                    "parse_mode": "Markdown"
                }
            )
            if not resp.is_success:
                # Retry with plain text if markdown fails
                await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": tg_id,
                        "text": f"🧠 {req.title}\n\n{req.text[:4090]}"
                    }
                )
        return {"success": True, "message": "Xabar Telegramingizga yuborildi!"}
    except Exception as e:
        logger.error(f"Send to telegram error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
