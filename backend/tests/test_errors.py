import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from fw.core.errors import ProblemDetailsException
from fw.main import create_app

test_router = APIRouter()


@test_router.get("/test-problem")
async def trigger_problem():
    raise ProblemDetailsException(
        status_code=400,
        title="Invalid Operation",
        detail="Cannot perform operation on draft entity.",
        code="INVALID_ENTITY_STATE",
    )


@pytest.mark.asyncio
async def test_rfc_7807_problem_details_response():
    app = create_app()
    app.include_router(test_router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/test-problem")
        assert response.status_code == 400
        assert response.headers["content-type"] == "application/problem+json"
        body = response.json()
        assert body["type"] == "about:blank"
        assert body["title"] == "Invalid Operation"
        assert body["detail"] == "Cannot perform operation on draft entity."
        assert body["code"] == "INVALID_ENTITY_STATE"
        assert body["instance"] == "/test-problem"
