from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.candidate import CandidateResponse
from app.schemas.vacancy import VacancyResponse

class ApplicationBase(BaseModel):
    vacancy_id: int
    candidate_id: int
    cv_original_filename: str
    cv_file_path: str
    cv_file_size: int
    cv_mime_type: str
    status: str = "New"
    hr_notes: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_matching_analysis: Optional[str] = None

class ApplicationCreate(BaseModel):
    vacancy_id: int
    telegram_user_id: int
    telegram_username: Optional[str] = None
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    cv_original_filename: str
    cv_bytes: bytes

class ApplicationStatusUpdate(BaseModel):
    status: str
    hr_notes: Optional[str] = None

class ApplicationNoteUpdate(BaseModel):
    hr_notes: str

class ApplicationResponse(BaseModel):
    id: int
    application_code: str
    candidate_id: int
    vacancy_id: int
    cv_original_filename: str
    cv_file_size: int
    cv_mime_type: str
    status: str
    hr_notes: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_matching_analysis: Optional[str] = None
    duplicate_submission_count: int
    submitted_at: datetime
    updated_at: datetime

    candidate: Optional[CandidateResponse] = None
    vacancy: Optional[VacancyResponse] = None

    model_config = ConfigDict(from_attributes=True)
