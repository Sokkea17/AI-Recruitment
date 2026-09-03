from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.application import Application

class Vacancy(Base):
    __tablename__ = 'vacancies'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vacancy_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    employment_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Full-time, etc.
    salary_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    short_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    education: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    experience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    skills: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status: Draft, Published, Closed
    status: Mapped[str] = mapped_column(String(32), default='Draft', index=True)
    
    closing_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    applications: Mapped[List['Application']] = relationship('Application', back_populates='vacancy', cascade='all, delete-orphan')
    jd_files: Mapped[List['JDFile']] = relationship('JDFile', back_populates='vacancy')

class JDFile(Base):
    __tablename__ = 'jd_files'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vacancy_id: Mapped[Optional[int]] = mapped_column(ForeignKey('vacancies.id', ondelete='SET NULL'), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_file_path: Mapped[str] = mapped_column(String(512))
    file_size: Mapped[int] = mapped_column(default=0)
    raw_extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    structured_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    vacancy: Mapped[Optional['Vacancy']] = relationship('Vacancy', back_populates='jd_files')
