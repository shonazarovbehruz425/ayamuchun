"""AI Service — Universal multi-provider AI engine.
Supports Google Gemini, OpenAI, DeepSeek, Groq, Claude, Ollama, and any OpenAI-compatible custom endpoint.
Configuration is fully managed via server environment variables (AI_PROVIDER, AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_DISPLAY_NAME).
Clean user-facing branding replaces third-party vendor names with custom mini app AI identity."""

import json
import logging
from typing import Optional, List, Dict, Any
import httpx

from bot.config import get_settings

logger = logging.getLogger(__name__)


class AIService:
    """Universal Service for AI-powered text processing, summarization, lesson planning and quiz generation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        display_name: Optional[str] = None
    ) -> None:
        settings = get_settings()
        # Read parameters with priority: explicit arg -> environment config
        self.api_key = (api_key or settings.AI_API_KEY or settings.GEMINI_API_KEY or "").strip()
        self.provider = (provider or settings.AI_PROVIDER or "gemini").lower().strip()
        self.base_url = (base_url or settings.AI_BASE_URL or "").strip()
        self.display_name = (display_name or settings.AI_DISPLAY_NAME or "EduBot AI").strip()

        # Resolve model name
        explicit_model = (model or settings.AI_MODEL or "").strip()
        if explicit_model:
            self.model_name = explicit_model
        elif self.provider in ("openai", "custom"):
            self.model_name = "gpt-4o-mini"
        elif self.provider == "deepseek":
            self.model_name = "deepseek-chat"
        else:
            self.model_name = "gemini-2.0-flash"

        # Resolve base URL for OpenAI-compatible providers
        if not self.base_url:
            if self.provider == "deepseek":
                self.base_url = "https://api.deepseek.com/v1"
            elif self.provider == "openai":
                self.base_url = "https://api.openai.com/v1"

        # Initialize Gemini client if selected and available
        self.gemini_model = None
        if self.provider == "gemini" and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.gemini_model = genai.GenerativeModel(self.model_name)
                logger.info(f"AIService: Gemini engine initialized (model={self.model_name})")
            except Exception as e:
                logger.error(f"Failed to configure Gemini engine: {e}")
        elif self.provider in ("openai", "deepseek", "custom"):
            logger.info(f"AIService: OpenAI-compatible engine initialized (provider={self.provider}, model={self.model_name}, endpoint={self.base_url or 'default'})")
        else:
            if not self.api_key:
                logger.warning("AIService: AI_API_KEY / GEMINI_API_KEY is not configured. AI features will be limited.")

    @property
    def is_configured(self) -> bool:
        """Returns True if an API key is configured."""
        return bool(self.api_key)

    async def _generate(self, prompt: str) -> str:
        """Execute text generation through configured AI provider."""
        if not self.api_key:
            raise RuntimeError(
                f"{self.display_name} API kaliti sozlanmagan. Iltimos, server muhit o'zgaruvchilariga "
                "AI_API_KEY yoki GEMINI_API_KEY kiriting."
            )

        # 1. Gemini Native Flow
        if self.provider == "gemini":
            if not self.gemini_model:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=self.api_key)
                    self.gemini_model = genai.GenerativeModel(self.model_name)
                except Exception as ce:
                    raise RuntimeError(f"{self.display_name} sozlanmadi: {ce}")
            try:
                response = await self.gemini_model.generate_content_async(prompt)
                return response.text
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                # If Gemini fails and custom endpoint or base_url was also provided, try fallback
                if self.base_url:
                    logger.info("Attempting OpenAI-compatible fallback...")
                    return await self._generate_openai_compatible(prompt)
                raise RuntimeError(f"{self.display_name} xizmati vaqtincha javob bermayapti: {e}")

        # 2. OpenAI / DeepSeek / Custom Endpoint Flow
        return await self._generate_openai_compatible(prompt)

    async def _generate_openai_compatible(self, prompt: str) -> str:
        """Send prompt to an OpenAI-compatible REST endpoint (e.g. OpenAI, DeepSeek, Groq, local LLM)."""
        base = self.base_url.rstrip("/")
        if not base:
            base = "https://api.openai.com/v1"
        url = f"{base}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": f"Sen {self.display_name} — o'qituvchilar, pedagoglar va talabalar uchun oliy darajadagi aqlli intellektual yordamchisan. Javoblaringni doimo o'zbek tilida, aniq, tushunarli, pedagogik talablarga mos va chiroyli formatlangan holda taqdim et."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return choices[0]["message"].get("content", "").strip()
                    return ""
                else:
                    err_msg = f"HTTP {res.status_code}: {res.text}"
                    logger.error(f"OpenAI-compatible AI error ({self.provider}): {err_msg}")
                    raise RuntimeError(f"{self.display_name} so'rovi muvaffaqiyatsiz bo'ldi ({res.status_code})")
        except Exception as e:
            logger.error(f"OpenAI-compatible generation error: {e}", exc_info=True)
            raise RuntimeError(f"{self.display_name} xizmatida xatolik: {e}")

    # ── Text Summarization ─────────────────────────────────────────────

    async def summarize_text(self, text: str, language: str = "uz") -> str:
        """Summarize the given text."""
        lang_map = {"uz": "o'zbek", "ru": "русский", "en": "English"}
        lang = lang_map.get(language, "o'zbek")
        prompt = (
            f"Quyidagi matnni {lang} tilida qisqacha xulosa qilib ber. "
            f"Asosiy g'oyalarni ajratib ko'rsat.\n\n"
            f"Matn:\n{text}"
        )
        return await self._generate(prompt)

    # ── Quiz Generation ────────────────────────────────────────────────

    async def generate_quiz(
        self,
        text: str,
        num_questions: int = 10,
        quiz_type: str = "multiple",
        language: str = "uz",
    ) -> list[dict]:
        """Generate quiz questions from text."""
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
            f"Javobni quyidagi JSON formatda ber (faqat JSON massiv, hech qanday boshqa matnsiz):\n"
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

        # Parse JSON from response
        try:
            text_clean = response.strip()
            if text_clean.startswith("```"):
                lines = text_clean.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text_clean = "\n".join(lines).strip()
            return json.loads(text_clean)
        except json.JSONDecodeError:
            logger.warning("Failed to parse quiz JSON, returning raw text")
            return [{"question": response, "options": [], "correct_answer": "", "explanation": ""}]

    # ── Translation ────────────────────────────────────────────────────

    async def translate_text(self, text: str, target_lang: str = "en") -> str:
        """Translate text to the target language."""
        lang_map = {"uz": "o'zbek", "ru": "русский", "en": "English"}
        lang = lang_map.get(target_lang, target_lang)
        prompt = (
            f"Quyidagi matnni {lang} tiliga professional darajada tarjima qil. "
            f"Faqat tarjimani yoz, boshqa hech qanday izoh qo'shma.\n\n"
            f"Matn:\n{text}"
        )
        return await self._generate(prompt)

    # ── Grammar Check ──────────────────────────────────────────────────

    async def check_grammar(self, text: str) -> str:
        """Check grammar and suggest corrections."""
        prompt = (
            "Quyidagi matndagi grammatik, imlo va uslubiy xatolarni top va to'g'rilangan variantini ber. "
            "Har bir xatoni aniq ko'rsat va tushuntir.\n\n"
            f"Matn:\n{text}"
        )
        return await self._generate(prompt)

    # ── Topic Explanation ──────────────────────────────────────────────

    async def explain_topic(self, topic: str, language: str = "uz") -> str:
        """Explain a topic in simple terms."""
        lang_map = {"uz": "o'zbek", "ru": "русский", "en": "English"}
        lang = lang_map.get(language, "o'zbek")
        prompt = (
            f"'{topic}' mavzusini {lang} tilida sodda va tushunarli qilib tushuntir. "
            f"O'qituvchilarga va o'quvchilarga qulay bo'lishi uchun amaliy misollar bilan yorit. "
            f"Mavzuni quyidagi tuzilmada ber:\n"
            f"1. Qisqa ta'rif\n"
            f"2. Asosiy tushunchalar\n"
            f"3. Misollar\n"
            f"4. Xulosa"
        )
        return await self._generate(prompt)

    # ── Lesson Plan Generation ─────────────────────────────────────────

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
            f"Quyidagi ma'lumotlar asosida zamonaviy pedagogik talablarga mos, batafsil dars ishlanmasi (konspekt) tuz.\n"
            f"Fan: {subject}\n"
            f"Mavzu: {topic}\n"
            f"Davomiyligi: {duration}\n"
            f"Til: {lang}\n\n"
            f"Dars rejasi quyidagilarni to'liq o'z ichiga olsin:\n"
            f"1. Dars maqsadlari (Ta'limiy, Tarbiyaviy, Rivojlantiruvchi)\n"
            f"2. Dars jihozi va kerakli materiallar\n"
            f"3. Dars bosqichlari (vaqt taqsimoti bilan):\n"
            f"   - Tashkiliy qism va motivatsiya (5 daqiqa)\n"
            f"   - O'tilgan mavzuni takrorlash (10 daqiqa)\n"
            f"   - Yangi mavzu bayoni va interaktiv usullar (20 daqiqa)\n"
            f"   - Yangi mavzuni mustahkamlash (5 daqiqa)\n"
            f"   - Baholash va dars yakuni (5 daqiqa)\n"
            f"4. Uyga vazifa\n"
            f"5. O'qituvchi uchun metodik tavsiyalar"
        )
        return await self._generate(prompt)

    # ── Text Improvement ───────────────────────────────────────────────

    async def improve_text(self, text: str, language: str = "uz") -> str:
        """Improve and rewrite the text to be more professional."""
        prompt = (
            "Quyidagi matnni yaxshila va rasmiy, professional uslubda qayta yoz. "
            "Mazmunini o'zgartirma, faqat uslubini va ta'sirchanligini oshir. "
            "Avval yaxshilangan matnni ber, keyin nimalar o'zgartirilganini qisqacha ko'rsat.\n\n"
            f"Matn:\n{text}"
        )
        return await self._generate(prompt)

    # ── Key Points Extraction ──────────────────────────────────────────

    async def extract_key_points(self, text: str, language: str = "uz") -> str:
        """Extract key points from the text."""
        prompt = (
            "Quyidagi matndan eng muhim asosiy fikrlarni ajratib ber. "
            "Har bir fikrni alohida punkt sifatida ko'rsat.\n\n"
            f"Matn:\n{text}"
        )
        return await self._generate(prompt)

    # ── Document Analysis ──────────────────────────────────────────────

    async def analyze_document(self, text: str, language: str = "uz") -> str:
        """Analyze a document and provide comprehensive pedagogical review."""
        prompt = (
            "Quyidagi hujjatni chuqur tahlil qil va quyidagilarni taqdim et:\n"
            "1. Hujjat haqida umumiy tushuncha\n"
            "2. Asosiy mavzular va bo'limlar\n"
            "3. Muhim xulosalar va faktlar\n"
            "4. Kuchli va takomillashtirish lozim bo'lgan jihatlar\n"
            "5. Umumiy xulosa\n\n"
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
