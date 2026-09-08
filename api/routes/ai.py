import os
import re
import time
import logging
from typing import List, Optional, Dict, Any
import docx
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field, field_validator
from .auth import get_current_user
from ..schemas.responses import AIRequest, AIResponse
from bot.services.ai_service import get_ai_service
from bot.config import get_settings
from bot.database.engine import get_session
from bot.database import crud
from bot.processors.converter import FileConverter
from bot.processors.word_processor import WordProcessor
from bot.processors.pdf_processor import PDFProcessor
from bot.processors.image_processor import ImageProcessor
from bot.utils.helpers import sanitize_filename, parse_lesson_subject_topic
from bot.utils.validators import is_prompt_injection, rate_limiter
from .files import send_file_to_telegram, save_and_backup_user_file, build_file_caption, save_upload_stream_safely

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
    role: str  # "user" | "assistant"
    content: str = Field(..., min_length=1, max_length=15000)

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ('user', 'assistant'):
            raise ValueError("Faqat 'user' va 'assistant' rollari ruxsat etilgan")
        return v

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Xabar matni bo'sh bo'lishi mumkin emas")
        if len(clean) > 15000:
            raise ValueError("Xabar uzunligi 15000 belgidan oshmasligi kerak")
        if is_prompt_injection(clean):
            raise ValueError("Xavfsizlik qoidalariga zid bo'lgan so'rov aniqlandi")
        return clean


class AIChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=20)

    @field_validator('messages')
    @classmethod
    def validate_messages_total_chars(cls, v: List[ChatMessage]) -> List[ChatMessage]:
        if not v:
            raise ValueError("Xabarlar ro'yxati bo'sh bo'lishi mumkin emas")
        if len(v) > 20:
            raise ValueError("Suhbat kontekstida maksimal 20 ta xabar yuborish mumkin")
        total_len = sum(len(m.content) for m in v)
        if total_len > 35000:
            raise ValueError(f"Umumiy suhbat konteksti hajmi juda katta ({total_len} belgi, ruxsat etilgan: 35 000)")
        return v


class AIChatResponse(BaseModel):
    message: str
    role: str = "assistant"
    model: Optional[str] = None


@router.post("/chat", response_model=AIChatResponse)
async def chat_with_ai(req: AIChatRequest, user: dict = Depends(get_current_user)):
    """To'liq interaktiv AI Chat (ChatGPT / Gemini kabi jonli muloqot va suhbat xotirasi)."""
    user_key = f"user_{user.get('telegram_id', 'unknown')}"
    rate_limiter.check(user_key, limit=20, window_seconds=60, action="chat xabari")

    try:
        dict_messages = [{"role": m.role, "content": m.content} for m in req.messages]
        reply_text = await ai_service.generate_chat(dict_messages)

        # Persist messages & log usage in database
        try:
            tokens = getattr(ai_service, "last_token_usage", {}) or {}
            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
                last_user_msg = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
                await crud.log_usage(
                    session,
                    db_user.id,
                    "ai_chat",
                    last_user_msg[:60],
                    prompt_tokens=tokens.get("prompt_tokens", 0),
                    completion_tokens=tokens.get("completion_tokens", 0),
                    total_tokens=tokens.get("total_tokens", 0)
                )
                if last_user_msg:
                    await crud.save_chat_message(session, db_user.id, "user", last_user_msg, session_id="web")
                await crud.save_chat_message(session, db_user.id, "assistant", reply_text, session_id="web")
        except Exception as log_err:
            logger.warning(f"Could not persist chat message: {log_err}")

        return AIChatResponse(
            message=reply_text,
            role="assistant",
            model=getattr(ai_service, "model_name", "ai")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="AI xizmatida xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")


