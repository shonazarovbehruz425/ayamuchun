import asyncio
import time
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# Real holat bosqichlari (soxta foizlarsiz, real soniyalar bilan)
DEFAULT_AI_STAGES: List[Tuple[str, str]] = [
    ("⚡️", "AI serveriga ulanilmoqda..."),
    ("🧠", "Savol o'rganilmoqda va rejalashtirilmoqda..."),
    ("🔍", "Kerakli ma'lumotlar tahlil qilinmoqda..."),
    ("💡", "Javob matni tuzilmoqda..."),
    ("✨", "Matn sayqallanmoqda..."),
    ("🚀", "Javob yakunlanmoqda...")
]

VISION_STAGES: List[Tuple[str, str]] = [
    ("👁", "Surat piksellari o'qilmoqda..."),
    ("🔍", "Matn va obyektlar tahlil qilinmoqda..."),
    ("⚡️", "Tafsilotlar o'rganilmoqda..."),
    ("✨", "Javob shakllantirilmoqda...")
]

class TelegramAiLoadingAnimation:
    """
    Telegram chatda yuklanish vaqtida soxta foizlar o'rniga
    real soniyalar hisoblagichi va jonli faollik indikatorini ko'rsatuvchi xabar.
    """

    def __init__(
        self,
        message,
        bot,
        chat_id: int,
        title: str = "EduBot AI",
        stages: Optional[List[Tuple[str, str]]] = None,
        interval: float = 2.5
    ):
        self.message = message
        self.bot = bot
        self.chat_id = chat_id
        self.title = title
        self.stages = stages or DEFAULT_AI_STAGES
        self.interval = interval
        self._start_time = time.time()
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    @classmethod
    async def create_and_start(
        cls,
        reply_target,
        bot,
        chat_id: int,
        title: str = "EduBot AI",
        initial_desc: str = "AI serveriga ulanilmoqda...",
        stages: Optional[List[Tuple[str, str]]] = None,
        interval: float = 2.5
    ):
        """
        Dastlabki xabarni darhol jo'natib, animatsiyani avtomatik ishga tushiradi.
        """
        initial_text = (
            f"⚡️ <b>{title}</b>\n"
            f"⏱ <b>0 soniya</b> | <i>{initial_desc}</i>\n"
            f"<code>[▰▱▱▱▱▱▱▱]</code>"
        )
        msg = await reply_target.reply_text(initial_text, parse_mode="HTML")
        animator = cls(
            message=msg,
            bot=bot,
            chat_id=chat_id,
            title=title,
            stages=stages,
            interval=interval
        )
        animator.start()
        return animator

    def start(self) -> "TelegramAiLoadingAnimation":
        self._task = asyncio.create_task(self._run())
        return self

    async def stop(self):
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    async def _run(self):
        wave_frames = [
            "[▰▱▱▱▱▱▱▱]",
            "[▱▰▱▱▱▱▱▱]",
            "[▱▱▰▱▱▱▱▱]",
            "[▱▱▱▰▱▱▱▱]",
            "[▱▱▱▱▰▱▱▱]",
            "[▱▱▱▱▱▰▱▱]",
            "[▱▱▱▱▱▱▰▱]",
            "[▱▱▱▱▱▱▱▰]",
            "[▱▱▱▱▱▱▰▱]",
            "[▱▱▱▱▱▰▱▱]",
            "[▱▱▱▱▰▱▱▱]",
            "[▱▱▱▰▱▱▱▱]",
            "[▱▱▰▱▱▱▱▱]",
            "[▱▰▱▱▱▱▱▱]",
        ]
        tick = 0
        last_edit_time = 0.0

        while not self._stop_event.is_set():
            try:
                elapsed = int(time.time() - self._start_time)
                # Telegram flood control / rate limit dan himoya:
                # 0-20s: 2.5s oralig'i; 20-45s: 3.2s; 45s+: 4.0s oralig'i
                if elapsed < 20:
                    current_interval = max(self.interval, 2.5)
                elif elapsed < 45:
                    current_interval = 3.2
                else:
                    current_interval = 4.0

                await asyncio.sleep(current_interval)
                if self._stop_event.is_set():
                    break

                elapsed = int(time.time() - self._start_time)
                wave = wave_frames[tick % len(wave_frames)]

                # Vaqtga qarab real holatni aks ettirish
                if elapsed < 3:
                    icon, desc = self.stages[0]
                elif elapsed < 7:
                    icon, desc = self.stages[min(1, len(self.stages) - 1)]
                elif elapsed < 15:
                    icon, desc = self.stages[min(2, len(self.stages) - 1)]
                elif elapsed < 25:
                    icon, desc = self.stages[min(3, len(self.stages) - 1)]
                elif elapsed < 45:
                    icon, desc = ("⏳", "Katta hajmdagi javob tuzilmoqda, kutilmoqda...")
                elif elapsed < 75:
                    icon, desc = ("⚡️", "Server hali hisoblamoqda, jarayon davom etmoqda...")
                else:
                    icon, desc = ("⏱", "Javob juda katta yoki server band, kutilmoqda...")

                content = (
                    f"⚡️ <b>{self.title}</b>\n"
                    f"⏱ <b>{elapsed} soniya</b> | {icon} <i>{desc}</i>\n"
                    f"<code>{wave}</code>"
                )

                try:
                    await self.bot.send_chat_action(chat_id=self.chat_id, action="typing")
                except Exception:
                    pass

                # Telegram edit_text minimal 2.0s cheklovi
                now = time.time()
                if now - last_edit_time < 2.0:
                    await asyncio.sleep(2.0 - (now - last_edit_time))

                await self.message.edit_text(content, parse_mode="HTML")
                last_edit_time = time.time()
                tick += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                err_text = str(e).lower()
                # Telegram flood control / RetryAfter xatosi kelsa, belgilangan soniya kutish
                if "retry_after" in err_text or "flood" in err_text:
                    try:
                        retry_sec = getattr(e, "retry_after", 5) or 5
                    except Exception:
                        retry_sec = 5
                    logger.warning(f"Telegram animator flood control: backing off for {retry_sec}s")
                    await asyncio.sleep(float(retry_sec) + 1.0)
                elif "not modified" in err_text:
                    pass
                else:
                    pass

    async def finish(self, final_text: str, reply_markup=None, update_message=None):
        """
        Animatsiyani to'xtatib, status xabarini to'g'ridan-to'g'ri yakuniy javobga aylantirish.
        HTML xatoliklarida yoki rate limitda to'xtab qolmasdan ishonchli ravishda foydalanuvchiga yetkazadi.
        """
        await self.stop()

        if not final_text:
            final_text = "Kechirasiz, javob matni bo'sh bo'ldi. Iltimos, qayta urinib ko'ring."

        async def _safe_deliver(text: str, is_first: bool = True, markup=None) -> bool:
            # 1-bosqich: mavjud loading xabarini edit qilish (avval HTML, keyin Plain Text)
            if is_first and self.message:
                try:
                    await self.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
                    return True
                except Exception as e1:
                    e1_str = str(e1).lower()
                    if any(k in e1_str for k in ["can't parse", "entity", "bad request", "tag"]):
                        # HTML parsing xatoligi (masalan AI matnida unescaped belgilar bor bo'lsa)
                        try:
                            await self.message.edit_text(text, reply_markup=markup, parse_mode=None)
                            return True
                        except Exception:
                            pass
                    logger.debug(f"edit_text failed ({e1}), falling back to new message...")

            # 2-bosqich: yangi xabar yuborish orqali yetkazish (update_message yoki bot.send_message)
            target = update_message or self.message
            if target and hasattr(target, "reply_text"):
                try:
                    await target.reply_text(text, reply_markup=markup, parse_mode="HTML")
                    # Eski status xabarini tozalashga urinish
                    if is_first and self.message:
                        try:
                            await self.message.delete()
                        except Exception:
                            pass
                    return True
                except Exception as e2:
                    e2_str = str(e2).lower()
                    if any(k in e2_str for k in ["can't parse", "entity", "bad request", "tag"]):
                        try:
                            await target.reply_text(text, reply_markup=markup, parse_mode=None)
                            if is_first and self.message:
                                try:
                                    await self.message.delete()
                                except Exception:
                                    pass
                            return True
                        except Exception:
                            pass

            # 3-bosqich: to'g'ridan-to'g'ri bot.send_message
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=text, reply_markup=markup, parse_mode="HTML")
                if is_first and self.message:
                    try:
                        await self.message.delete()
                    except Exception:
                        pass
                return True
            except Exception:
                try:
                    await self.bot.send_message(chat_id=self.chat_id, text=text, reply_markup=markup, parse_mode=None)
                    if is_first and self.message:
                        try:
                            await self.message.delete()
                        except Exception:
                            pass
                    return True
                except Exception as bot_err:
                    logger.error(f"Failed all delivery attempts: {bot_err}")
                    return False

        if len(final_text) <= 4000:
            await _safe_deliver(final_text, is_first=True, markup=reply_markup)
        else:
            chunks = [final_text[i:i + 3800] for i in range(0, len(final_text), 3800)]
            first_done = await _safe_deliver(chunks[0], is_first=True, markup=reply_markup if len(chunks) == 1 else None)
            start_idx = 1 if first_done else 0
            for i in range(start_idx, len(chunks)):
                chunk = chunks[i]
                is_last = (i == len(chunks) - 1)
                await _safe_deliver(chunk, is_first=False, markup=reply_markup if is_last else None)
