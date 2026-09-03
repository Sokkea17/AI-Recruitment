import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.database.base import Base

# Normalize SQLite database URL for async if needed
db_url = settings.DATABASE_URL
if db_url.startswith('sqlite:///'):
    db_url = db_url.replace('sqlite:///', 'sqlite+aiosqlite:///')

engine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    future=True
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    # Import all models to ensure they are registered with Base.metadata
    from app.models import Vacancy, JDFile, Candidate, Application, Interview, User, AuditLog, SystemSetting
    from app.utils.security import hash_password

    # Ensure storage paths exist
    os.makedirs(settings.cv_storage_path, exist_ok=True)
    os.makedirs(settings.jd_storage_path, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize default admin user and system settings if not existing
    async with async_session_factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.username == settings.HR_DEFAULT_USERNAME))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                username=settings.HR_DEFAULT_USERNAME,
                email='admin@recruitment.local',
                hashed_password=hash_password(settings.HR_DEFAULT_PASSWORD),
                full_name='HR Administrator',
                role='admin',
                is_active=True
            )
            session.add(admin)

        # Initialize default settings
        default_settings = {
            'hr_telegram_chat_id': settings.HR_TELEGRAM_CHAT_ID or '',
            'notifications_enabled': 'true',
            'notify_on_duplicates': 'true',
            'include_ai_summary': 'true',
            'duplicate_cv_policy': 'allow_update', # 'allow_update', 'reject'
            'ai_provider': settings.AI_PROVIDER,
        }
        for key, val in default_settings.items():
            s_result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
            if not s_result.scalar_one_or_none():
                session.add(SystemSetting(key=key, value=val))

        await session.commit()
