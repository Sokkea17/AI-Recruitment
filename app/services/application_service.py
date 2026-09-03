from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telegram import Bot

from app.models.candidate import Candidate
from app.models.application import Application
from app.models.vacancy import Vacancy
from app.models.audit_log import AuditLog
from app.schemas.application import ApplicationCreate
from app.services.storage_service import storage_service
from app.services.document_parser import document_parser
from app.services.ai_service import ai_service
from app.services.notification_service import notification_service

class ApplicationService:
    @staticmethod
    async def generate_application_code(session: AsyncSession) -> str:
        stmt = select(func.count(Application.id))
        result = await session.execute(stmt)
        count = result.scalar() or 0
        return f"APP-{(count + 1):04d}"

    @staticmethod
    async def get_or_create_candidate(
        telegram_user_id: int,
        telegram_username: Optional[str],
        full_name: str,
        phone: Optional[str],
        email: Optional[str],
        session: AsyncSession
    ) -> Candidate:
        stmt = select(Candidate).where(Candidate.telegram_user_id == telegram_user_id)
        result = await session.execute(stmt)
        candidate = result.scalar_one_or_none()

        if not candidate:
            candidate = Candidate(
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
                full_name=full_name,
                phone=phone,
                email=email
            )
            session.add(candidate)
            await session.commit()
            await session.refresh(candidate)
        else:
            # Update contact info if provided
            updated = False
            if full_name and candidate.full_name != full_name:
                candidate.full_name = full_name
                updated = True
            if phone and candidate.phone != phone:
                candidate.phone = phone
                updated = True
            if email and candidate.email != email:
                candidate.email = email
                updated = True
            if telegram_username and candidate.telegram_username != telegram_username:
                candidate.telegram_username = telegram_username
                updated = True
            if updated:
                candidate.updated_at = datetime.utcnow()
                await session.commit()
                await session.refresh(candidate)

        return candidate

    @staticmethod
    async def check_duplicate(
        telegram_user_id: int,
        vacancy_id: int,
        session: AsyncSession
    ) -> Optional[Application]:
        stmt = (
            select(Application)
            .join(Candidate)
            .where(Candidate.telegram_user_id == telegram_user_id)
            .where(Application.vacancy_id == vacancy_id)
            .options(selectinload(Application.candidate), selectinload(Application.vacancy))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def submit_application(
        data: ApplicationCreate,
        session: AsyncSession,
        is_update: bool = False,
        bot: Optional[Bot] = None
    ) -> Application:
        # 1. Verify Vacancy
        stmt = select(Vacancy).where(Vacancy.id == data.vacancy_id)
        v_result = await session.execute(stmt)
        vacancy = v_result.scalar_one_or_none()
        if not vacancy:
            raise ValueError("The selected position does not exist or has been removed.")

        # 2. Get or create candidate
        candidate = await ApplicationService.get_or_create_candidate(
            telegram_user_id=data.telegram_user_id,
            telegram_username=data.telegram_username,
            full_name=data.full_name,
            phone=data.phone,
            email=data.email,
            session=session
        )

        # 3. Save CV File
        stored_path, stored_filename, file_size, mime_type = storage_service.save_file(
            data.cv_bytes,
            data.cv_original_filename,
            category="cvs"
        )

        # 4. Extract CV text
        extracted_text = ""
        try:
            extracted_text = document_parser.extract_text_from_bytes(data.cv_bytes, data.cv_original_filename)
        except Exception:
            pass

        # 5. Perform AI analysis (advisory summary & matching)
        analysis = await ai_service.analyze_application(
            cv_text=extracted_text,
            vacancy_title=vacancy.title,
            vacancy_requirements=vacancy.requirements,
            vacancy_skills=vacancy.skills
        )

        # 6. Check existing application for duplicate
        existing = await ApplicationService.check_duplicate(data.telegram_user_id, data.vacancy_id, session)

        if existing and is_update:
            # Update existing application with new CV
            existing.cv_file_path = stored_path
            existing.cv_original_filename = data.cv_original_filename
            existing.cv_file_size = file_size
            existing.cv_mime_type = mime_type
            existing.extracted_cv_text = extracted_text
            existing.ai_summary = analysis["ai_summary"]
            existing.ai_matching_analysis = analysis["ai_matching_analysis"]
            existing.status = "New" # Reset to New on CV update
            existing.duplicate_submission_count += 1
            existing.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(existing)
            application = existing
        else:
            # Create new Application
            app_code = await ApplicationService.generate_application_code(session)
            application = Application(
                application_code=app_code,
                candidate_id=candidate.id,
                vacancy_id=vacancy.id,
                cv_file_path=stored_path,
                cv_original_filename=data.cv_original_filename,
                cv_file_size=file_size,
                cv_mime_type=mime_type,
                extracted_cv_text=extracted_text,
                status="New",
                ai_summary=analysis["ai_summary"],
                ai_matching_analysis=analysis["ai_matching_analysis"],
                duplicate_submission_count=0
            )
            session.add(application)
            await session.commit()
            await session.refresh(application)

        # 7. Audit log
        audit = AuditLog(
            action="APPLICATION_SUBMITTED" if not is_update else "APPLICATION_CV_UPDATED",
            target_entity="application",
            target_id=application.id,
            details=f"Application {application.application_code} for {vacancy.title} by {candidate.full_name}"
        )
        session.add(audit)
        await session.commit()

        # 8. Trigger HR Notification
        await notification_service.send_new_application_alert(
            application=application,
            candidate=candidate,
            vacancy=vacancy,
            session=session,
            bot=bot
        )

        return application

    @staticmethod
    async def get_applications(
        session: AsyncSession,
        status: Optional[str] = None,
        vacancy_id: Optional[int] = None,
        search: Optional[str] = None
    ) -> List[Application]:
        stmt = (
            select(Application)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.vacancy),
                selectinload(Application.interviews)
            )
            .order_by(desc(Application.submitted_at))
        )
        if status and status != "all":
            stmt = stmt.where(Application.status == status)
        if vacancy_id:
            stmt = stmt.where(Application.vacancy_id == vacancy_id)
        if search:
            search_term = f"%{search}%"
            stmt = stmt.join(Candidate).join(Vacancy).where(
                or_(
                    Application.application_code.ilike(search_term),
                    Candidate.full_name.ilike(search_term),
                    Candidate.email.ilike(search_term),
                    Candidate.phone.ilike(search_term),
                    Vacancy.title.ilike(search_term)
                )
            )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_application_by_id(session: AsyncSession, application_id: int) -> Optional[Application]:
        stmt = (
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.vacancy),
                selectinload(Application.interviews)
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_status(
        session: AsyncSession,
        application_id: int,
        new_status: str,
        user_id: Optional[int] = None,
        hr_notes: Optional[str] = None
    ) -> Optional[Application]:
        app = await ApplicationService.get_application_by_id(session, application_id)
        if not app:
            return None

        old_status = app.status
        app.status = new_status
        if hr_notes is not None:
            app.hr_notes = hr_notes
        app.updated_at = datetime.utcnow()

        audit = AuditLog(
            user_id=user_id,
            action="STATUS_CHANGE",
            target_entity="application",
            target_id=app.id,
            details=f"Changed status from '{old_status}' to '{new_status}'"
        )
        session.add(audit)
        await session.commit()
        await session.refresh(app)
        return app

    @staticmethod
    async def get_candidate_applications(
        session: AsyncSession,
        telegram_user_id: int
    ) -> List[Application]:
        stmt = (
            select(Application)
            .join(Candidate)
            .where(Candidate.telegram_user_id == telegram_user_id)
            .options(selectinload(Application.vacancy))
            .order_by(desc(Application.submitted_at))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

application_service = ApplicationService()
