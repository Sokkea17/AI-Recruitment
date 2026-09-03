import pytest
from app.database import init_db, async_session_factory
from app.services.vacancy_service import vacancy_service
from app.schemas.vacancy import VacancyCreate, VacancyUpdate

@pytest.mark.asyncio
async def test_vacancy_lifecycle():
    await init_db()
    async with async_session_factory() as session:
        # 1. Create Vacancy
        create_data = VacancyCreate(
            title="HR Executive",
            department="HR & Admin",
            location="Phnom Penh",
            employment_type="Full-time",
            salary_range="$600 - $900",
            short_description="Handle HR operations and recruitment.",
            requirements="Bachelor's degree in HR or relevant field."
        )
        vacancy = await vacancy_service.create_vacancy(create_data, session)
        assert vacancy.id is not None
        assert vacancy.status == "Draft"
        assert vacancy.vacancy_code.startswith("VAC-")
        assert vacancy.title == "HR Executive"

        vac_id = vacancy.id

        # 2. Check published list (should be empty for Draft)
        published = await vacancy_service.get_published_vacancies(session)
        assert not any(v.id == vac_id for v in published)

        # 3. Publish vacancy
        published_vac = await vacancy_service.publish_vacancy(vac_id, session)
        assert published_vac.status == "Published"

        # 4. Verify in published vacancies
        published_now = await vacancy_service.get_published_vacancies(session)
        assert any(v.id == vac_id for v in published_now)

        # 5. Update vacancy
        updated_vac = await vacancy_service.update_vacancy(
            vac_id,
            VacancyUpdate(salary_range="$700 - $1,000"),
            session
        )
        assert updated_vac.salary_range == "$700 - $1,000"

        # 6. Close vacancy
        closed_vac = await vacancy_service.close_vacancy(vac_id, session)
        assert closed_vac.status == "Closed"

        # 7. Check published list again (closed vacancy shouldn't appear)
        published_after_close = await vacancy_service.get_published_vacancies(session)
        assert not any(v.id == vac_id for v in published_after_close)

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models import AuditLog
from sqlalchemy import select

@pytest.mark.asyncio
async def test_vacancy_deletion_and_endpoint():
    await init_db()
    async with async_session_factory() as session:
        create_data = VacancyCreate(
            title="Temporary Test Role",
            department="QA",
            requirements="Test requirements."
        )
        vac = await vacancy_service.create_vacancy(create_data, session)
        vac_id = vac.id
        assert vac_id is not None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Login
        login_resp = await client.post(
            "/login",
            data={"username": "admin", "password": "admin123"},
            follow_redirects=False
        )
        cookies = login_resp.cookies

        # 1. Delete via POST /vacancies/{id}/delete
        del_resp = await client.post(
            f"/vacancies/{vac_id}/delete",
            cookies=cookies,
            follow_redirects=False
        )
        assert del_resp.status_code in [302, 303]
        assert del_resp.headers["location"] == "/vacancies"

        # 2. Verify vacancy no longer exists in DB
        async with async_session_factory() as session:
            v_after = await vacancy_service.get_vacancy_by_id(vac_id, session)
            assert v_after is None

            # Verify audit log recorded
            audit_stmt = select(AuditLog).where(
                AuditLog.action == "VACANCY_DELETED",
                AuditLog.target_id == vac_id
            )
            audit_res = await session.execute(audit_stmt)
            audit_entry = audit_res.scalar_one_or_none()
            assert audit_entry is not None
            assert "Temporary Test Role" in audit_entry.details

        # 3. Deleting non-existent returns 404
        del_404 = await client.post(
            f"/vacancies/999999/delete",
            cookies=cookies,
            follow_redirects=False
        )
        assert del_404.status_code == 404
