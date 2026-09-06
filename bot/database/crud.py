from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from datetime import datetime
from bot.database.models import User, File, Quiz, UsageLog
from typing import Optional, List

async def get_or_create_user(session: AsyncSession, telegram_id: int, full_name: str, username: Optional[str] = None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if user:
        user.full_name = full_name
        user.username = username
        user.last_active = datetime.utcnow()
    else:
        user = User(telegram_id=telegram_id, full_name=full_name, username=username)
        session.add(user)
    
    await session.commit()
    await session.refresh(user)
    return user

async def update_user_activity(session: AsyncSession, telegram_id: int):
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        user.last_active = datetime.utcnow()
        await session.commit()

async def save_file_record(session: AsyncSession, user_id: int, file_name: str, file_type: str, telegram_file_id: str, local_path: str, file_size: int) -> File:
    file_record = File(
        user_id=user_id,
        file_name=file_name,
        file_type=file_type,
        telegram_file_id=telegram_file_id,
        local_path=local_path,
        file_size=file_size
    )
    session.add(file_record)
    await session.commit()
    await session.refresh(file_record)
    return file_record

async def get_user_files(session: AsyncSession, user_id: int, file_type: Optional[str] = None, limit: int = 50) -> List[File]:
    query = select(File).where(File.user_id == user_id).order_by(File.uploaded_at.desc()).limit(limit)
    if file_type:
        query = query.where(File.file_type == file_type)
    result = await session.execute(query)
    return list(result.scalars().all())

async def delete_file_record(session: AsyncSession, file_id: int):
    result = await session.execute(select(File).where(File.id == file_id))
    file_record = result.scalar_one_or_none()
    if file_record:
        await session.delete(file_record)
        await session.commit()

async def create_quiz(session: AsyncSession, user_id: int, title: str, subject: Optional[str], questions_count: int, questions_data: dict) -> Quiz:
    quiz = Quiz(
        user_id=user_id,
        title=title,
        subject=subject,
        questions_count=questions_count,
        questions_data=questions_data
    )
    session.add(quiz)
    await session.commit()
    await session.refresh(quiz)
    return quiz

async def get_user_quizzes(session: AsyncSession, user_id: int, limit: int = 20) -> List[Quiz]:
    query = select(Quiz).where(Quiz.user_id == user_id).order_by(Quiz.created_at.desc()).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())

async def log_usage(session: AsyncSession, user_id: int, action_type: str, details: Optional[str] = None):
    log = UsageLog(user_id=user_id, action_type=action_type, details=details)
    session.add(log)
    await session.commit()

async def get_user_stats(session: AsyncSession, user_id: int) -> dict:
    file_count_result = await session.execute(select(func.count(File.id)).where(File.user_id == user_id))
    quiz_count_result = await session.execute(select(func.count(Quiz.id)).where(Quiz.user_id == user_id))
    
    return {
        "file_count": file_count_result.scalar_one_or_none() or 0,
        "quiz_count": quiz_count_result.scalar_one_or_none() or 0
    }
