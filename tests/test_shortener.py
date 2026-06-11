import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import AsyncSessionLocal

# --- Crucial Fix for "fixture 'db_session' not found" ---
# Provides a clean async session fixture for any test cases that interact
# directly with the database model schemas.
@pytest.fixture(scope="session")
async def db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()

# We mark the asyncio tests with `scope="session"` to request a shared
# event loop across tests instead of overriding the deprecated `event_loop` fixture.
@pytest.mark.asyncio(scope="session")
async def test_health_check_endpoint():
    """Verify that the health check endpoint returns 200 and checks infrastructure status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "postgres" in response.json()["infrastructure"]
    assert "redis" in response.json()["infrastructure"]

@pytest.mark.asyncio(scope="session")
async def test_ssrf_blocker_prevents_loopback():
    """Verify that the SSRF loopback safety checks prevent loopback URL creation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"long_url": "http://127.0.0.1/admin-panel"}
        response = await ac.post("/api/v1/shorten", json=payload)
    assert response.status_code == 422
    assert "blocked" in response.json()["detail"].lower()

@pytest.mark.asyncio(scope="session")
async def test_short_code_generation_and_redirect(db_session):
    """Verify that shortening a URL successfully creates a redirect that resolves correctly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Shorten a valid URL
        payload = {"long_url": "https://www.google.com"}
        response = await ac.post("/api/v1/shorten", json=payload)
        assert response.status_code == 201
        
        data = response.json()
        assert "short_code" in data
        short_code = data["short_code"]

        # 2. Test dynamic redirection
        redirect_response = await ac.get(f"/{short_code}", follow_redirects=False)
        assert redirect_response.status_code == 302
        assert redirect_response.headers["location"] == "https://www.google.com"