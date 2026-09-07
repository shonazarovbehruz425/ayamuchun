"""AI Service — Universal multi-provider AI engine.
Supports Google Gemini, OpenAI, DeepSeek, OpenRouter, Groq, Claude, Ollama, and any OpenAI-compatible custom endpoint.
Configuration is fully managed via server environment variables (AI_PROVIDER, AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_DISPLAY_NAME).
Clean user-facing branding replaces third-party vendor names with custom mini app AI identity."""

import asyncio
import json
import logging
from typing import Optional, List, Dict, Any
import httpx

from bot.config import get_settings

logger = logging.getLogger(__name__)


class AIService:
    """Universal Service for AI-powered interactive chat, text processing, summarization, lesson planning and quiz generation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        display_name: Optional[str] = None
    ) -> None:
        settings = get_settings()
        self.api_key = (api_key or settings.AI_API_KEY or settings.GEMINI_API_KEY or "").strip()
        raw_provider = (provider or settings.AI_PROVIDER or "gemini").lower().strip()
        self.base_url = (base_url or settings.AI_BASE_URL or "").strip()
        self.display_name = (display_name or settings.AI_DISPLAY_NAME or "EduBot AI").strip()

        # Intelligent provider normalization:
        if "openrouter" in raw_provider or "openrouter" in self.base_url.lower():
            self.provider = "openrouter"
            if not self.base_url:
                self.base_url = "https://openrouter.ai/api/v1"
        elif raw_provider in ("openai", "custom", "ai") or (self.base_url and "gemini" not in self.base_url):
            self.provider = "openai"
        elif raw_provider == "deepseek" or "deepseek" in self.base_url.lower():
            self.provider = "deepseek"
            if not self.base_url:
                self.base_url = "https://api.deepseek.com/v1"
        else:
            self.provider = "gemini"

        # Resolve model name
        explicit_model = (model or settings.AI_MODEL or "").strip()
        if explicit_model:
            self.model_name = explicit_model
        elif self.provider in ("openai", "custom", "openrouter"):
            self.model_name = "gpt-4o-mini"
        elif self.provider == "deepseek":
            self.model_name = "deepseek-chat"
        else:
            self.model_name = "gemini-2.0-flash"

        # Resolve base URL fallback
        if not self.base_url:
            if self.provider == "deepseek":
                self.base_url = "https://api.deepseek.com/v1"
            elif self.provider in ("openai", "custom"):
                self.base_url = "https://api.openai.com/v1"

        # Initialize Gemini client if selected
        self.gemini_model = None
        if self.provider == "gemini" and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.gemini_model = genai.GenerativeModel(
                    self.model_name,
                    generation_config={"max_output_tokens": 4096}
                )
                logger.info(f"AIService: Gemini engine initialized (model={self.model_name})")
            except Exception as e:
                logger.error(f"Failed to configure Gemini engine: {e}")
        else:
            logger.info(f"AIService: REST engine initialized (provider={self.provider}, model={self.model_name}, endpoint={self.base_url or 'default'})")

    @property
    def is_configured(self) -> bool:
        """Returns True if an API key is configured."""
        return bool(self.api_key)

    async def _generate(self, prompt: str) -> str:
        """Execute text generation through configured AI provider."""
        return await self.generate_chat([{"role": "user", "content": prompt[:15000]}])

    async def generate_chat(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None) -> str:
        """
        Interactive multi-turn conversation generation (like ChatGPT / Gemini).
        Accepts list of {'role': 'user'|'assistant'|'system', 'content': str}.
        """
        if not self.api_key:
            raise RuntimeError(
                f"{self.display_name} API kaliti sozlanmagan. Iltimos, server sozlamalarini tekshiring."
            )

        default_sys = (
            f"Sen {self.display_name} — o'qituvchilar, talabalar, o'quvchilar va barcha foydalanuvchilar uchun "
            f"yuksak zakovatli, nihoyatda bilimdon, xushmuomala va do'stona virtual sun'iy intellekt yordamchisisan. "
            f"Foydalanuvchi bilan xuddi ChatGPT yoki Gemini kabi samimiy va erkin chat rejimida suhbatlash. "
            f"Har qanday mavzuda — ta'lim, fan, texnologiya, kundalik savollar, maslahatlar, kod yozish yoki shunchaki suhbatlashishda "
            f"o'zbek tilida (yoki foydalanuvchi qaysi tilda yozsa o'sha tilda) aniq, tushunarli, chiroyli va qiziqarli javob ber."
        )
        effective_sys = system_prompt or default_sys

        # 1. Gemini Native Flow
        if self.provider == "gemini":
            if not self.gemini_model:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=self.api_key)
                    self.gemini_model = genai.GenerativeModel(
                        self.model_name,
                        generation_config={"max_output_tokens": 4096}
                    )
                except Exception as ce:
                    logger.error(f"Gemini config error: {ce}")
                    raise RuntimeError("AI xizmatini ishga tushirib bo'lmadi.")

            # Format conversation history for Gemini
            gemini_contents = []
            for m in messages:
                role = "user" if m.get("role") in ("user", "system") else "model"
                gemini_contents.append({"role": role, "parts": [m.get("content", "")[:15000]]})
            
            # Prepend system instruction if possible
            if effective_sys and gemini_contents:
                gemini_contents[0]["parts"].insert(0, f"[Yo'riqnoma: {effective_sys}]\n\n")

            # Retry with exponential backoff on 429/rate-limit
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await self.gemini_model.generate_content_async(gemini_contents)
                    return response.text
                except Exception as e:
                    err_str = str(e).lower()
                    # If 401 or Invalid API key -> fail immediately, do not retry
                    if "401" in err_str or "unauthenticated" in err_str or "invalid api key" in err_str or "api_key_invalid" in err_str:
                        logger.error(f"Gemini auth error: {e}")
                        raise RuntimeError("AI autentifikatsiya xatosi: API kalit yaroqsiz.")
                    # If 429 (ResourceExhausted / Rate limit) -> retry with backoff
                    if ("429" in err_str or "resourceexhausted" in err_str or "quota" in err_str) and attempt < max_retries - 1:
                        backoff = (2 ** attempt) * 1.5
                        logger.warning(f"Gemini rate limited (429), retrying in {backoff}s (attempt {attempt + 1}/{max_retries})...")
                        await asyncio.sleep(backoff)
                        continue
                    # If timeout -> raise friendly timeout error
                    if "timeout" in err_str or "deadline" in err_str:
                        logger.error(f"Gemini timeout error: {e}")
                        raise RuntimeError("AI xizmati javob berish vaqti tugadi (timeout). Iltimos, qayta urinib ko'ring.")
                    
                    logger.error(f"Gemini API error on attempt {attempt + 1}: {e}")
                    if self.base_url:
                        logger.info("Attempting OpenAI-compatible fallback...")
                        return await self._chat_openai_compatible(messages, effective_sys)
                    raise RuntimeError("AI xizmati vaqtincha javob bermayapti. Iltimos, birozdan so'ng qayta urinib ko'ring.")

        # 2. OpenAI / OpenRouter / DeepSeek / Custom Endpoint Flow
        return await self._chat_openai_compatible(messages, effective_sys)

    async def _chat_openai_compatible(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        """Send chat messages to an OpenAI-compatible REST endpoint with retry and backoff."""
        base = (self.base_url or "https://api.openai.com/v1").rstrip("/")
        url = f"{base}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        if "openrouter" in base:
            headers["HTTP-Referer"] = "https://ayamuchun.onrender.com"
            headers["X-Title"] = self.display_name

        chat_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            r = m.get("role", "user")
            c = (m.get("content", "") or "").strip()
            if c:
                chat_messages.append({"role": r, "content": c[:15000]})

        payload = {
            "model": self.model_name,
            "messages": chat_messages,
            "temperature": 0.7,
            "max_tokens": 4096
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        choices = data.get("choices", [])
                        if choices and "message" in choices[0]:
                            return choices[0]["message"].get("content", "").strip()
                        return ""
                    elif res.status_code == 401:
                        logger.error(f"OpenAI-compatible 401 Unauthorized: {res.text}")
                        raise RuntimeError("AI autentifikatsiya xatosi: API kalit yaroqsiz.")
                    elif res.status_code == 429 and attempt < max_retries - 1:
                        backoff = (2 ** attempt) * 1.5
                        logger.warning(f"OpenAI-compatible 429 Rate Limit, retrying in {backoff}s...")
                        await asyncio.sleep(backoff)
                        continue
                    else:
                        logger.error(f"OpenAI-compatible error ({res.status_code}): {res.text}")
                        raise RuntimeError(f"AI xizmati xatolik qaytardi ({res.status_code}).")
            except httpx.TimeoutException:
                logger.error("OpenAI-compatible timeout")
                raise RuntimeError("AI xizmati javob berish vaqti tugadi (timeout).")
            except RuntimeError:
                raise
            except Exception as e:
                logger.error(f"OpenAI-compatible chat error: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.5)
                    continue
                raise RuntimeError("AI xizmatiga ulanishda xatolik yuz berdi.")

        return ""

    # ── Convenience helper methods ─────────────────────────────────────

    async def summarize_text(self, text: str, language: str = "uz") -> str:
        """Summarize the given text with input limit."""
        lang_map = {"uz": "o'zbek", "ru": "русский", "en": "English"}
        lang = lang_map.get(language, "o'zbek")
        prompt = (
            f"Quyidagi matnni {lang} tilida qisqacha xulosa qilib ber. "
            f"Asosiy g'oyalarni ajratib ko'rsat.\n\n"
            f"Matn:\n{text[:15000]}"
        )
        return await self._generate(prompt)

    async def generate_quiz(
        self,
        text: str,
        num_questions: int = 10,
        quiz_type: str = "multiple",
        language: str = "uz",
    ) -> list[dict]:
        """Generate quiz questions from text and validate structure."""
        lang_map = {"uz": "o'zbek", "ru": "русский", "en": "English"}
        lang = lang_map.get(language, "o'zbek")

        type_instruction = {
            "multiple": "Har bir savol uchun 4 ta variant (A, B, C, D) bo'lsin.",
            "open": "Savollar ochiq bo'lsin, javob matn shaklida.",
            "mixed": "Ba'zi savollar testli (4 variant), ba'zilari ochiq bo'lsin.",
        }
        qtype = type_instruction.get(quiz_type, type_instruction["multiple"])

        prompt = (
            f"Quyidagi matn asosida {num_questions} ta savol yarat.\n"
            f"{qtype}\n"
            f"Til: {lang}\n\n"
            f"Javobni quyidagi JSON formatda ber (faqat JSON massiv, boshqa hech qanday so'zsiz):\n"
            f'[\n'
            f'  {{\n'
            f'    "question": "Savol matni",\n'
            f'    "options": ["A variant", "B variant", "C variant", "D variant"],\n'
            f'    "correct_answer": "To\'g\'ri javob",\n'
            f'    "explanation": "Tushuntirish"\n'
            f'  }}\n'
            f']\n\n'
            f"Matn:\n{text[:15000]}"
        )
        response = await self._generate(prompt)

        try:
            text_clean = response.strip()
            if text_clean.startswith("```"):
                lines = text_clean.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text_clean = "\n".join(lines).strip()
            parsed = json.loads(text_clean)
            if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict) and "question" in parsed[0]:
                return parsed
            raise ValueError("JSON tuzilmasi test formatiga mos kelmadi")
        except Exception as e:
            logger.warning(f"Failed to parse valid quiz JSON: {e}, raw response: {response[:200]}")
            raise RuntimeError("AI test savollarini to'g'ri shakllantira olmadi. Iltimos, qayta urinib ko'ring.")

    async def translate_text(self, text: str, target_lang: Optional[str] = None) -> str:
        """Translate text with auto-detection or to specified target language."""
        clean_text = text[:15000]
        # If target_lang is not specified or set to auto
        if not target_lang or target_lang in ("auto", ""):
            prompt = (
                "Quyidagi matnni tahlil qil va uning tilini aniqlab tarjima qil:\n"
                "- Agar matn o'zbek tilida bo'lsa, uni Ruscha va Inglizcha variantlarini alohida bo'limlar bilan ber.\n"
                "- Agar matn rus yoki ingliz yoki boshqa tilda bo'lsa, uni O'zbek tiliga mukammal pedagogik tarjima qilib ber.\n\n"
                f"Matn:\n{clean_text}"
            )
        else:
            lang_map = {"uz": "o'zbek", "ru": "русский", "en": "English"}
            lang = lang_map.get(target_lang, target_lang)
            prompt = (
                f"Quyidagi matnni {lang} tiliga professional darajada tarjima qil. "
                f"Faqat tarjimani yoz, boshqa hech qanday ortiqcha gap qo'shma.\n\n"
                f"Matn:\n{clean_text}"
            )
        return await self._generate(prompt)


    async def check_grammar(self, text: str) -> str:
        """Check grammar and suggest corrections."""
        prompt = (
            "Quyidagi matndagi grammatik, imlo va uslubiy xatolarni top va to'g'rilangan variantini ber. "
            "Har bir xatoni aniq ko'rsat va tushuntir.\n\n"
            f"Matn:\n{text[:15000]}"
        )
        return await self._generate(prompt)

    async def explain_topic(self, topic: str, language: str = "uz") -> str:
        """Explain a topic in simple terms."""
        lang_map = {"uz": "o'zbek", "ru": "русский", "en": "English"}
        lang = lang_map.get(language, "o'zbek")
        prompt = (
            f"'{topic[:5000]}' mavzusini {lang} tilida sodda va tushunarli qilib tushuntir. "
            f"Mavzuni quyidagi tuzilmada ber:\n"
            f"1. Qisqa ta'rif\n"
            f"2. Asosiy tushunchalar\n"
            f"3. Misollar\n"
            f"4. Xulosa"
        )
        return await self._generate(prompt)

    async def generate_lesson_plan(
        self,
        subject: str,
        topic: str,
        duration: str = "45 daqiqa",
        language: str = "uz",
    ) -> str:
        """Generate a complete pedagogical lesson plan for a given subject and topic."""
        lang_map = {"uz": "o'zbek", "ru": "русский", "en": "English"}
        lang = lang_map.get(language, "o'zbek")
        prompt = (
            f"Quyidagi ma'lumotlar asosida zamonaviy dars ishlanmasi (konspekt) tuz.\n"
            f"Fan: {subject[:200]}\n"
            f"Mavzu: {topic[:2000]}\n"
            f"Davomiyligi: {duration}\n"
            f"Til: {lang}\n\n"
            f"Dars rejasi quyidagilarni to'liq o'z ichiga olsin:\n"
            f"1. Dars maqsadlari (Ta'limiy, Tarbiyaviy, Rivojlantiruvchi)\n"
            f"2. Dars jihozi va kerakli materiallar\n"
            f"3. Dars bosqichlari (vaqt taqsimoti bilan)\n"
            f"4. Uyga vazifa\n"
            f"5. O'qituvchi uchun metodik tavsiyalar"
        )
        return await self._generate(prompt)

    async def improve_text(self, text: str, language: str = "uz") -> str:
        """Improve and rewrite the text to be more professional."""
        prompt = (
            "Quyidagi matnni yaxshila va rasmiy, professional uslubda qayta yoz. "
            "Avval yaxshilangan matnni ber, keyin nimalar o'zgartirilganini qisqacha ko'rsat.\n\n"
            f"Matn:\n{text[:15000]}"
        )
        return await self._generate(prompt)

    async def extract_key_points(self, text: str, language: str = "uz") -> str:
        """Extract key points from the text."""
        prompt = (
            "Quyidagi matndan eng muhim asosiy fikrlarni ajratib ber. "
            "Har bir fikrni alohida punkt sifatida ko'rsat.\n\n"
            f"Matn:\n{text[:15000]}"
        )
        return await self._generate(prompt)


    async def analyze_document(self, text: str, language: str = "uz") -> str:
        """Analyze a document and provide comprehensive pedagogical review."""
        prompt = (
            "Quyidagi hujjatni chuqur tahlil qil va xulosalarni ber:\n\n"
            f"Hujjat matni:\n{text[:15000]}"
        )
        return await self._generate(prompt)


# Helper singleton factory
_ai_service_instance: Optional[AIService] = None

def get_ai_service() -> AIService:
    """Returns singleton AIService instance configured from current settings."""
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance
