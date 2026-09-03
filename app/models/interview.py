from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.candidate import Candidate
    from app.models.vacancy import Vacancy

class Interview(Base):
    __tablename__ = 'interviews'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id', ondelete='CASCADE'), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey('candidates.id', ondelete='CASCADE'), index=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey('vacancies.id', ondelete='CASCADE'), index=True)

    interview_date: Mapped[str] = mapped_column(String(32))  # e.g. "2026-09-10"
    interview_time: Mapped[str] = mapped_column(String(32))  # e.g. "10:00 AM"
    interview_timezone: Mapped[str] = mapped_column(String(64), default='Asia/Phnom_Penh')
    interview_type: Mapped[str] = mapped_column(String(32), default='In-person')  # In-person, Online, Phone
    interview_location: Mapped[str] = mapped_column(String(500))  # Office address or meeting link
    meeting_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    interviewer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status: Scheduled, Confirmed, Reschedule Requested, Declined, Completed, Cancelled
    status: Mapped[str] = mapped_column(String(32), default='Scheduled', index=True)

    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    invitation_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    invitation_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    application: Mapped['Application'] = relationship('Application', back_populates='interviews')
    candidate: Mapped['Candidate'] = relationship('Candidate')
    vacancy: Mapped['Vacancy'] = relationship('Vacancy')
