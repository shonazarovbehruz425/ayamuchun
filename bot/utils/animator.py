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
        interval: float = 1.0
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
        interval: float = 1.0
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

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.interval)
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

                await self.message.edit_text(content, parse_mode="HTML")
                tick += 1
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def finish(self, final_text: str, reply_markup=None, update_message=None):
        """
        Animatsiyani to'xtatib, status xabarini to'g'ridan-to'g'ri yakuniy javobga aylantirish.
        Hech qanday o'chirish/qaytadan yuborish chalg'itishlarisiz ravon o'tadi.
        """
        await self.stop()

        if len(final_text) <= 4000:
            try:
                await self.message.edit_text(
                    final_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                return
            except Exception as e:
                logger.debug(f"edit_text failed, falling back: {e}")
                try:
                    await self.message.delete()
                except Exception:
                    pass
                if update_message:
                    await update_message.reply_text(
                        final_text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
        else:
            chunks = [final_text[i:i + 3800] for i in range(0, len(final_text), 3800)]
            first_edited = False
            try:
                await self.message.edit_text(
                    chunks[0],
                    reply_markup=reply_markup if len(chunks) == 1 else None,
                    parse_mode="HTML"
                )
                first_edited = True
            except Exception:
                pass

            start_idx = 1 if first_edited else 0
            if update_message:
                for i in range(start_idx, len(chunks)):
                    chunk = chunks[i]
                    is_last = (i == len(chunks) - 1)
                    try:
                        await update_message.reply_text(
                            chunk,
                            reply_markup=reply_markup if is_last else None,
                            parse_mode="HTML"
                        )
                    except Exception:
                        await update_message.reply_text(
                            chunk,
                            reply_markup=reply_markup if is_last else None
                        )
