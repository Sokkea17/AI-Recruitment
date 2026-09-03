import pytest
import time
import uuid
from datetime import datetime, timedelta, time as dtime, timezone
from zoneinfo import ZoneInfo
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import init_db, async_session_factory
from app.models import Vacancy, Candidate, Application, Interview
from app.services.application_service import application_service
from app.services.vacancy_service import vacancy_service
from app.services.interview_service import interview_service
from app.utils.formatters import parse_date_range_to_utc, get_current_cambodia_time

CAMBODIA_TZ = ZoneInfo("Asia/Phnom_Penh")

def get_unique_id():
    return int(time.time() * 1000) % 2147483647

@pytest.mark.asyncio
async def test_date_range_inclusive_and_validation():
    # 1. Validation error when from_date > to_date
    f_utc, t_utc, err = parse_date_range_to_utc("2026-09-10", "2026-09-05")
    assert f_utc is None
    assert t_utc is None
    assert "From Date cannot be later than To Date" in err

    # 2. Inclusive end-of-day in Cambodia Local Time (UTC+7)
    f_utc, t_utc, err = parse_date_range_to_utc("2026-09-01", "2026-09-03")
    assert err is None
    # 2026-09-01 00:00:00 ICT is 2026-08-31 17:00:00 UTC
    assert f_utc == datetime(2026, 8, 31, 17, 0, 0)
    # 2026-09-03 23:59:59.999999 ICT is 2026-09-03 16:59:59.999999 UTC
    assert t_utc == datetime(2026, 9, 3, 16, 59, 59, 999999)

@pytest.mark.asyncio
async def test_combined_application_filters_and_date_range():
    await init_db()
    uid = get_unique_id()

    # Create distinct candidates and vacancies
    async with async_session_factory() as session:
        vac_hr = Vacancy(
            vacancy_code=f"VAC-HR-{uid}",
            title=f"HR Executive {uid}",
            department="Human Resources",
            status="Published"
        )
        vac_it = Vacancy(
            vacancy_code=f"VAC-IT-{uid}",
            title=f"Network Engineer {uid}",
            department="Information Technology",
            status="Published"
        )
        session.add_all([vac_hr, vac_it])
        await session.commit()
        await session.refresh(vac_hr)
        await session.refresh(vac_it)

        cand1 = Candidate(
            telegram_user_id=uid,
            full_name=f"John Smith {uid}",
            email=f"john_{uid}@test.local",
            phone="+855 12 111 222"
        )
        cand2 = Candidate(
            telegram_user_id=uid + 1,
            full_name=f"Maria Garcia {uid}",
            email=f"maria_{uid}@test.local",
            phone="+855 12 333 444"
        )
        session.add_all([cand1, cand2])
        await session.commit()
        await session.refresh(cand1)
        await session.refresh(cand2)

        # Application 1: HR Executive, Shortlisted, on Sep 2
        app1_time = datetime(2026, 9, 2, 8, 0, 0)
        app1 = Application(
            application_code=f"APP-HR-{uid}",
            candidate_id=cand1.id,
            vacancy_id=vac_hr.id,
            cv_file_path="/tmp/test1.pdf",
            cv_original_filename="test1.pdf",
            status="Shortlisted",
            submitted_at=app1_time
        )
        # Application 2: Network Engineer, New, on Sep 2
        app2_time = datetime(2026, 9, 2, 9, 0, 0)
        app2 = Application(
            application_code=f"APP-IT-{uid}",
            candidate_id=cand2.id,
            vacancy_id=vac_it.id,
            cv_file_path="/tmp/test2.pdf",
            cv_original_filename="test2.pdf",
            status="New",
            submitted_at=app2_time
        )
        session.add_all([app1, app2])
        await session.commit()

        f_utc, t_utc, _ = parse_date_range_to_utc("2026-09-01", "2026-09-03")

        # Test 1: Combined search (Position: HR Executive, Status: Shortlisted, Date Range: Sep 1 to Sep 3)
        res_combined = await application_service.get_applications(
            session=session,
            vacancy_id=vac_hr.id,
            status="Shortlisted",
            from_date=f_utc,
            to_date=t_utc
        )
        assert len(res_combined) == 1
        assert res_combined[0].application_code == f"APP-HR-{uid}"

        # Test 2: Filter by Department
        res_dept = await application_service.get_applications(
            session=session,
            department="Information Technology",
            from_date=f_utc,
            to_date=t_utc
        )
        assert any(a.application_code == f"APP-IT-{uid}" for a in res_dept)
        assert not any(a.application_code == f"APP-HR-{uid}" for a in res_dept)

        # Test 3: Search by candidate email
        res_search = await application_service.get_applications(
            session=session,
            search=f"john_{uid}@test.local"
        )
        assert len(res_search) == 1
        assert res_search[0].candidate.full_name == f"John Smith {uid}"

        # Test 4: Date outside range returns 0
        f_out, t_out, _ = parse_date_range_to_utc("2026-08-01", "2026-08-15")
        res_out = await application_service.get_applications(
            session=session,
            vacancy_id=vac_hr.id,
            from_date=f_out,
            to_date=t_out
        )
        assert len(res_out) == 0

