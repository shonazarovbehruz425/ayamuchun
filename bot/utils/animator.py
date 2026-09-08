import asyncio
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

DEFAULT_AI_STAGES: List[Tuple[str, str, str, str]] = [
    ("🧠", "Savolingiz tahlil qilinmoqda...", "▰▰▱▱▱▱▱▱▱▱", "20%"),
    ("🔍", "Kerakli ma'lumotlar saralanmoqda...", "▰▰▰▰▱▱▱▱▱▱", "45%"),
    ("⚡️", "Eng to'g'ri yechim shakllantirilmoqda...", "▰▰▰▰▰▰▱▱▱▱", "70%"),
    ("💡", "Javob matni tuzilmoqda...", "▰▰▰▰▰▰▰▰▱▱", "85%"),
    ("✨", "Matn sayqallanmoqda...", "▰▰▰▰▰▰▰▰▰▱", "95%"),
    ("🚀", "Deyarli tayyor...", "▰▰▰▰▰▰▰▰▰▰", "99%"),
]

VISION_STAGES: List[Tuple[str, str, str, str]] = [
    ("👁", "Surat piksellari o'qilmoqda...", "▰▰▱▱▱▱▱▱▱▱", "25%"),
    ("🔍", "Matn va obyektlar ajratilmoqda...", "▰▰▰▰▱▱▱▱▱▱", "50%"),
    ("⚡️", "Tafsilotlar tahlil qilinmoqda...", "▰▰▰▰▰▰▱▱▱▱", "75%"),
    ("✨", "Natija shakllantirilmoqda...", "▰▰▰▰▰▰▰▰▰▰", "98%"),
]

class TelegramAiLoadingAnimation:
    """
    Telegram chatda yuklanish vaqtida 'VAU' effekt beruvchi
    jonli animatsiyali progress xabari.
    """

    def __init__(
        self,
        message,
        bot,
        chat_id: int,
        title: str = "EduBot AI",
        stages: Optional[List[Tuple[str, str, str, str]]] = None,
        interval: float = 0.95
    ):
        self.message = message
        self.bot = bot
        self.chat_id = chat_id
        self.title = title
        self.stages = stages or DEFAULT_AI_STAGES
        self.interval = interval
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    @classmethod
    async def create_and_start(
        cls,
        reply_target,
        bot,
        chat_id: int,
        title: str = "EduBot AI",
        initial_desc: str = "Fikrlash boshlandi...",
        stages: Optional[List[Tuple[str, str, str, str]]] = None,
        interval: float = 0.95
    ):
        """
        Dastlabki xabarni darhol jo'natib, animatsiyani avtomatik ishga tushiradi.
        """
        initial_text = (
            f"⚡️ <b>{title}</b>\n"
            f"<code>▰▱▱▱▱▱▱▱▱▱</code> <b>10%</b>\n"
            f"💭 <i>{initial_desc}</i>"
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
        idx = 0
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.interval)
                if self._stop_event.is_set():
                    break

                if idx < len(self.stages):
                    icon, text, bar, pct = self.stages[idx]
                else:
                    pulse_icons = ["🔮", "✨", "⚡️", "💡", "🧠"]
                    icon = pulse_icons[idx % len(pulse_icons)]
                    text = "Mukammal javob yakunlanmoqda..."
                    bar = "▰▰▰▰▰▰▰▰▰▰"
                    pct = "99%"

                content = (
                    f"⚡️ <b>{self.title}</b>\n"
                    f"<code>{bar}</code> <b>{pct}</b>\n"
                    f"{icon} <i>{text}</i>"
                )

                try:
                    await self.bot.send_chat_action(chat_id=self.chat_id, action="typing")
                except Exception:
                    pass

                await self.message.edit_text(content, parse_mode="HTML")
                idx += 1
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
