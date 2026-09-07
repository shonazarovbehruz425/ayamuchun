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

async def save_file_record(session: AsyncSession, user_id: int, file_name: str, file_type: str, telegram_file_id: str, local_path: str, file_size: int, upsert: bool = True) -> File:
    if upsert:
        import os
        from datetime import datetime
        result = await session.execute(
            select(File).where(File.user_id == user_id, File.file_name == file_name).order_by(File.uploaded_at.desc())
        )
        existing = result.scalars().first()
        if existing:
            # Delete old file on disk if path changed
            if existing.local_path and existing.local_path != local_path and os.path.exists(existing.local_path):
                try:
                    os.remove(existing.local_path)
                except Exception:
                    pass
            existing.file_type = file_type
            existing.telegram_file_id = telegram_file_id
            existing.local_path = local_path
            existing.file_size = file_size
            existing.uploaded_at = datetime.utcnow()
            await session.commit()
            await session.refresh(existing)
            return existing

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

async def get_admin_overview(session: AsyncSession) -> dict:
    from datetime import datetime, timedelta
    
    users_cnt = (await session.execute(select(func.count(User.id)))).scalar_one_or_none() or 0
    files_cnt = (await session.execute(select(func.count(File.id)))).scalar_one_or_none() or 0
    quizzes_cnt = (await session.execute(select(func.count(Quiz.id)))).scalar_one_or_none() or 0
    total_size = (await session.execute(select(func.sum(File.file_size)))).scalar_one_or_none() or 0

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    active_today = (await session.execute(
        select(func.count(User.id)).where(User.last_active >= today_start)
    )).scalar_one_or_none() or 0

    return {
        "total_users": users_cnt,
        "active_today": active_today,
        "total_files": files_cnt,
        "total_quizzes": quizzes_cnt,
        "total_storage_bytes": int(total_size)
    }

async def get_admin_users_list(session: AsyncSession, limit: int = 100, search: Optional[str] = None) -> list:
    query = select(User).order_by(User.last_active.desc()).limit(limit)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (User.full_name.ilike(search_pattern)) | 
            (User.username.ilike(search_pattern)) | 
            (func.cast(User.telegram_id, String).ilike(search_pattern))
        )
    users = list((await session.execute(query)).scalars().all())
    
    user_list = []
    for u in users:
        fc = (await session.execute(select(func.count(File.id)).where(File.user_id == u.id))).scalar_one_or_none() or 0
        qc = (await session.execute(select(func.count(Quiz.id)).where(Quiz.user_id == u.id))).scalar_one_or_none() or 0
        user_list.append({
            "id": u.id,
            "telegram_id": u.telegram_id,
            "full_name": u.full_name,
            "username": u.username or "",
            "phone_number": getattr(u, "phone_number", None) or "",
            "language": u.language or "uz",
            "file_count": fc,
            "quiz_count": qc,
            "created_at": u.created_at.strftime("%d.%m.%Y %H:%M") if u.created_at else "",
            "last_active": u.last_active.strftime("%d.%m.%Y %H:%M") if u.last_active else ""
        })
    return user_list

async def get_admin_recent_files(session: AsyncSession, limit: int = 50) -> list:
    query = (
        select(File, User.full_name, User.username, User.telegram_id)
        .join(User, File.user_id == User.id)
        .order_by(File.uploaded_at.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    rows = result.all()
    
    file_list = []
    for f, full_name, username, telegram_id in rows:
        file_list.append({
            "id": f.id,
            "file_name": f.file_name,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "user_name": full_name,
            "username": username or "",
            "telegram_id": telegram_id,
            "uploaded_at": f.uploaded_at.strftime("%d.%m.%Y %H:%M") if f.uploaded_at else ""
        })
    return file_list

async def get_all_user_ids(session: AsyncSession) -> list[int]:
    result = await session.execute(select(User.telegram_id))
    return list(result.scalars().all())
