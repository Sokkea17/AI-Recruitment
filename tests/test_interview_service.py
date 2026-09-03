import pytest
import uuid
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from app.database import init_db, async_session_factory
from app.models import Vacancy, Candidate, Application, Interview
from app.services.interview_service import interview_service
from app.bot.handlers.interview_response import candidate_interview_response_callback
from app.utils.formatters import get_current_cambodia_time

def get_unique_uid():
    return int(time.time() * 1000) % 2147483647

@pytest.mark.asyncio
async def test_interview_scheduling_and_past_date_validation():
    await init_db()

    uid = get_unique_uid()
    async with async_session_factory() as session:
        cand = Candidate(
            telegram_user_id=uid,
            full_name=f"Alice {uid}",
            phone="+855 12 999 888",
            email=f"alice_{uid}@test.local"
        )
        session.add(cand)

        vac = Vacancy(
            vacancy_code=f"VAC-{uid}",
            title="Senior Network Specialist",
            department="NOC",
            status="Published"
        )
        session.add(vac)
        await session.commit()
        await session.refresh(cand)
        await session.refresh(vac)

        app = Application(
            application_code=f"APP-{uid}",
            candidate_id=cand.id,
            vacancy_id=vac.id,
            cv_file_path="/tmp/test.pdf",
            cv_original_filename="test.pdf",
            status="Shortlisted"
        )
        session.add(app)
        await session.commit()
        await session.refresh(app)

        # 1. Past date validation failure
        past_date = (get_current_cambodia_time().date() - timedelta(days=2)).strftime("%Y-%m-%d")
        inv_fail, err = await interview_service.schedule_interview(
            session=session,
            application_id=app.id,
            interview_date=past_date,
            interview_time="10:00 AM",
            interview_type="In-person",
            interview_location="ADC Office, Phnom Penh",
            send_invitation=False
        )
        assert inv_fail is None
        assert "cannot be in the past" in err

        # 2. Valid upcoming date
        future_date = (get_current_cambodia_time().date() + timedelta(days=3)).strftime("%Y-%m-%d")
        inv, err = await interview_service.schedule_interview(
            session=session,
            application_id=app.id,
            interview_date=future_date,
            interview_time="02:30 PM",
            interview_type="In-person",
            interview_location="ADC Office, Phnom Penh",
            interviewer_name="HR Director",
            notes="Please bring identity card",
            send_invitation=False
        )
        assert inv is not None
        assert inv.status == "Scheduled"
        assert inv.interview_location == "ADC Office, Phnom Penh"
        assert inv.interviewer_name == "HR Director"
        assert app.status == "Interview Scheduled"

@pytest.mark.asyncio
async def test_interview_edit_complete_and_cancel():
    await init_db()

    uid = get_unique_uid() + 10
    async with async_session_factory() as session:
        cand = Candidate(
            telegram_user_id=uid,
            full_name=f"Bob {uid}",
            phone="+855 12 999 777",
            email=f"bob_{uid}@test.local"
        )
        session.add(cand)

        vac = Vacancy(
            vacancy_code=f"VAC-{uid}",
            title="HR Generalist",
            department="HR",
            status="Published"
        )
        session.add(vac)
        await session.commit()
        await session.refresh(cand)
        await session.refresh(vac)

        app = Application(
            application_code=f"APP-{uid}",
            candidate_id=cand.id,
            vacancy_id=vac.id,
            cv_file_path="/tmp/test.pdf",
            cv_original_filename="test.pdf",
            status="Shortlisted"
        )
        session.add(app)
        await session.commit()
        await session.refresh(app)

        future_date = (get_current_cambodia_time().date() + timedelta(days=2)).strftime("%Y-%m-%d")
        inv, _ = await interview_service.schedule_interview(
            session=session,
            application_id=app.id,
            interview_date=future_date,
            interview_time="09:00 AM",
            interview_type="Online",
            interview_location="Google Meet",
            meeting_link="https://meet.google.com/abc-def-ghi",
            send_invitation=False
        )
        assert inv is not None

        # 1. Edit interview
        resched_date = (get_current_cambodia_time().date() + timedelta(days=5)).strftime("%Y-%m-%d")
        edited, _ = await interview_service.edit_interview(
            session=session,
            interview_id=inv.id,
            interview_date=resched_date,
            interview_time="11:00 AM",
            interview_type="Online",
            interview_location="Google Meet",
            meeting_link="https://meet.google.com/xyz",
            send_update=False
        )
        assert edited.interview_date == resched_date
        assert edited.interview_time == "11:00 AM"
        assert edited.meeting_link == "https://meet.google.com/xyz"

        # 2. Mark completed
        completed, _ = await interview_service.mark_completed(session, inv.id)
        assert completed.status == "Completed"
        assert app.status == "Interview Completed"

        # 3. Cancel
        cancelled, _ = await interview_service.cancel_interview(session, inv.id, send_cancellation=False)
        assert cancelled.status == "Cancelled"

