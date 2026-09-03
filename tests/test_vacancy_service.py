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
