from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class VacancyBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    salary_range: Optional[str] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    education: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[str] = None
    instructions: Optional[str] = None
    closing_date: Optional[datetime] = None

class VacancyCreate(VacancyBase):
    pass

class VacancyUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    salary_range: Optional[str] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    education: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[str] = None
    instructions: Optional[str] = None
    status: Optional[str] = None
    closing_date: Optional[datetime] = None

class VacancyResponse(VacancyBase):
    id: int
    vacancy_code: str
    status: str
    created_at: datetime
    updated_at: datetime
    applications_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

class ExtractedJDData(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    salary_range: Optional[str] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    education: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[str] = None
    instructions: Optional[str] = None
    positions_detected: List[Dict[str, Any]] = []
