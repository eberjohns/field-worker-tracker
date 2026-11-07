"""API routes."""

from fastapi import APIRouter

from fw.api.audit import router as audit_router
from fw.api.auth import router as auth_router
from fw.api.devices import router as devices_router
from fw.api.employees import router as employees_router
from fw.api.imports import router as imports_router
from fw.api.jobs import router as jobs_router
from fw.api.org_entities import router as org_entities_router
from fw.api.salary import router as salary_router
from fw.api.scheduling import router as scheduling_router
from fw.api.settings import router as settings_router
from fw.api.users import router as users_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(employees_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(org_entities_router)
api_v1_router.include_router(devices_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(settings_router)
api_v1_router.include_router(imports_router)
api_v1_router.include_router(salary_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(scheduling_router)

__all__ = ["api_v1_router"]
