from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class CandidateBase(BaseModel):
    telegram_user_id: int
    telegram_username: Optional[str] = None
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None

class CandidateCreate(CandidateBase):
    pass

class CandidateResponse(CandidateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
