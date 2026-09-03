from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.vacancy import Vacancy
    from app.models.interview import Interview

class Application(Base):
    __tablename__ = 'applications'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey('candidates.id', ondelete='CASCADE'), index=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey('vacancies.id', ondelete='CASCADE'), index=True)
    
    cv_file_path: Mapped[str] = mapped_column(String(512))
    cv_original_filename: Mapped[str] = mapped_column(String(255))
    cv_file_size: Mapped[int] = mapped_column(Integer, default=0)
    cv_mime_type: Mapped[str] = mapped_column(String(100), default='application/pdf')
    extracted_cv_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status: New, Under Review, Shortlisted, Interview Scheduled, Interview Confirmed, Interview Completed, Reschedule Requested, Interview Declined, Interview, Selected, Rejected, Withdrawn
    status: Mapped[str] = mapped_column(String(32), default='New', index=True)
    
    hr_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_matching_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    duplicate_submission_count: Mapped[int] = mapped_column(Integer, default=0)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    candidate: Mapped['Candidate'] = relationship('Candidate', back_populates='applications')
    vacancy: Mapped['Vacancy'] = relationship('Vacancy', back_populates='applications')
    interviews: Mapped[List['Interview']] = relationship('Interview', back_populates='application', cascade='all, delete-orphan', order_by='desc(Interview.created_at)')
