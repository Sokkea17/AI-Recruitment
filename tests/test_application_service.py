import time
import pytest
from app.database import init_db, async_session_factory
from app.services.vacancy_service import vacancy_service
from app.services.application_service import application_service
from app.schemas.vacancy import VacancyCreate
from app.schemas.application import ApplicationCreate

@pytest.mark.asyncio
async def test_application_lifecycle_and_duplicates():
    await init_db()
    # Generate unique test candidate ID for idempotency
    candidate_tg_id = int(time.time() * 1000) % 1000000000

    async with async_session_factory() as session:
        # 1. Create a published vacancy
        vac_data = VacancyCreate(
            title=f"Legal Executive {candidate_tg_id}",
            department="Legal",
            requirements="LL.B degree, 3+ years experience in corporate law."
        )
        vacancy = await vacancy_service.create_vacancy(vac_data, session)
        await vacancy_service.publish_vacancy(vacancy.id, session)

        # 2. Candidate submits application with a mock PDF CV
        mock_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        app_data = ApplicationCreate(
            vacancy_id=vacancy.id,
            telegram_user_id=candidate_tg_id,
            telegram_username=f"john_{candidate_tg_id}",
            full_name="John Smith",
            phone="+855 12 999 888",
            email="john.smith@example.com",
            cv_original_filename="John_Smith_CV.pdf",
            cv_bytes=mock_pdf
        )

        app1 = await application_service.submit_application(app_data, session)
        assert app1.id is not None
        assert app1.application_code.startswith("APP-")
        assert app1.status == "New"
        assert app1.vacancy_id == vacancy.id

        # 3. Check duplicate detection
        duplicate = await application_service.check_duplicate(candidate_tg_id, vacancy.id, session)
        assert duplicate is not None
        assert duplicate.id == app1.id

        # 4. Candidate submits updated CV for the SAME position
        updated_mock_pdf = b"%PDF-1.4\n% Updated CV\n%%EOF"
        updated_app_data = ApplicationCreate(
            vacancy_id=vacancy.id,
            telegram_user_id=candidate_tg_id,
            telegram_username=f"john_{candidate_tg_id}",
            full_name="John Smith",
            phone="+855 12 999 888",
            email="john.smith@example.com",
            cv_original_filename="John_Smith_CV_v2.pdf",
            cv_bytes=updated_mock_pdf
        )

        app1_updated = await application_service.submit_application(
            updated_app_data,
            session,
            is_update=True
        )
        assert app1_updated.id == app1.id
        assert app1_updated.duplicate_submission_count == 1
        assert app1_updated.cv_original_filename == "John_Smith_CV_v2.pdf"

        # 5. Candidate applies for a DIFFERENT position (Multiple positions allowed)
        vac2_data = VacancyCreate(
            title=f"HR Executive {candidate_tg_id}",
            department="HR & Admin"
        )
        vacancy2 = await vacancy_service.create_vacancy(vac2_data, session)
        await vacancy_service.publish_vacancy(vacancy2.id, session)

        app2_data = ApplicationCreate(
            vacancy_id=vacancy2.id,
            telegram_user_id=candidate_tg_id,
            telegram_username=f"john_{candidate_tg_id}",
            full_name="John Smith",
            phone="+855 12 999 888",
            email="john.smith@example.com",
            cv_original_filename="John_Smith_HR_CV.pdf",
            cv_bytes=mock_pdf
        )

        app2 = await application_service.submit_application(app2_data, session)
        assert app2.id != app1.id
        assert app2.vacancy_id == vacancy2.id
        assert app2.application_code != app1.application_code

        # 6. Candidate status lookup (/myapplications)
        candidate_apps = await application_service.get_candidate_applications(session, candidate_tg_id)
        assert len(candidate_apps) == 2
        vac_ids = [a.vacancy_id for a in candidate_apps]
        assert vacancy.id in vac_ids
        assert vacancy2.id in vac_ids

        # 7. HR updates status
        updated_status_app = await application_service.update_status(
            session,
            app1.id,
            new_status="Shortlisted",
            hr_notes="Strong candidate with good background."
        )
        assert updated_status_app.status == "Shortlisted"
        assert updated_status_app.hr_notes == "Strong candidate with good background."
