import logging
from telegram import Update
from telegram.ext import ContextTypes, BaseHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def logging_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        logger.info(f"User {user.id} ({user.username}) triggered an update.")
