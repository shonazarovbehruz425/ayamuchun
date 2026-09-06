"""AI Service — Google Gemini API integration for document analysis and educational tools."""

import json
import logging
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered text processing using Google Gemini."""

    def __init__(self, api_key: str) -> None:
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")
        logger.info("AIService initialized with Gemini 2.0 Flash")

    async def _generate(self, prompt: str) -> str:
        """Send a prompt to Gemini and return the response text."""
        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise RuntimeError(f"AI xizmati vaqtincha ishlamayapti: {e}")

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
            f"Javobni quyidagi JSON formatda ber (faqat JSON, boshqa matn yo'q):\n"
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
            # Try to extract JSON array from response
            text_clean = response.strip()
            if text_clean.startswith("```"):
                # Remove markdown code block markers
                lines = text_clean.split("\n")
                text_clean = "\n".join(lines[1:-1])
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
            f"Quyidagi matnni {lang} tiliga tarjima qil. "
            f"Faqat tarjimani yoz, boshqa izoh qo'shma.\n\n"
            f"Matn:\n{text}"
        )
        return await self._generate(prompt)

    # ── Grammar Check ──────────────────────────────────────────────────

    async def check_grammar(self, text: str) -> str:
        """Check grammar and suggest corrections."""
        prompt = (
            "Quyidagi matndagi grammatik xatolarni top va to'g'rilangan variantini ber. "
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
            f"O'qituvchilarga qulay bo'lishi uchun misollar bilan tushuntir. "
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
        """Generate a lesson plan for a given subject and topic."""
        lang_map = {"uz": "o'zbek", "ru": "русский", "en": "English"}
        lang = lang_map.get(language, "o'zbek")
        prompt = (
            f"Quyidagi ma'lumotlar asosida batafsil dars rejasi tuz.\n"
            f"Fan: {subject}\n"
            f"Mavzu: {topic}\n"
            f"Davomiyligi: {duration}\n"
            f"Til: {lang}\n\n"
            f"Dars rejasi quyidagilarni o'z ichiga olsin:\n"
            f"1. Dars maqsadlari\n"
            f"2. Kerakli materiallar\n"
            f"3. Dars bosqichlari (vaqt taqsimoti bilan)\n"
            f"   - Kirish/motivatsiya\n"
            f"   - Asosiy qism\n"
            f"   - Mustahkamlash\n"
            f"   - Baholash\n"
            f"4. Uy vazifasi\n"
            f"5. Qo'shimcha izohlar"
        )
        return await self._generate(prompt)

    # ── Text Improvement ───────────────────────────────────────────────

    async def improve_text(self, text: str, language: str = "uz") -> str:
        """Improve and rewrite the text to be more professional."""
        prompt = (
            "Quyidagi matnni yaxshila va professional qilib qayta yoz. "
            "Mazmunini o'zgartirma, faqat uslubini yaxshila. "
            "Avval yaxshilangan matnni ber, keyin nimalarni o'zgartirganingni qisqacha tushuntir.\n\n"
            f"Matn:\n{text}"
        )
        return await self._generate(prompt)

    # ── Key Points Extraction ──────────────────────────────────────────

    async def extract_key_points(self, text: str, language: str = "uz") -> str:
        """Extract key points from the text."""
        prompt = (
            "Quyidagi matndan asosiy fikrlarni ajratib ber. "
            "Har bir fikrni alohida nuqta sifatida ko'rsat.\n\n"
            f"Matn:\n{text}"
        )
        return await self._generate(prompt)

    # ── Document Analysis ──────────────────────────────────────────────

    async def analyze_document(self, text: str, language: str = "uz") -> str:
        """Analyze a document and provide comprehensive summary."""
        prompt = (
            "Quyidagi hujjatni tahlil qil va quyidagilarni ber:\n"
            "1. Hujjat haqida umumiy ma'lumot\n"
            "2. Asosiy mavzular\n"
            "3. Muhim fikrlar va xulosalar\n"
            "4. Hujjatning kuchli va zaif tomonlari\n"
            "5. Qisqacha xulosa\n\n"
            f"Hujjat:\n{text[:15000]}"
        )
        return await self._generate(prompt)