@router.get("/chat/history")
async def get_chat_history_endpoint(session_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Fetch persistent chat history for the user from database (survives restart & incognito)."""
    try:
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
            messages = await crud.get_chat_history(session, db_user.id, session_id=session_id or "web", limit=50)
            return {
                "status": "ok",
                "messages": [
                    {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                    for m in messages
                ]
            }
    except Exception as e:
        logger.error(f"Get chat history error: {e}")
        return {"status": "ok", "messages": []}


@router.delete("/chat/history")
async def clear_chat_history_endpoint(session_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Clear user chat history from database."""
    try:
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
            await crud.clear_chat_history(session, db_user.id, session_id=session_id or "web")
            return {"status": "ok", "message": "Suhbatlar tarixi tozalandi"}
    except Exception as e:
        logger.error(f"Clear chat history error: {e}")
        raise HTTPException(status_code=500, detail="Suhbatlar tarixini tozalashda xatolik yuz berdi.")


class ActionTelegramRequest(BaseModel):
    title: str = Field("EduBot AI Natijasi", max_length=200)
    text: str = Field(..., min_length=1, max_length=50000)
    action_type: str = Field("text")

    @field_validator("title", "text", "action_type")
    @classmethod
    def strip_fields(cls, v: str) -> str:
        clean = v.strip() if isinstance(v, str) else v
        if not clean:
            raise ValueError("Maydon bo'sh bo'lishi mumkin emas")
        return clean


class ExportDocxRequest(BaseModel):
    title: str = Field("EduBot AI Natijasi", max_length=200)
    text: str = Field(..., min_length=1, max_length=50000)

    @field_validator("title", "text")
    @classmethod
    def strip_fields(cls, v: str) -> str:
        clean = v.strip() if isinstance(v, str) else v
        if not clean:
            raise ValueError("Maydon bo'sh bo'lishi mumkin emas")
        return clean


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
    user_key = f"user_{user.get('telegram_id', 'unknown')}"
    rate_limiter.check(user_key, limit=20, window_seconds=60, action="xulosa so'rovi")
    try:
        result = await ai_service.summarize_text(req.text, req.language)
        tokens = getattr(ai_service, "last_token_usage", {}) or {}
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            await crud.log_usage(
                session, db_user.id, "ai_summarize", req.text[:50],
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
                total_tokens=tokens.get("total_tokens", 0)
            )
        return AIResponse(result=result, action="summarize")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI summarize error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Xulosa tayyorlashda xatolik yuz berdi.")


@router.post("/translate", response_model=AIResponse)
async def translate(req: AIRequest, user: dict = Depends(get_current_user)):
    user_key = f"user_{user.get('telegram_id', 'unknown')}"
    rate_limiter.check(user_key, limit=20, window_seconds=60, action="tarjima so'rovi")
    try:
        target_lang = req.language or "uz"
        result = await ai_service.translate_text(req.text, target_lang)
        tokens = getattr(ai_service, "last_token_usage", {}) or {}
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            await crud.log_usage(
                session, db_user.id, "ai_translate", f"[{target_lang}] {req.text[:60]}",
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
                total_tokens=tokens.get("total_tokens", 0)
            )
        return AIResponse(result=result, action="translate")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI translate error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Tarjima qilishda xatolik yuz berdi.")


@router.post("/lesson-plan", response_model=AIResponse)
async def lesson_plan(req: AIRequest, user: dict = Depends(get_current_user)):
    user_key = f"user_{user.get('telegram_id', 'unknown')}"
    rate_limiter.check(user_key, limit=20, window_seconds=60, action="dars rejasi so'rovi")
    try:
        subject, topic = parse_lesson_subject_topic(req.text)
        result = await ai_service.generate_lesson_plan(subject, topic, language=req.language)
        tokens = getattr(ai_service, "last_token_usage", {}) or {}
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            await crud.log_usage(
                session, db_user.id, "ai_lesson_plan", f"{subject} — {topic}"[:60],
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
                total_tokens=tokens.get("total_tokens", 0)
            )
        return AIResponse(result=result, action="lesson-plan")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI lesson plan error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Dars rejasi yaratishda xatolik yuz berdi.")


@router.post("/grammar", response_model=AIResponse)
async def grammar(req: AIRequest, user: dict = Depends(get_current_user)):
    user_key = f"user_{user.get('telegram_id', 'unknown')}"
    rate_limiter.check(user_key, limit=20, window_seconds=60, action="grammatika tekshirish")
    try:
        result = await ai_service.check_grammar(req.text)
        tokens = getattr(ai_service, "last_token_usage", {}) or {}
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            await crud.log_usage(
                session, db_user.id, "ai_grammar", req.text[:50],
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
                total_tokens=tokens.get("total_tokens", 0)
            )
        return AIResponse(result=result, action="grammar")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI grammar error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Grammatika tekshirishda xatolik yuz berdi.")


@router.post("/improve", response_model=AIResponse)
async def improve(req: AIRequest, user: dict = Depends(get_current_user)):
    user_key = f"user_{user.get('telegram_id', 'unknown')}"
    rate_limiter.check(user_key, limit=20, window_seconds=60, action="matnni yaxshilash")
    try:
        result = await ai_service.improve_text(req.text, req.language)
        tokens = getattr(ai_service, "last_token_usage", {}) or {}
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            await crud.log_usage(
                session, db_user.id, "ai_improve", req.text[:50],
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
                total_tokens=tokens.get("total_tokens", 0)
            )
        return AIResponse(result=result, action="improve")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI improve error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Matnni yaxshilashda xatolik yuz berdi.")


@router.post("/explain", response_model=AIResponse)
async def explain(req: AIRequest, user: dict = Depends(get_current_user)):
    user_key = f"user_{user.get('telegram_id', 'unknown')}"
    rate_limiter.check(user_key, limit=20, window_seconds=60, action="tushuntirish so'rovi")
    try:
        result = await ai_service.explain_topic(req.text, req.language)
        tokens = getattr(ai_service, "last_token_usage", {}) or {}
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            await crud.log_usage(
                session, db_user.id, "ai_explain", req.text[:50],
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
                total_tokens=tokens.get("total_tokens", 0)
            )
        return AIResponse(result=result, action="explain")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI explain error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Mavzuni tushuntirishda xatolik yuz berdi.")


@router.post("/key-points", response_model=AIResponse)
async def key_points_endpoint(req: AIRequest, user: dict = Depends(get_current_user)):
    """Extract key points and bullet insights from text."""
    user_key = f"user_{user.get('telegram_id', 'unknown')}"
    rate_limiter.check(user_key, limit=20, window_seconds=60, action="asosiy fikrlarni ajratish")
    try:
        result = await ai_service.extract_key_points(req.text, req.language)
        tokens = getattr(ai_service, "last_token_usage", {}) or {}
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            await crud.log_usage(
                session, db_user.id, "ai_key_points", req.text[:50],
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
                total_tokens=tokens.get("total_tokens", 0)
            )
        return AIResponse(result=result, action="key_points")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI key points error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Asosiy fikrlarni ajratishda xatolik yuz berdi.")


@router.post("/quiz", response_model=AIResponse)
async def create_quiz_ai(req: AIRequest, user: dict = Depends(get_current_user)):
    """Generate structured quiz questions with multiple choice options."""
    user_key = f"user_{user.get('telegram_id', 'unknown')}"
    rate_limiter.check(user_key, limit=15, window_seconds=60, action="test tuzish")
    try:
        topic = req.text
        count = 5
        # Check if question count is specified in text
        m = re.search(r'(\d+)\s*ta\s*savol', topic, re.IGNORECASE)
        if m:
            count = int(m.group(1))
            topic = re.sub(r'(\d+)\s*ta\s*savol[:—\s]*', '', topic, flags=re.IGNORECASE).strip()
            
        quiz_data = await ai_service.generate_quiz(topic, num_questions=min(20, max(3, count)), language=req.language or "uz")
        tokens = getattr(ai_service, "last_token_usage", {}) or {}
        
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
            await crud.log_usage(
                session, db_user.id, "ai_quiz", topic[:50],
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
                total_tokens=tokens.get("total_tokens", 0)
            )
            
        return AIResponse(result="\n".join(lines), action="quiz")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI quiz error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Test savollarini tuzishda xatolik yuz berdi.")



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

        def _chunk_text(text: str, max_size: int = 3900) -> List[str]:
            if len(text) <= max_size:
                return [text]
            res = []
            remaining = text
            while len(remaining) > max_size:
                split_idx = remaining.rfind("\n", 0, max_size)
                if split_idx == -1 or split_idx < max_size // 2:
                    split_idx = remaining.rfind(" ", 0, max_size)
                if split_idx == -1 or split_idx < max_size // 2:
                    split_idx = max_size
                chunk = remaining[:split_idx].strip()
                if chunk:
                    res.append(chunk)
                remaining = remaining[split_idx:].strip()
            if remaining:
                res.append(remaining)
            return res

        chunks = _chunk_text(msg_text, max_size=3900)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for chunk in chunks:
                resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": tg_id,
                        "text": chunk,
                        "parse_mode": "Markdown"
                    }
                )
                if not resp.is_success:
                    # Retry with plain text if markdown formatting fails
                    clean_plain = chunk.replace('*', '').replace('_', '').replace('`', '')
                    await client.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={
                            "chat_id": tg_id,
                            "text": clean_plain
                        }
                    )
        return {"success": True, "message": "Xabar to'liq hajmda Telegramingizga yuborildi!"}
    except Exception as e:
        logger.error(f"Send to telegram error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── MULTIMODAL AI CHAT WITH FILES & AUTOMATIC TOOL DISPATCHER ───────────

converter_tool = FileConverter()
word_processor_tool = WordProcessor()
pdf_processor_tool = PDFProcessor()
image_processor_tool = ImageProcessor()

@router.post("/chat-with-files")
async def chat_with_files(
    prompt: str = Form(""),
    files: List[UploadFile] = File(...),
    user: dict = Depends(get_current_user)
):
    """
    Foydalanuvchi bir nechta fayllar (rasm, PDF, Word va b.) yuklaganda
    va vazifa berganida avtomatik ravishda mos asbobni (converter, photo, pdf, word, text-extraction + AI)
    ishga tushiruvchi multimodal asboblar tizimi.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Kamida bitta fayl yuklanishi shart")

    user_key = f"user_{user.get('telegram_id', 'unknown')}"
    rate_limiter.check(user_key, limit=10, window_seconds=60, action="fayllar bilan ishlash so'rovi")

    prompt_clean = (prompt or "").strip()
    if prompt_clean:
        if len(prompt_clean) > 15000:
            raise HTTPException(status_code=400, detail="Topshiriq matni 15 000 belgidan oshmasligi kerak")
        if is_prompt_injection(prompt_clean):
            raise HTTPException(status_code=400, detail="Xavfsizlik qoidalariga zid bo'lgan so'rov aniqlandi")

    tg_id = user.get("telegram_id")
    user_upload_dir = os.path.join(settings.upload_dir, str(tg_id or "shared"))
    os.makedirs(user_upload_dir, exist_ok=True)
    os.makedirs(settings.processed_dir, exist_ok=True)

    timestamp = int(time.time())
    saved_files = [] # list of (orig_name, ext, local_path, is_image, is_pdf, is_word)

    try:
        # 1. Save all uploaded files to disk safely
        for idx, u_file in enumerate(files):
            orig_name = u_file.filename or f"file_{idx}"
            base_part, raw_ext = os.path.splitext(orig_name)
            ext = raw_ext.lower()
            clean_name = f"{sanitize_filename(base_part)}{ext}"
            save_path = os.path.join(user_upload_dir, f"ai_input_{timestamp}_{idx}_{clean_name}")
            
            await save_upload_stream_safely(u_file, save_path)

            is_img = ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic")
            is_pdf = ext == ".pdf"
            is_word = ext in (".docx", ".doc")
            file_size = os.path.getsize(save_path) if os.path.exists(save_path) else 0
            saved_files.append({
                "orig_name": orig_name,
                "clean_name": clean_name,
                "ext": ext,
                "path": save_path,
                "is_img": is_img,
                "is_pdf": is_pdf,
                "is_word": is_word,
                "size": file_size
            })

        user_prompt_lower = prompt_clean.lower()
        all_images = [f for f in saved_files if f["is_img"]]
        all_pdfs = [f for f in saved_files if f["is_pdf"]]
        all_words = [f for f in saved_files if f["is_word"]]

        # ── TOOL DISPATCH LOGIC ────────────────────────────────────────

        # ASBOB 1: RASMLARDAN PDF YARATISH
        # Agar yuklangan fayllar rasm bo'lsa va prompt bo'sh bo'lsa yoki "pdf", "birlashtir", "jamla", "kitob" kabi so'zlar bo'lsa
        if len(all_images) == len(saved_files) and len(all_images) >= 1 and (
            not user_prompt_lower or any(k in user_prompt_lower for k in ["pdf", "birlashtir", "jamla", "kitob", "fayl qil", "varaq", "sahifa"])
        ) and not any(k in user_prompt_lower for k in ["3x4", "3*4", "hujjat foto", "pasport", "vizas"]):
            from PIL import Image, ImageOps
            pil_images = []
            for item in all_images:
                try:
                    im = Image.open(item["path"])
                    im = ImageOps.exif_transpose(im)
                    if im.mode != "RGB":
                        im = im.convert("RGB")
                    pil_images.append(im)
                except Exception as img_err:
                    logger.warning(f"Rasm ochishda xato: {img_err}")

            if pil_images:
                out_name = f"Rasmlar_PDF_{timestamp}.pdf"
                out_path = os.path.join(settings.processed_dir, out_name)
                pil_images[0].save(
                    out_path,
                    save_all=True,
                    append_images=pil_images[1:],
                    resolution=150.0,
                    quality=95
                )

                async with get_session() as session:
                    db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
                    rec = await save_and_backup_user_file(
                        session=session,
                        db_user=db_user,
                        user_dict=user,
                        local_path=out_path,
                        file_name=out_name,
                        file_type="pdf",
                        tool_name="AI_Rasmlar_PDF"
                    )

                caption = build_file_caption(
                    file_name=out_name,
                    tool_name="Rasmlar jamlangan PDF",
                    details=[f"Yuklangan rasmlar soni: {len(pil_images)} ta", "Standart: A4 yuqori sifat (150 DPI)"],
                    file_size=os.path.getsize(out_path)
                )
                if tg_id:
                    try:
                        await send_file_to_telegram(tg_id, out_path, caption, file_id=rec.telegram_file_id)
                    except Exception:
                        pass

                return {
                    "message": f"✅ Siz yuklagan {len(pil_images)} ta rasm muvaffaqiyatli bitta yuqori sifatli PDF hujjatiga birlashtirildi! Quyidagi tugma orqali yuklab olishingiz mumkin:",
                    "role": "assistant",
                    "result_file": {
                        "id": rec.id,
                        "file_name": out_name,
                        "file_type": "pdf",
                        "file_size": os.path.getsize(out_path),
                        "download_url": f"/api/files/{rec.id}/download"
                    }
                }

        # ASBOB 2: 3x4 HUJJAT RASMI VA 10x15 sm VARAQ
        if len(all_images) >= 1 and any(k in user_prompt_lower for k in ["3x4", "3*4", "hujjat rasm", "pasport", "viza", "guvohnoma"]):
            first_img = all_images[0]
            single_name = f"foto_3x4_{timestamp}.jpg"
            sheet_name = f"foto_3x4_varaq_10x15_{timestamp}.jpg"
            single_path = os.path.join(settings.processed_dir, single_name)
            sheet_path = os.path.join(settings.processed_dir, sheet_name)

            change_bg = "oq" in user_prompt_lower or "fon" in user_prompt_lower
            add_corner = "burchak" in user_prompt_lower or "doira" in user_prompt_lower

            await image_processor_tool.process_photo_3x4(
                input_path=first_img["path"],
                output_single_path=single_path,
                output_sheet_path=sheet_path,
                bg_color_hex="#FFFFFF",
                change_bg=change_bg,
                add_corner=add_corner,
                brightness=1.0,
                contrast=1.0,
                dpi=300
            )

            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
                single_rec = await save_and_backup_user_file(
                    session=session,
                    db_user=db_user,
                    user_dict=user,
                    local_path=single_path,
                    file_name=single_name,
                    file_type="jpg",
                    tool_name="AI_Foto_3x4"
                )
                sheet_rec = await save_and_backup_user_file(
                    session=session,
                    db_user=db_user,
                    user_dict=user,
                    local_path=sheet_path,
                    file_name=sheet_name,
                    file_type="jpg",
                    tool_name="AI_Foto_3x4_Varaq"
                )

            if tg_id:
                try:
                    await send_file_to_telegram(tg_id, single_path, "📸 3×4 Hujjat fotosi (Yakka)")
                    await send_file_to_telegram(tg_id, sheet_path, "🖨️ 10×15 sm Chop etish varaqasi (6 ta foto)")
                except Exception:
                    pass

            return {
                "message": "✅ Fotosuratingiz rasmiy 3×4 sm standart o'lchamiga keltirildi va chop etish uchun 10×15 sm varaqqa 6 nusxada joylashtirildi!",
                "role": "assistant",
                "result_file": {
                    "id": sheet_rec.id,
                    "file_name": sheet_name,
                    "file_type": "jpg",
                    "file_size": os.path.getsize(sheet_path),
                    "download_url": f"/api/files/{sheet_rec.id}/download"
                }
            }

        # ASBOB 3: PDF ➔ WORD (DOCX) KONVERTATSIYA
        if len(all_pdfs) >= 1 and any(k in user_prompt_lower for k in ["word", "docx", "dok", "tahrirlanadigan", "o'gir", "aylantir", "konvert"]):
            pdf_item = all_pdfs[0]
            base_n = os.path.splitext(pdf_item["clean_name"])[0]
            out_name = f"{base_n}_Word_{timestamp}.docx"
            out_path = os.path.join(settings.processed_dir, out_name)

            await converter_tool.pdf_to_word(pdf_item["path"], out_path)

            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
                rec = await save_and_backup_user_file(
                    session=session,
                    db_user=db_user,
                    user_dict=user,
                    local_path=out_path,
                    file_name=out_name,
                    file_type="docx",
                    tool_name="AI_PDF_To_Word"
                )

            if tg_id:
                try:
                    c = build_file_caption(out_name, "PDF ➔ Word Konvertatsiya", file_size=os.path.getsize(out_path))
                    await send_file_to_telegram(tg_id, out_path, c, file_id=rec.telegram_file_id)
                except Exception:
                    pass

            return {
                "message": f"✅ `{pdf_item['orig_name']}` hujjati muvaffaqiyatli Word (DOCX) formatiga o'tkazildi! Endi uni bemalol tahrirlashingiz mumkin.",
                "role": "assistant",
                "result_file": {
                    "id": rec.id,
                    "file_name": out_name,
                    "file_type": "docx",
                    "file_size": os.path.getsize(out_path),
                    "download_url": f"/api/files/{rec.id}/download"
                }
            }

        # ASBOB 4: WORD ➔ PDF KONVERTATSIYA
        if len(all_words) >= 1 and any(k in user_prompt_lower for k in ["pdf", "qotir", "o'gir", "aylantir"]):
            word_item = all_words[0]
            base_n = os.path.splitext(word_item["clean_name"])[0]
            out_name = f"{base_n}_{timestamp}.pdf"
            out_path = os.path.join(settings.processed_dir, out_name)

            await converter_tool.word_to_pdf(word_item["path"], out_path)

            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
                rec = await save_and_backup_user_file(
                    session=session,
                    db_user=db_user,
                    user_dict=user,
                    local_path=out_path,
                    file_name=out_name,
                    file_type="pdf",
                    tool_name="AI_Word_To_PDF"
                )

            if tg_id:
                try:
                    c = build_file_caption(out_name, "Word ➔ PDF Konvertatsiya", file_size=os.path.getsize(out_path))
                    await send_file_to_telegram(tg_id, out_path, c, file_id=rec.telegram_file_id)
                except Exception:
                    pass

            return {
                "message": f"✅ Word hujjatingiz asl shriftlar va sahifa mutanosibligi saqlangan holda PDF formatiga aylantirildi!",
                "role": "assistant",
                "result_file": {
                    "id": rec.id,
                    "file_name": out_name,
                    "file_type": "pdf",
                    "file_size": os.path.getsize(out_path),
                    "download_url": f"/api/files/{rec.id}/download"
                }
            }

        # ASBOB 5: BIR NECHTA PDF HUJJATLARNI BIRLASHTIRISH
        if len(all_pdfs) >= 2 and any(k in user_prompt_lower for k in ["birlashtir", "ulash", "qosh", "qo'sh", "jamla"]):
            pdf_paths = [p["path"] for p in all_pdfs]
            out_name = f"Birlashtirilgan_{timestamp}.pdf"
            out_path = os.path.join(settings.processed_dir, out_name)

            await pdf_processor_tool.merge_pdfs(pdf_paths, out_path)

            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
                rec = await save_and_backup_user_file(
                    session=session,
                    db_user=db_user,
                    user_dict=user,
                    local_path=out_path,
                    file_name=out_name,
                    file_type="pdf",
                    tool_name="AI_PDF_Birlashtirish"
                )

            if tg_id:
                try:
                    c = build_file_caption(out_name, "Birlashtirilgan PDF", details=[f"Fayllar soni: {len(pdf_paths)} ta"], file_size=os.path.getsize(out_path))
                    await send_file_to_telegram(tg_id, out_path, c, file_id=rec.telegram_file_id)
                except Exception:
                    pass

            return {
                "message": f"✅ Siz yuklagan {len(pdf_paths)} ta PDF hujjati ketma-ketlikda bitta to'liq PDF ga birlashtirildi!",
                "role": "assistant",
                "result_file": {
                    "id": rec.id,
                    "file_name": out_name,
                    "file_type": "pdf",
                    "file_size": os.path.getsize(out_path),
                    "download_url": f"/api/files/{rec.id}/download"
                }
            }

        # ── ASBOB 6: HUJJATLAR ICHIDAGI MATNNI SUG'URIB OLIB AI TAHLIL QILISH (QA / TEST / XULOSA) ──
        # Agar konvertatsiya buyrug'i bo'lmasa yoki matn tahlili, test tuzish, tarjima, savollar so'ralsa:
        extracted_texts = []
        for f_info in saved_files:
            try:
                if f_info["is_pdf"]:
                    txt = await pdf_processor_tool.extract_text(f_info["path"])
                    if txt and txt.strip():
                        extracted_texts.append(f"--- HUJJAT: {f_info['orig_name']} ---\n{txt.strip()[:10000]}")
                elif f_info["is_word"]:
                    txt = await word_processor_tool.extract_text(f_info["path"])
                    if txt and txt.strip():
                        extracted_texts.append(f"--- HUJJAT: {f_info['orig_name']} ---\n{txt.strip()[:10000]}")
                elif f_info["ext"] in (".txt", ".md", ".csv", ".json"):
                    with open(f_info["path"], "r", encoding="utf-8", errors="ignore") as tf:
                        txt = tf.read()
                        if txt.strip():
                            extracted_texts.append(f"--- FAYL: {f_info['orig_name']} ---\n{txt.strip()[:10000]}")
            except Exception as read_err:
                logger.warning(f"Fayl matnini o'qishda xatolik ({f_info['orig_name']}): {read_err}")

        # Agar hujjatlardan matn ajratib olingan bo'lsa
        if extracted_texts:
            full_document_context = "\n\n".join(extracted_texts)
            user_instruction = prompt.strip() if prompt.strip() else "Ushbu yuklangan hujjat(lar) mazmunini to'liq tahlil qilib, asosiy g'oyalari, bo'limlari va qisqacha xulosasini ber."

            ai_messages = [
                {
                    "role": "system",
                    "content": (
                        "Siz professional pedagogik AI assistentsiz. Foydalanuvchi sizga hujjat(lar) matnini taqdim etdi. "
                        "Ushbu hujjat matniga tayangan holda foydalanuvchi so'ragan vazifani (test tuzish, konspekt, dars rejasi, tahlil, xulosa yoki savollarga javob) "
                        "o'zbek tilida juda chiroyli, aniq, tushunarli va professional tarzda bajarib bering."
                    )
                },
                {
                    "role": "user",
                    "content": f"Foydalanuvchi topshirig'i:\n{user_instruction}\n\nBiriktirilgan hujjatlar matni:\n{full_document_context[:25000]}"
                }
            ]

            reply_text = await ai_service.generate_chat(ai_messages)

            # Agar foydalanuvchi test tuzishni so'ragan bo'lsa yoki matn Word shaklida kerak bo'lsa, Word hujjati ham tayyorlab beramiz
            result_file_data = None
            if any(k in user_prompt_lower for k in ["test", "savol", "konspekt", "dars rejasi", "hujjat shaklida", "word"]) or len(reply_text) > 1500:
                doc_title = "AI_Tahlil_va_Xulosa"
                if "test" in user_prompt_lower:
                    doc_title = "Testlar_To'plami"
                elif "konspekt" in user_prompt_lower or "reja" in user_prompt_lower:
                    doc_title = "Dars_Konspekti"

                out_doc_name = f"{doc_title}_{timestamp}.docx"
                out_doc_path = os.path.join(settings.processed_dir, out_doc_name)
                create_clean_docx(doc_title.replace("_", " "), reply_text, out_doc_path)

                async with get_session() as session:
                    db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
                    rec = await save_and_backup_user_file(
                        session=session,
                        db_user=db_user,
                        user_dict=user,
                        local_path=out_doc_path,
                        file_name=out_doc_name,
                        file_type="docx",
                        tool_name="AI_Matn_Docx"
                    )

                result_file_data = {
                    "id": rec.id,
                    "file_name": out_doc_name,
                    "file_type": "docx",
                    "file_size": os.path.getsize(out_doc_path),
                    "download_url": f"/api/files/{rec.id}/download"
                }

            # Log usage for document analysis
            try:
                tokens = getattr(ai_service, "last_token_usage", {}) or {}
                async with get_session() as session:
                    db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
                    file_cnt = len(saved_files)
                    await crud.log_usage(
                        session,
                        db_user.id,
                        "ai_chat_with_files",
                        f"{file_cnt} ta fayl: {user_instruction[:40]}",
                        prompt_tokens=tokens.get("prompt_tokens", 0),
                        completion_tokens=tokens.get("completion_tokens", 0),
                        total_tokens=tokens.get("total_tokens", 0)
                    )
            except Exception as log_err:
                logger.warning(f"Could not log chat-with-files usage: {log_err}")

            return {
                "message": reply_text,
                "role": "assistant",
                "result_file": result_file_data
            }

        # Agar hech qanday matn o'qib bo'lmagan bo'lsa (masalan faqat rasm yuklangan, ammo konvertatsiya buyrug'i berilmagan)
        file_names_str = ", ".join([f["orig_name"] for f in saved_files])
        fallback_prompt = prompt or f"{file_names_str} fayllari qabul qilindi. Ushbu fayllar bilan nima qilishimni xohlaysiz? Masalan: 'PDF ga aylantir', '3x4 rasm qil', yoki matnli savol bering."
        
        reply_text = await ai_service.generate_chat([
            {"role": "user", "content": f"Foydalanuvchi quyidagi fayllarni yukladi: {file_names_str}.\nFoydalanuvchi so'rovi: {fallback_prompt}"}
        ])

        # Log usage to DB
        try:
            tokens = getattr(ai_service, "last_token_usage", {}) or {}
            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "User"))
                file_cnt = len(saved_files)
                await crud.log_usage(
                    session,
                    db_user.id,
                    "ai_chat_with_files",
                    f"{file_cnt} ta fayl: {prompt[:40]}",
                    prompt_tokens=tokens.get("prompt_tokens", 0),
                    completion_tokens=tokens.get("completion_tokens", 0),
                    total_tokens=tokens.get("total_tokens", 0)
                )
        except Exception as log_err:
            logger.warning(f"Could not log chat-with-files usage: {log_err}")

        return {
            "message": reply_text,
            "role": "assistant",
            "result_file": None
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Chat with files error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Fayllar bilan ishlashda xatolik yuz berdi.")

