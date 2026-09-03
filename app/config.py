import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory is the project root (where app/ is located)
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / '.env'),
        env_file_encoding='utf-8',
        extra='ignore'
    )

    BASE_DIR: Path = BASE_DIR

    # Application
    APP_NAME: str = 'Recruitment Assistant & HR Automation'
    HOST: str = '0.0.0.0'
    PORT: int = 8000
    DEBUG: bool = False
    SECRET_KEY: str = 'f9c2d78a1b6e4f3a8d9c2e5b7a1d4f6e8b0c2d4e6f8a0b2c4d6e8f0a2b4c6d8e'
    SESSION_EXPIRE_HOURS: int = 24

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = ''
    HR_TELEGRAM_CHAT_ID: str = ''

    # Database: Default to project root recruitment.db
    DATABASE_URL: str = f'sqlite+aiosqlite:///{BASE_DIR / "recruitment.db"}'

    # Storage: Default to project root /storage
    STORAGE_PATH: str = str(BASE_DIR / 'storage')
    MAX_FILE_SIZE_MB: int = 15

    # HR Admin Initial Credentials
    HR_DEFAULT_USERNAME: str = 'admin'
    HR_DEFAULT_PASSWORD: str = 'admin123'

    # AI Configuration
    AI_PROVIDER: str = 'none'  # 'none', 'openai', 'gemini'
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def cv_storage_path(self) -> str:
        return os.path.join(self.STORAGE_PATH, 'cvs')

    @property
    def jd_storage_path(self) -> str:
        return os.path.join(self.STORAGE_PATH, 'jds')

settings = Settings()
