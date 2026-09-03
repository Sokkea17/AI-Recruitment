import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db

@pytest.mark.asyncio
async def test_auth_guard_redirects_unauthenticated():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Unauthenticated request to / should redirect to /login
        resp = await client.get("/", follow_redirects=False)
        assert resp.status_code in [302, 303, 307]
        assert "/login" in resp.headers["location"]

        # 2. Login page itself is accessible
        login_page_resp = await client.get("/login")
        assert login_page_resp.status_code == 200
        assert "HR Administrator Login" in login_page_resp.text

@pytest.mark.asyncio
async def test_successful_login_and_dashboard():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Attempt login with valid credentials
        login_resp = await client.post(
            "/login",
            data={"username": "admin", "password": "admin123"},
            follow_redirects=False
        )
        assert login_resp.status_code in [302, 303]
        assert "session_token" in login_resp.cookies

        # 2. Access dashboard with the session cookie
        dash_resp = await client.get("/", cookies=login_resp.cookies)
        assert dash_resp.status_code == 200
        assert "Recruitment Overview" in dash_resp.text
        assert "Total Applications" in dash_resp.text

        # 3. Access vacancies page
        vac_resp = await client.get("/vacancies", cookies=login_resp.cookies)
        assert vac_resp.status_code == 200
        assert "Job Vacancies" in vac_resp.text

        # 4. Access applications page
        apps_resp = await client.get("/applications", cookies=login_resp.cookies)
        assert apps_resp.status_code == 200
        assert "Candidate Applications" in apps_resp.text

        # 5. Export CSV
        csv_resp = await client.get("/applications/export/csv", cookies=login_resp.cookies)
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        assert "Application ID,Candidate Name" in csv_resp.text

        # 6. Access candidates directory
        cand_resp = await client.get("/candidates", cookies=login_resp.cookies)
        assert cand_resp.status_code == 200
        assert "Candidate Directory" in cand_resp.text

        # 7. Access settings page
        settings_resp = await client.get("/settings", cookies=login_resp.cookies)
        assert settings_resp.status_code == 200
        assert "Telegram Notifications Configuration" in settings_resp.text