@pytest.mark.asyncio
async def test_candidate_telegram_response_callback():
    await init_db()

    uid = get_unique_uid() + 20
    async with async_session_factory() as session:
        cand = Candidate(
            telegram_user_id=uid,
            full_name=f"Charlie {uid}",
            phone="+855 12 999 666",
            email=f"charlie_{uid}@test.local"
        )
        session.add(cand)

        vac = Vacancy(
            vacancy_code=f"VAC-{uid}",
            title="Database Administrator",
            department="IT",
            status="Published"
        )
        session.add(vac)
        await session.commit()
        await session.refresh(cand)
        await session.refresh(vac)

        app = Application(
            application_code=f"APP-{uid}",
            candidate_id=cand.id,
            vacancy_id=vac.id,
            cv_file_path="/tmp/test.pdf",
            cv_original_filename="test.pdf",
            status="Shortlisted"
        )
        session.add(app)
        await session.commit()
        await session.refresh(app)

        future_date = (get_current_cambodia_time().date() + timedelta(days=2)).strftime("%Y-%m-%d")
        inv, _ = await interview_service.schedule_interview(
            session=session,
            application_id=app.id,
            interview_date=future_date,
            interview_time="10:30 AM",
            interview_type="In-person",
            interview_location="ADC Office",
            send_invitation=False
        )
        inv_id = inv.id

    # 1. Simulate Confirm callback
    mock_update = MagicMock()
    mock_query = AsyncMock()
    mock_query.data = f"intv_confirm_{inv_id}"
    mock_update.callback_query = mock_query

    mock_context = MagicMock()
    mock_bot = AsyncMock()
    mock_context.bot = mock_bot

    await candidate_interview_response_callback(mock_update, mock_context)

    async with async_session_factory() as verify_session:
        updated_inv = await interview_service.get_interview_by_id(verify_session, inv_id)
        assert updated_inv.status == "Confirmed"
        assert updated_inv.application.status == "Interview Confirmed"
    mock_query.edit_message_text.assert_called_once()

    # 2. Simulate Reschedule callback
    mock_query.reset_mock()
    mock_query.data = f"intv_resched_{inv_id}"
    await candidate_interview_response_callback(mock_update, mock_context)

    async with async_session_factory() as verify_session:
        updated_inv = await interview_service.get_interview_by_id(verify_session, inv_id)
        assert updated_inv.status == "Reschedule Requested"
        assert updated_inv.application.status == "Reschedule Requested"

    # 3. Simulate Decline callback
    mock_query.reset_mock()
    mock_query.data = f"intv_decline_{inv_id}"
    await candidate_interview_response_callback(mock_update, mock_context)

    async with async_session_factory() as verify_session:
        updated_inv = await interview_service.get_interview_by_id(verify_session, inv_id)
        assert updated_inv.status == "Declined"
        assert updated_inv.application.status == "Interview Declined"

from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_interview_web_endpoints_flow():
    await init_db()

    uid = get_unique_uid() + 30
    async with async_session_factory() as session:
        cand = Candidate(
            telegram_user_id=uid,
            full_name=f"Daisy Web {uid}",
            phone="+855 12 999 555",
            email=f"daisy_{uid}@test.local"
        )
        session.add(cand)

        vac = Vacancy(
            vacancy_code=f"VAC-{uid}",
            title="Senior DevOps Engineer",
            department="Cloud",
            status="Published"
        )
        session.add(vac)
        await session.commit()
        await session.refresh(cand)
        await session.refresh(vac)

        app_rec = Application(
            application_code=f"APP-{uid}",
            candidate_id=cand.id,
            vacancy_id=vac.id,
            cv_file_path="/tmp/test.pdf",
            cv_original_filename="test.pdf",
            status="Shortlisted"
        )
        session.add(app_rec)
        await session.commit()
        await session.refresh(app_rec)
        app_id = app_rec.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Login
        login_resp = await client.post(
            "/login",
            data={"username": "admin", "password": "admin123"},
            follow_redirects=False
        )
        assert login_resp.status_code in [302, 303]
        cookies = login_resp.cookies

        # 1. Schedule Interview via Web Route
        future_date = (get_current_cambodia_time().date() + timedelta(days=3)).strftime("%Y-%m-%d")
        sched_resp = await client.post(
            f"/applications/{app_id}/interview/schedule",
            data={
                "interview_date": future_date,
                "interview_time": "10:00 AM",
                "interview_type": "In-person",
                "interview_location": "ADC Office, Phnom Penh",
                "interviewer_name": "VP of Engineering",
                "notes": "Technical coding round",
                "send_invitation": False
            },
            cookies=cookies,
            follow_redirects=False
        )
        assert sched_resp.status_code in [302, 303]

        # 2. View Application Detail to see Interview Card
        detail_resp = await client.get(f"/applications/{app_id}", cookies=cookies)
        assert detail_resp.status_code == 200
        assert "Interview Management" in detail_resp.text
        assert "ADC Office, Phnom Penh" in detail_resp.text
        assert "VP of Engineering" in detail_resp.text
        assert "Technical coding round" in detail_resp.text

        # 3. Complete Interview
        async with async_session_factory() as session:
            intvs = await interview_service.get_interviews_for_application(session, app_id)
            intv_id = intvs[0].id

        comp_resp = await client.post(
            f"/applications/{app_id}/interview/{intv_id}/complete",
            cookies=cookies,
            follow_redirects=False
        )
        assert comp_resp.status_code in [302, 303]

        # Verify application status
        detail_after = await client.get(f"/applications/{app_id}", cookies=cookies)
        assert "Interview Completed" in detail_after.text
