import logging
from datetime import datetime, date
from typing import Optional, List, Tuple
from sqlalchemy import select, desc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.interview import Interview
from app.models.application import Application
from app.models.audit_log import AuditLog
from app.utils.formatters import get_current_cambodia_time

logger = logging.getLogger(__name__)

class InterviewService:
    @staticmethod
    def validate_schedule_date(interview_date_str: str) -> bool:
        """
        Validates that the selected date is not in the past relative to Cambodia Local Time.
        """
        try:
            intv_date = datetime.strptime(interview_date_str, "%Y-%m-%d").date()
            today_cambodia = get_current_cambodia_time().date()
            return intv_date >= today_cambodia
        except Exception:
            return False

    @staticmethod
    async def get_interviews_for_application(session: AsyncSession, application_id: int) -> List[Interview]:
        stmt = (
            select(Interview)
            .where(Interview.application_id == application_id)
            .order_by(desc(Interview.created_at))
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_active_interview(session: AsyncSession, application_id: int) -> Optional[Interview]:
        stmt = (
            select(Interview)
            .where(
                Interview.application_id == application_id,
                Interview.status.in_(["Scheduled", "Confirmed", "Reschedule Requested"])
            )
            .order_by(desc(Interview.created_at))
        )
        res = await session.execute(stmt)
        active = res.scalars().first()
        if not active:
            # Fall back to latest interview if none strictly active
            stmt_latest = (
                select(Interview)
                .where(Interview.application_id == application_id)
                .order_by(desc(Interview.created_at))
            )
            res_latest = await session.execute(stmt_latest)
            active = res_latest.scalars().first()
        return active

    @staticmethod
    async def get_interview_by_id(session: AsyncSession, interview_id: int) -> Optional[Interview]:
        stmt = (
            select(Interview)
            .where(Interview.id == interview_id)
            .options(
                selectinload(Interview.application),
                selectinload(Interview.candidate),
                selectinload(Interview.vacancy)
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def schedule_interview(
        session: AsyncSession,
        application_id: int,
        interview_date: str,
        interview_time: str,
        interview_type: str,
        interview_location: str,
        meeting_link: Optional[str] = None,
        interviewer_name: Optional[str] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None,
        send_invitation: bool = True
    ) -> Tuple[Optional[Interview], Optional[str]]:
        # 1. Fetch application with candidate & vacancy
        app_stmt = (
            select(Application)
            .where(Application.id == application_id)
            .options(selectinload(Application.candidate), selectinload(Application.vacancy))
        )
        app_res = await session.execute(app_stmt)
        application = app_res.scalar_one_or_none()
        if not application:
            return None, "Application not found."

        # 2. Validation
        if not interview_date or not interview_time or not interview_location:
            return None, "Interview date, time, and location are required."

        if not InterviewService.validate_schedule_date(interview_date):
            return None, "Interview date cannot be in the past."

        # 3. Create interview record
        interview = Interview(
            application_id=application.id,
            candidate_id=application.candidate_id,
            vacancy_id=application.vacancy_id,
            interview_date=interview_date.strip(),
            interview_time=interview_time.strip(),
            interview_timezone="Asia/Phnom_Penh",
            interview_type=interview_type.strip() if interview_type else "In-person",
            interview_location=interview_location.strip(),
            meeting_link=meeting_link.strip() if meeting_link else None,
            interviewer_name=interviewer_name.strip() if interviewer_name else None,
            notes=notes.strip() if notes else None,
            status="Scheduled",
            invitation_sent=False
        )
        session.add(interview)

        # Update application status
        application.status = "Interview Scheduled"
        application.updated_at = datetime.utcnow()

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="INTERVIEW_SCHEDULED",
            target_entity="interview",
            details=f"Scheduled interview for {application.candidate.full_name} ({application.application_code}) on {interview_date} {interview_time}"
        )
        session.add(audit)
        await session.commit()
        await session.refresh(interview)

        # 4. Dispatch Telegram invitation if requested
        error_msg = None
        if send_invitation:
            from app.services.interview_notification_service import interview_notification_service
            sent, err = await interview_notification_service.send_interview_invitation(interview, session)
            interview.invitation_sent = sent
            interview.invitation_error = err
            await session.commit()
            if not sent:
                error_msg = err or "Telegram invitation could not be delivered to candidate."

        return interview, error_msg

    @staticmethod
    async def edit_interview(
        session: AsyncSession,
        interview_id: int,
        interview_date: str,
        interview_time: str,
        interview_type: str,
        interview_location: str,
        meeting_link: Optional[str] = None,
        interviewer_name: Optional[str] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None,
        send_update: bool = True
    ) -> Tuple[Optional[Interview], Optional[str]]:
        interview = await InterviewService.get_interview_by_id(session, interview_id)
        if not interview:
            return None, "Interview not found."

        if not interview_date or not interview_time or not interview_location:
            return None, "Interview date, time, and location are required."

        if not InterviewService.validate_schedule_date(interview_date):
            return None, "Interview date cannot be in the past."

        interview.interview_date = interview_date.strip()
        interview.interview_time = interview_time.strip()
        interview.interview_type = interview_type.strip() if interview_type else interview.interview_type
        interview.interview_location = interview_location.strip()
        interview.meeting_link = meeting_link.strip() if meeting_link else None
        interview.interviewer_name = interviewer_name.strip() if interviewer_name else None
        interview.notes = notes.strip() if notes else None
        interview.updated_at = datetime.utcnow()

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="INTERVIEW_EDITED",
            target_entity="interview",
            target_id=interview.id,
            details=f"Updated interview details to {interview_date} {interview_time}"
        )
        session.add(audit)
        await session.commit()
        await session.refresh(interview)

        error_msg = None
        if send_update:
            from app.services.interview_notification_service import interview_notification_service
            sent, err = await interview_notification_service.send_interview_update(interview, session)
            if not sent:
                error_msg = err or "Telegram update notification could not be delivered to candidate."

        return interview, error_msg

    @staticmethod
    async def cancel_interview(
        session: AsyncSession,
        interview_id: int,
        user_id: Optional[int] = None,
        send_cancellation: bool = True
    ) -> Tuple[Optional[Interview], Optional[str]]:
        interview = await InterviewService.get_interview_by_id(session, interview_id)
        if not interview:
            return None, "Interview not found."

        interview.status = "Cancelled"
        interview.updated_at = datetime.utcnow()

        if interview.application:
            interview.application.status = "Shortlisted"
            interview.application.updated_at = datetime.utcnow()

        audit = AuditLog(
            user_id=user_id,
            action="INTERVIEW_CANCELLED",
            target_entity="interview",
            target_id=interview.id,
            details=f"Cancelled interview #{interview.id}"
        )
        session.add(audit)
        await session.commit()
        await session.refresh(interview)

        error_msg = None
        if send_cancellation:
            from app.services.interview_notification_service import interview_notification_service
            sent, err = await interview_notification_service.send_interview_cancellation(interview, session)
            if not sent:
                error_msg = err or "Cancellation message could not be sent to candidate on Telegram."

        return interview, error_msg

    @staticmethod
    async def mark_completed(
        session: AsyncSession,
        interview_id: int,
        user_id: Optional[int] = None
    ) -> Tuple[Optional[Interview], Optional[str]]:
        interview = await InterviewService.get_interview_by_id(session, interview_id)
        if not interview:
            return None, "Interview not found."

        interview.status = "Completed"
        interview.updated_at = datetime.utcnow()

        if interview.application:
            interview.application.status = "Interview Completed"
            interview.application.updated_at = datetime.utcnow()

        audit = AuditLog(
            user_id=user_id,
            action="INTERVIEW_COMPLETED",
            target_entity="interview",
            target_id=interview.id,
            details=f"Marked interview #{interview.id} as completed"
        )
        session.add(audit)
        await session.commit()
        return interview, None


    @staticmethod
    async def get_all_interviews(
        session: AsyncSession,
        search: Optional[str] = None,
        vacancy_id: Optional[int] = None,
        status: Optional[str] = None,
        interview_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[Interview]:
        from app.models.candidate import Candidate
        from app.models.vacancy import Vacancy
        from sqlalchemy import or_

        stmt = (
            select(Interview)
            .join(Candidate, Interview.candidate_id == Candidate.id, isouter=True)
            .join(Vacancy, Interview.vacancy_id == Vacancy.id, isouter=True)
            .options(
                selectinload(Interview.application),
                selectinload(Interview.candidate),
                selectinload(Interview.vacancy)
            )
            .order_by(desc(Interview.interview_date), desc(Interview.created_at))
        )

        if status and status != "all":
            stmt = stmt.where(Interview.status == status)
        if interview_type and interview_type != "all":
            stmt = stmt.where(Interview.interview_type == interview_type)
        if vacancy_id:
            stmt = stmt.where(Interview.vacancy_id == vacancy_id)
        if from_date and from_date.strip():
            stmt = stmt.where(Interview.interview_date >= from_date.strip())
        if to_date and to_date.strip():
            stmt = stmt.where(Interview.interview_date <= to_date.strip())
        if search and search.strip():
            from sqlalchemy import and_
            words = [w for w in search.strip().split() if w]
            intv_conditions = []
            for word in words:
                w_term = f"%{word}%"
                intv_conditions.append(
                    or_(
                        Candidate.full_name.ilike(w_term),
                        Candidate.email.ilike(w_term),
                        Candidate.phone.ilike(w_term),
                        Candidate.telegram_username.ilike(w_term),
                        Vacancy.title.ilike(w_term),
                        Interview.interview_location.ilike(w_term),
                        Interview.interviewer_name.ilike(w_term)
                    )
                )
            stmt = stmt.where(and_(*intv_conditions))

        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_upcoming_interviews(session: AsyncSession, limit: int = 5) -> List[Interview]:
        today_cambodia = get_current_cambodia_time().date().strftime("%Y-%m-%d")
        stmt = (
            select(Interview)
            .where(
                Interview.status.in_(["Scheduled", "Confirmed", "Reschedule Requested"]),
                Interview.interview_date >= today_cambodia
            )
            .options(
                selectinload(Interview.application),
                selectinload(Interview.candidate),
                selectinload(Interview.vacancy)
            )
            .order_by(Interview.interview_date.asc(), desc(Interview.created_at))
            .limit(limit)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

interview_service = InterviewService()
