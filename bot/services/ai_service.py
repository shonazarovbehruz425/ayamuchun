"""AI Service — Universal multi-provider AI engine.
Supports Google Gemini, OpenAI, DeepSeek, OpenRouter, Groq, Claude, Ollama, and any OpenAI-compatible custom endpoint.
Configuration is fully managed via server environment variables (AI_PROVIDER, AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_DISPLAY_NAME).
Clean user-facing branding replaces third-party vendor names with custom mini app AI identity."""

import asyncio
import json
import logging
import os
import base64
import mimetypes
from typing import Optional, List, Dict, Any
import httpx

from bot.config import get_settings

logger = logging.getLogger(__name__)


class AIService:
    """Universal Service for AI-powered interactive chat, text processing, summarization, lesson planning and quiz generation."""

    @staticmethod
    def normalize_base_url(raw_url: str) -> str:
        """
        AI Base URL ni tozalab, standart base_url (/v1 prefiksli, chat/completions siz) ko'rinishiga keltiradi.
        Quyidagi barcha variantlarni qabul qiladi:
          - https://api.b.ai/v1/chat/completions -> https://api.b.ai/v1
          - https://api.b.ai/v1                 -> https://api.b.ai/v1
          - https://api.b.ai                    -> https://api.b.ai/v1
          - https://api.b.ai/chat/completions   -> https://api.b.ai
        """
        if not raw_url:
            return ""
        clean = raw_url.strip().strip("'\"").rstrip("/")
        if clean.endswith("/chat/completions"):
            clean = clean[:-len("/chat/completions")].rstrip("/")
            return clean
        if clean.endswith("/v1") or clean.endswith("/v2") or clean.endswith("/v3"):
            return clean
        if "://" in clean:
            return f"{clean}/v1"
        return clean

    @staticmethod
    def resolve_chat_url(raw_url: str) -> str:
        """
        AI chat completions endpoint URL sini aniqlaydi.
        Moslashuvchan ravishda barcha formatlarni qo'llab-quvvatlaydi:
          - https://api.b.ai/v1/chat/completions -> https://api.b.ai/v1/chat/completions
          - https://api.b.ai/v1                 -> https://api.b.ai/v1/chat/completions
          - https://api.b.ai                    -> https://api.b.ai/v1/chat/completions
          - https://api.b.ai/chat/completions   -> https://api.b.ai/chat/completions
        """
        if not raw_url:
            return "https://api.openai.com/v1/chat/completions"
        clean = raw_url.strip().strip("'\"").rstrip("/")
        if clean.endswith("/chat/completions"):
            return clean
        if clean.endswith("/v1") or clean.endswith("/v2") or clean.endswith("/v3"):
            return f"{clean}/chat/completions"
        return f"{clean}/v1/chat/completions"

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
        raw_base = (base_url or settings.AI_BASE_URL or "").strip().strip("'\"")
        self.raw_base_url = raw_base
        self.base_url = self.normalize_base_url(raw_base) if raw_base else ""
        self.display_name = (display_name or settings.AI_DISPLAY_NAME or "EduBot AI").strip()
        explicit_model = (model or settings.AI_MODEL or "").strip()

        # Check storage/ai_key.json if api_key not set via env
        if not self.api_key:
            try:
                import os, json
                key_file = os.path.join(settings.STORAGE_PATH, "ai_key.json")
                if os.path.exists(key_file):
                    with open(key_file, "r", encoding="utf-8") as f:
                        saved_cfg = json.load(f)
                        self.api_key = saved_cfg.get("api_key", "").strip()
                        if saved_cfg.get("provider"):
                            raw_provider = saved_cfg.get("provider")
                        if saved_cfg.get("model"):
                            explicit_model = saved_cfg.get("model")
                        if saved_cfg.get("base_url"):
                            raw_saved_base = saved_cfg.get("base_url").strip().strip("'\"")
                            self.raw_base_url = raw_saved_base
                            self.base_url = self.normalize_base_url(raw_saved_base)
            except Exception as fe:
                logger.debug(f"Could not load saved ai_key.json: {fe}")

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

        self.last_token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

    def update_config(self, api_key: str, provider: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None) -> None:
        """Update API credentials at runtime and persist to storage/ai_key.json."""
        self.api_key = api_key.strip()
        if provider:
            self.provider = provider.strip().lower()
        if model:
            self.model_name = model.strip()
        if base_url:
            raw_base = base_url.strip().strip("'\"")
            self.raw_base_url = raw_base
            self.base_url = self.normalize_base_url(raw_base)

        # Re-initialize Gemini if applicable
        self.gemini_model = None
        if self.provider == "gemini" and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.gemini_model = genai.GenerativeModel(
                    self.model_name,
                    generation_config={"max_output_tokens": 4096}
                )
                logger.info(f"AIService: reconfigured Gemini engine (model={self.model_name})")
            except Exception as e:
                logger.error(f"Failed to reconfigure Gemini engine: {e}")

        # Persist to storage/ai_key.json
        try:
            import os, json
            settings = get_settings()
            os.makedirs(settings.STORAGE_PATH, exist_ok=True)
            key_file = os.path.join(settings.STORAGE_PATH, "ai_key.json")
            with open(key_file, "w", encoding="utf-8") as f:
                json.dump({
                    "api_key": self.api_key,
                    "provider": self.provider,
                    "model": self.model_name,
                    "base_url": self.base_url
                }, f)
        except Exception as se:
            logger.warning(f"Could not persist ai_key.json: {se}")

    @property
    def is_configured(self) -> bool:
        """Returns True if an API key is configured."""
        return bool(self.api_key)

    async def _generate(self, prompt: str) -> str:
        """Execute text generation through configured AI provider."""
        return await self.generate_chat([{"role": "user", "content": prompt[:15000]}])

    async def generate_response(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        system_instruction: Optional[str] = None,
        system_prompt: Optional[str] = None,
        image_paths: Optional[List[str]] = None
    ) -> str:
        """
        Universal response generator method (supports multi-turn messages, single prompt, and images).
        """
        sys = system_instruction or system_prompt
        if messages:
            return await self.generate_chat(messages, system_prompt=sys, image_paths=image_paths)
        if prompt:
            return await self.generate_chat([{"role": "user", "content": prompt[:15000]}], system_prompt=sys, image_paths=image_paths)
        return await self.generate_chat([{"role": "user", "content": "Salom"}], system_prompt=sys, image_paths=image_paths)

    async def generate_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        image_paths: Optional[List[str]] = None
    ) -> str:
        """
        Interactive multi-turn conversation generation (like ChatGPT / Gemini).
        Accepts list of {'role': 'user'|'assistant'|'system', 'content': str}
        and optional image_paths for multimodal visual analysis.
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

        # Prepare PIL images for multimodal support if paths are provided
        valid_image_paths = []
        if image_paths:
            for p in image_paths:
                if p and os.path.exists(p):
                    valid_image_paths.append(p)

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

            # Format conversation history for Gemini:
            raw_turns = []
            for m in messages:
                role = "user" if m.get("role") in ("user", "system") else "model"
                content = (m.get("content") or "").strip()[:15000]
                if not content:
                    continue
                if raw_turns and raw_turns[-1]["role"] == role:
                    raw_turns[-1]["parts"][0] += f"\n\n{content}"
                else:
                    raw_turns.append({"role": role, "parts": [content]})

            # Strip leading model turns
            while raw_turns and raw_turns[0]["role"] != "user":
                raw_turns.pop(0)

            if not raw_turns:
                raw_turns = [{"role": "user", "parts": ["Ushbu tasvirni ko'rib chiqib, tahlil qilib bering."] if valid_image_paths else ["Assalomu alaykum"]}]

            # Multimodal: append PIL images to the last user turn parts
            if valid_image_paths:
                try:
                    from PIL import Image
                    for img_p in valid_image_paths:
                        try:
                            im = Image.open(img_p)
                            if im.mode in ("RGBA", "P"):
                                im = im.convert("RGB")
                            # Find last user turn
                            last_user_turn = None
                            for turn in reversed(raw_turns):
                                if turn["role"] == "user":
                                    last_user_turn = turn
                                    break
                            if last_user_turn is not None:
                                last_user_turn["parts"].append(im)
                            else:
                                raw_turns.append({"role": "user", "parts": [im]})
                        except Exception as im_err:
                            logger.warning(f"Could not load image {img_p} for Gemini: {im_err}")
                except Exception as e:
                    logger.warning(f"Failed to process images for Gemini multimodal: {e}")

            gemini_contents = raw_turns

            # Prepend system instruction safely to the first user turn text
            if effective_sys and gemini_contents:
                for idx, part in enumerate(gemini_contents[0]["parts"]):
                    if isinstance(part, str):
                        gemini_contents[0]["parts"][idx] = f"[Yo'riqnoma: {effective_sys}]\n\n" + part
                        break

            # Retry with exponential backoff on 429/rate-limit
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await self.gemini_model.generate_content_async(gemini_contents)
                    # Capture token usage from Gemini usage_metadata
                    try:
                        u_meta = getattr(response, "usage_metadata", None)
                        if u_meta:
                            p_tok = getattr(u_meta, "prompt_token_count", 0) or 0
                            c_tok = getattr(u_meta, "candidates_token_count", 0) or 0
                            t_tok = getattr(u_meta, "total_token_count", 0) or (p_tok + c_tok)
                            self.last_token_usage = {
                                "prompt_tokens": p_tok,
                                "completion_tokens": c_tok,
                                "total_tokens": t_tok
                            }
                        else:
                            self.last_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                    except Exception as meta_e:
                        logger.debug(f"Could not parse Gemini usage_metadata: {meta_e}")
                        self.last_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

                    try:
                        text_result = response.text
                    except Exception:
                        text_result = ""
                        try:
                            if response.candidates and response.candidates[0].content:
                                text_result = "".join(getattr(p, "text", "") for p in response.candidates[0].content.parts)
                        except Exception:
                            pass
                    if not text_result:
                        text_result = "Kechirasiz, javob matnini shakllantirib bo'lmadi. Iltimos, savolingizni boshqacharoq yozing."
                    return text_result
                except Exception as e:
                    err_str = str(e).lower()
                    if "api key not valid" in err_str or "api_key_invalid" in err_str or "401" in err_str or "unauthenticated" in err_str:
                        logger.error(f"Gemini auth error: {e}")
                        raise RuntimeError("AI API kaliti yaroqsiz yoki noto'g'ri kiritilgan. Iltimos, API kalitni tekshiring.")
                    if "403" in err_str or "permission_denied" in err_str or "location" in err_str:
                        logger.error(f"Gemini permission error: {e}")
                        raise RuntimeError("AI xizmatiga ulanish rad etildi (403). API kalit ruxsati yoki hududiy cheklov mavjud.")
                    if ("429" in err_str or "resourceexhausted" in err_str or "quota" in err_str) and attempt < max_retries - 1:
                        backoff = (2 ** attempt) * 1.5
                        logger.warning(f"Gemini rate limited (429), retrying in {backoff}s (attempt {attempt + 1}/{max_retries})...")
                        await asyncio.sleep(backoff)
                        continue
                    if "timeout" in err_str or "deadline" in err_str:
                        logger.error(f"Gemini timeout error: {e}")
                        raise RuntimeError("AI xizmati javob berish vaqti tugadi (timeout). Iltimos, qayta urinib ko'ring.")
                    
                    logger.error(f"Gemini API error on attempt {attempt + 1}: {e}")
                    if self.base_url:
                        logger.info("Attempting OpenAI-compatible fallback...")
                        return await self._chat_openai_compatible(messages, effective_sys, image_paths=valid_image_paths)
                    
                    if "quota" in err_str or "resourceexhausted" in err_str or "429" in err_str:
                        raise RuntimeError("AI so'rovlar limiti (kvota) tugadi. Iltimos, birozdan so'ng urinib ko'ring yoki yangi API kalit kiriting.")
                    
                    raise RuntimeError(f"AI xizmati vaqtincha javob bermayapti ({e}).")

        # 2. OpenAI / OpenRouter / DeepSeek / Custom Endpoint Flow
        return await self._chat_openai_compatible(messages, effective_sys, image_paths=valid_image_paths)

    async def _chat_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        image_paths: Optional[List[str]] = None
    ) -> str:
        """Send chat messages to an OpenAI-compatible REST endpoint with retry, endpoint fallback, backoff, and vision image support."""
        target_base = getattr(self, "raw_base_url", None) or self.base_url or "https://api.openai.com/v1"
        url = self.resolve_chat_url(target_base)
        tried_alt_url = False

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        if "openrouter" in (self.base_url or "").lower() or "openrouter" in url.lower():
            headers["HTTP-Referer"] = "https://ayamuchun.onrender.com"
            headers["X-Title"] = self.display_name

        # Prepare base64 images for OpenAI Vision format if image_paths provided
        image_content_items = []
        if image_paths:
            for img_p in image_paths:
                if img_p and os.path.exists(img_p):
                    try:
                        mime_type, _ = mimetypes.guess_type(img_p)
                        if not mime_type or not mime_type.startswith("image/"):
                            mime_type = "image/jpeg"
                        with open(img_p, "rb") as f_img:
                            b64_data = base64.b64encode(f_img.read()).decode("utf-8")
                        image_content_items.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{b64_data}"
                            }
                        })
                    except Exception as b64_err:
                        logger.warning(f"Could not encode image {img_p} to base64: {b64_err}")

        chat_messages = [{"role": "system", "content": system_prompt}]
        for idx, m in enumerate(messages):
            r = m.get("role", "user")
            c = (m.get("content", "") or "").strip()
            # If this is the last user message and we have images, format as multimodal content list
            is_last_message = (idx == len(messages) - 1)
            if is_last_message and image_content_items and r == "user":
                parts = [{"type": "text", "text": c[:15000] if c else "Ushbu rasm(lar)ni ko'rib chiqib tahlil qiling va savolga javob bering."}]
                parts.extend(image_content_items)
                chat_messages.append({"role": r, "content": parts})
            elif c:
                chat_messages.append({"role": r, "content": c[:15000]})

        # If no user message was added but we have images
        if image_content_items and not any(m.get("role") == "user" for m in chat_messages):
            parts = [{"type": "text", "text": "Ushbu tasvirni to'liq tahlil qilib bering."}]
            parts.extend(image_content_items)
            chat_messages.append({"role": "user", "content": parts})

        payload = {
            "model": self.model_name,
            "messages": chat_messages,
            "temperature": 0.7,
            "max_tokens": 4096
        }

        max_retries = 3
        timeout_config = httpx.Timeout(60.0, connect=10.0)
        logger.info(f"Connecting to OpenAI-compatible endpoint: {url} | Model: {payload['model']}")

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        usage = data.get("usage", {})
                        p_tok = usage.get("prompt_tokens", 0) or 0
                        c_tok = usage.get("completion_tokens", 0) or 0
                        t_tok = usage.get("total_tokens", 0) or (p_tok + c_tok)
                        self.last_token_usage = {
                            "prompt_tokens": p_tok,
                            "completion_tokens": c_tok,
                            "total_tokens": t_tok
                        }
                        choices = data.get("choices", [])
                        if choices and "message" in choices[0]:
                            return choices[0]["message"].get("content", "").strip()
                        return ""
                    elif res.status_code in (400, 404):
                        # 1. OpenRouter model unavailability check
                        if "openrouter" in (self.base_url or "").lower() or "openrouter" in url.lower():
                            err_text_low = res.text.lower()
                            if ("unavailable for free" in err_text_low or "not found" in err_text_low or "does not exist" in err_text_low) and payload["model"] != "nvidia/nemotron-3.5-lightning:free":
                                logger.warning(f"OpenRouter model {payload['model']} is unavailable. Falling back to nvidia/nemotron-3.5-lightning:free...")
                                payload["model"] = "nvidia/nemotron-3.5-lightning:free"
                                self.model_name = "nvidia/nemotron-3.5-lightning:free"
                                continue

                        # 2. Endpoint 404 bo'lsa, moslashuvchan muqobil endpoint sinab ko'rish (/v1/chat/completions <-> /chat/completions)
                        if res.status_code == 404 and not tried_alt_url:
                            tried_alt_url = True
                            if "/v1/chat/completions" in url:
                                alt_url = url.replace("/v1/chat/completions", "/chat/completions")
                                logger.info(f"AI endpoint 404 berdi, muqobil endpoint sinab ko'rilmoqda: {alt_url}")
                                url = alt_url
                                continue
                            elif "/chat/completions" in url and "/v1" not in url:
                                alt_url = url.replace("/chat/completions", "/v1/chat/completions")
                                logger.info(f"AI endpoint 404 berdi, muqobil endpoint sinab ko'rilmoqda: {alt_url}")
                                url = alt_url
                                continue

                        err_msg = ""
                        try:
                            err_msg = res.json().get("error", {}).get("message", "")
                        except Exception:
                            pass
                        err_msg = err_msg or f"Model yoki endpoint topilmadi ({res.status_code})"
                        raise RuntimeError(f"AI model xatosi: {err_msg}")
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
                        err_msg = ""
                        try:
                            err_msg = res.json().get("error", {}).get("message", "")
                        except Exception:
                            pass
                        err_msg = err_msg or f"Xatolik kodi: {res.status_code}"
                        raise RuntimeError(f"AI provayder xatosi: {err_msg}")
            except httpx.ConnectTimeout:
                logger.error(f"OpenAI-compatible connection timeout to {url}")
                raise RuntimeError(f"AI serveriga ulanib bo'lmadi ({url}). Server manzili noto'g'ri yoki ulanish bloklangan.")
            except httpx.ReadTimeout:
                logger.error(f"OpenAI-compatible read timeout from {url}")
                raise RuntimeError(f"AI server ({url}) javob qaytarishda kechikdi (read timeout). Model serveri band bo'lishi mumkin.")
            except httpx.TimeoutException:
                logger.error(f"OpenAI-compatible timeout to {url}")
                raise RuntimeError(f"AI xizmati javob berish vaqti tugadi ({url}).")
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

    async def analyze_image(
        self,
        image_paths: List[str],
        prompt: str = "Ushbu tasvirni to'liq tahlil qilib, mazmunini, undagi barcha matn va tafsilotlarni tushuntirib bering.",
        system_prompt: Optional[str] = None
    ) -> str:
        """Analyze one or more images using Multimodal Vision capabilities."""
        if not image_paths:
            return await self.generate_response(prompt=prompt, system_prompt=system_prompt)
        messages = [{"role": "user", "content": prompt}]
        return await self.generate_chat(
            messages=messages,
            system_prompt=system_prompt,
            image_paths=image_paths
        )



# Helper singleton factory
_ai_service_instance: Optional[AIService] = None

def get_ai_service() -> AIService:
    """Returns singleton AIService instance configured from current settings."""
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance
