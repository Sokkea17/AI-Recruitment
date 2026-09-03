from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.vacancy import Vacancy, JDFile
from app.schemas.vacancy import VacancyCreate, VacancyUpdate
from app.services.storage_service import storage_service
from app.services.document_parser import document_parser

class VacancyService:
    @staticmethod
    async def generate_vacancy_code(session: AsyncSession) -> str:
        year = datetime.utcnow().year
        stmt = select(func.count(Vacancy.id))
        result = await session.execute(stmt)
        count = result.scalar() or 0
        return f"VAC-{year}-{(count + 1):03d}"

    @staticmethod
    async def create_vacancy(data: VacancyCreate, session: AsyncSession) -> Vacancy:
        code = await VacancyService.generate_vacancy_code(session)
        vacancy = Vacancy(
            vacancy_code=code,
            title=data.title,
            department=data.department,
            location=data.location,
            employment_type=data.employment_type,
            salary_range=data.salary_range,
            short_description=data.short_description,
            full_description=data.full_description,
            responsibilities=data.responsibilities,
            requirements=data.requirements,
            education=data.education,
            experience=data.experience,
            skills=data.skills,
            instructions=data.instructions,
            status="Draft",
            closing_date=data.closing_date
        )
        session.add(vacancy)
        await session.commit()
        await session.refresh(vacancy)
        return vacancy

    @staticmethod
    async def get_vacancy_by_id(vacancy_id: int, session: AsyncSession) -> Optional[Vacancy]:
        stmt = select(Vacancy).options(selectinload(Vacancy.applications), selectinload(Vacancy.jd_files)).where(Vacancy.id == vacancy_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_vacancy_by_code(code: str, session: AsyncSession) -> Optional[Vacancy]:
        stmt = select(Vacancy).where(Vacancy.vacancy_code == code)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_vacancies(session: AsyncSession, status_filter: Optional[str] = None) -> List[Vacancy]:
        stmt = select(Vacancy).options(selectinload(Vacancy.applications)).order_by(desc(Vacancy.created_at))
        if status_filter:
            stmt = stmt.where(Vacancy.status == status_filter)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_published_vacancies(session: AsyncSession) -> List[Vacancy]:
        stmt = select(Vacancy).where(Vacancy.status == "Published").order_by(desc(Vacancy.created_at))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_vacancy(vacancy_id: int, data: VacancyUpdate, session: AsyncSession) -> Optional[Vacancy]:
        vacancy = await VacancyService.get_vacancy_by_id(vacancy_id, session)
        if not vacancy:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            setattr(vacancy, key, val)

        vacancy.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(vacancy)
        return vacancy

    @staticmethod
    async def publish_vacancy(vacancy_id: int, session: AsyncSession) -> Optional[Vacancy]:
        vacancy = await VacancyService.get_vacancy_by_id(vacancy_id, session)
        if not vacancy:
            return None
        vacancy.status = "Published"
        vacancy.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(vacancy)
        return vacancy

    @staticmethod
    async def close_vacancy(vacancy_id: int, session: AsyncSession) -> Optional[Vacancy]:
        vacancy = await VacancyService.get_vacancy_by_id(vacancy_id, session)
        if not vacancy:
            return None
        vacancy.status = "Closed"
        vacancy.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(vacancy)
        return vacancy

    @staticmethod
    async def process_jd_upload(file_bytes: bytes, filename: str, session: AsyncSession) -> Tuple[JDFile, Dict[str, Any]]:
        # 1. Save file securely to storage/jds
        stored_path, stored_filename, file_size, mime_type = storage_service.save_file(file_bytes, filename, category="jds")

        # 2. Extract text and structured fields
        raw_text = document_parser.extract_text_from_bytes(file_bytes, filename)
        extracted_data = document_parser.parse_jd_sections(raw_text)

        # 3. Create JDFile record
        jd_file = JDFile(
            original_filename=filename,
            stored_file_path=stored_path,
            file_size=file_size,
            raw_extracted_text=raw_text,
            structured_data=extracted_data
        )
        session.add(jd_file)
        await session.commit()
        await session.refresh(jd_file)

        return jd_file, extracted_data

vacancy_service = VacancyService()