@pytest.mark.asyncio
async def test_vacancies_and_candidates_filtering():
    await init_db()
    uid = get_unique_id() + 10

    async with async_session_factory() as session:
        # Create Vacancy
        vac = Vacancy(
            vacancy_code=f"VAC-FIN-{uid}",
            title=f"Chief Financial Officer {uid}",
            department="Finance",
            status="Published"
        )
        session.add(vac)

        # Create Candidate
        cand = Candidate(
            telegram_user_id=uid,
            full_name=f"Robert Finance {uid}",
            email=f"robert_{uid}@finance.local",
            phone="+855 12 777 999"
        )
        session.add(cand)
        await session.commit()

        # 1. Vacancy Filter by department & search
        vac_res = await vacancy_service.get_all_vacancies(
            session=session,
            search=f"Financial Officer {uid}",
            department="Finance",
            status_filter="Published"
        )
        assert len(vac_res) == 1
        assert vac_res[0].vacancy_code == f"VAC-FIN-{uid}"

        # 2. Departments list contains 'Finance'
        depts = await vacancy_service.get_departments(session)
        assert "Finance" in depts

        # 3. Candidate search by phone
        cand_stmt = await session.execute(
            Candidate.__table__.select().where(Candidate.phone == "+855 12 777 999")
        )
        assert cand_stmt.first() is not None

@pytest.mark.asyncio
async def test_interviews_filtering_and_dashboard_integration():
    await init_db()
    uid = get_unique_id() + 20

    async with async_session_factory() as session:
        cand = Candidate(
            telegram_user_id=uid,
            full_name=f"Elena Interviewee {uid}",
            email=f"elena_{uid}@test.local"
        )
        session.add(cand)
        vac = Vacancy(
            vacancy_code=f"VAC-SEC-{uid}",
            title=f"Cybersecurity Specialist {uid}",
            status="Published"
        )
        session.add(vac)
        await session.commit()
        await session.refresh(cand)
        await session.refresh(vac)

        app_rec = Application(
            application_code=f"APP-SEC-{uid}",
            candidate_id=cand.id,
            vacancy_id=vac.id,
            cv_file_path="/tmp/test3.pdf",
            cv_original_filename="test3.pdf",
            status="Interview Scheduled"
        )
        session.add(app_rec)
        await session.commit()
        await session.refresh(app_rec)

        # Create Interview with date 2026-09-15
        inv = Interview(
            application_id=app_rec.id,
            candidate_id=cand.id,
            vacancy_id=vac.id,
            interview_date="2026-09-15",
            interview_time="11:00 AM",
            interview_type="Online",
            interview_location="Google Meet",
            status="Confirmed",
            invitation_sent=True
        )
        session.add(inv)
        await session.commit()

        # 1. Filter Interviews by candidate name, status, type, and date range
        intv_res = await interview_service.get_all_interviews(
            session=session,
            search=f"Elena Interviewee {uid}",
            status="Confirmed",
            interview_type="Online",
            from_date="2026-09-10",
            to_date="2026-09-20"
        )
        assert len(intv_res) == 1
        assert intv_res[0].candidate.full_name == f"Elena Interviewee {uid}"

        # 2. Date filter outside interview date returns 0
        intv_empty = await interview_service.get_all_interviews(
            session=session,
            search=f"Elena Interviewee {uid}",
            from_date="2026-09-01",
            to_date="2026-09-05"
        )
        assert len(intv_empty) == 0

    # 3. Test HTTP Web Endpoints for Dashboard and Interviews
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        login_resp = await client.post(
            "/login",
            data={"username": "admin", "password": "admin123"},
            follow_redirects=False
        )
        cookies = login_resp.cookies

        # Test Dashboard with From-To filter
        dash_resp = await client.get("/?from_date=2026-09-01&to_date=2026-09-30", cookies=cookies)
        assert dash_resp.status_code == 200
        assert "Recruitment Overview" in dash_resp.text
        assert "Scheduled Interviews" in dash_resp.text
        assert "Upcoming Interviews" in dash_resp.text
        assert "Shortlisted Candidates" in dash_resp.text

        # Test Dashboard Invalid Date Range
        dash_err_resp = await client.get("/?from_date=2026-09-30&to_date=2026-09-01", cookies=cookies)
        assert dash_err_resp.status_code == 200
        assert "From Date cannot be later than To Date" in dash_err_resp.text

        # Test Central Interviews Page
        intv_page_resp = await client.get(
            f"/interviews?q=Elena&from_date=2026-09-10&to_date=2026-09-20",
            cookies=cookies
        )
        assert intv_page_resp.status_code == 200
        assert "Interview Management" in intv_page_resp.text
        assert "Elena Interviewee" in intv_page_resp.text
        assert "Google Meet" in intv_page_resp.text
        assert "Confirmed" in intv_page_resp.text
