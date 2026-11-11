from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.config import Settings, get_settings
from fw.core.db import get_db

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    country: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    database: str


@router.api_route(
    "/health",
    methods=["GET", "HEAD"],
    response_model=HealthResponse,
    summary="Liveness check",
)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        country=settings.DEPLOYMENT_COUNTRY,
        environment=settings.APP_ENV,
    )


@router.api_route(
    "/health/ready",
    methods=["GET", "HEAD"],
    response_model=ReadinessResponse,
    responses={503: {"description": "Service not ready"}},
    summary="Readiness check",
)
async def health_ready(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    try:
        await db.execute(text("SELECT 1;"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready", "database": "connected"},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "detail": str(exc),
            },
        )
