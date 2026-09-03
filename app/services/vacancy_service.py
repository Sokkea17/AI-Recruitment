from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, func, desc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.vacancy import Vacancy, JDFile
from app.models.audit_log import AuditLog
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
    async def get_all_vacancies(
        session: AsyncSession,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
        department: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[Vacancy]:
        stmt = select(Vacancy).options(selectinload(Vacancy.applications)).order_by(desc(Vacancy.created_at))
        if status_filter and status_filter != "all":
            stmt = stmt.where(Vacancy.status == status_filter)
        if department and department != "all":
            stmt = stmt.where(Vacancy.department == department)
        if from_date:
            stmt = stmt.where(Vacancy.created_at >= from_date)
        if to_date:
            stmt = stmt.where(Vacancy.created_at <= to_date)
        if search and search.strip():
            words = [w for w in search.strip().split() if w]
            vac_conditions = []
            for word in words:
                w_term = f"%{word}%"
                vac_conditions.append(
                    or_(
                        Vacancy.title.ilike(w_term),
                        Vacancy.vacancy_code.ilike(w_term),
                        Vacancy.department.ilike(w_term),
                        Vacancy.location.ilike(w_term),
                        Vacancy.skills.ilike(w_term),
                        Vacancy.requirements.ilike(w_term)
                    )
                )
            stmt = stmt.where(and_(*vac_conditions))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_departments(session: AsyncSession) -> List[str]:
        stmt = select(Vacancy.department).where(Vacancy.department.is_not(None)).distinct()
        res = await session.execute(stmt)
        depts = [r[0] for r in res.all() if r[0] and r[0].strip()]
        return sorted(list(set(depts)))

    @staticmethod
    async def get_jd_files(
        session: AsyncSession,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[JDFile]:
        stmt = select(JDFile).options(selectinload(JDFile.vacancy)).order_by(desc(JDFile.uploaded_at))
        if from_date:
            stmt = stmt.where(JDFile.uploaded_at >= from_date)
        if to_date:
            stmt = stmt.where(JDFile.uploaded_at <= to_date)
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

    @staticmethod
    async def delete_vacancy(vacancy_id: int, session: AsyncSession) -> bool:
        vacancy = await VacancyService.get_vacancy_by_id(vacancy_id, session)
        if not vacancy:
            return False

        # If any JD files are associated, set vacancy_id to None to preserve document history
        for jd in vacancy.jd_files:
            jd.vacancy_id = None

        audit = AuditLog(
            action="VACANCY_DELETED",
            target_entity="vacancy",
            target_id=vacancy.id,
            details=f"Vacancy '{vacancy.title}' ({vacancy.vacancy_code}) permanently deleted"
        )
        session.add(audit)

        await session.delete(vacancy)
        await session.commit()
        return True

vacancy_service = VacancyService()
