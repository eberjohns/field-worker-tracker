from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.config import get_settings
from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.events import EventBatchRequest, EventBatchResponse, EventsService
from fw.modules.identity import AuthService, User, UserService
from fw.modules.org import Employee, RegisteredDevice
from fw.modules.sync.schemas import (
    MobileChangePasswordRequest,
    MobileConsentRequest,
    MobileDeviceUpdateRequest,
    MobileEmployeeInfo,
    MobileHeartbeatRequest,
    MobileHeartbeatResponse,
    MobileLoginRequest,
    MobileLoginResponse,
    MobilePolicyResponse,
    MobileRefreshRequest,
    SyncAckRequest,
    SyncAckResponse,
    SyncChangesResponse,
    SyncSnapshotResponse,
)
from fw.modules.sync.service import SyncService

router = APIRouter(prefix="/mobile", tags=["mobile"])


async def get_mobile_auth_context(
    authorization: str | None = Header(None),
    session: AsyncSession = Depends(get_db),
    allow_password_change_pending: bool = False,
) -> tuple[User, Employee, RegisteredDevice]:
    """Validate Bearer token and ensure active device binding for mobile endpoints."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(
            code="UNAUTHENTICATED",
            message="Missing or invalid Authorization header.",
            status_code=401,
        )

    token = authorization.split(" ", 1)[1]
    settings = get_settings()

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as err:
        raise AppError(
            code="INVALID_TOKEN",
            message="Token is invalid or expired.",
            status_code=401,
        ) from err

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AppError(code="INVALID_TOKEN", message="Invalid token payload.", status_code=401)

    user = await UserService.get_by_id(session, UUID(user_id_str))
    if not user or not user.is_active:
        raise AppError(
            code="ACCOUNT_DISABLED",
            message="Account is deactivated.",
            status_code=403,
        )

    if user.must_change_password and not allow_password_change_pending:
        raise AppError(
            code="PASSWORD_CHANGE_REQUIRED",
            message="Password change is required before proceeding.",
            status_code=403,
        )

    # Find employee
    from sqlalchemy import select

    emp_query = select(Employee).where(Employee.id == user.employee_id)
    emp_res = await session.execute(emp_query)
    employee = emp_res.scalar_one_or_none()
    if not employee:
        raise AppError(code="EMPLOYEE_NOT_FOUND", message="Employee not found.", status_code=404)

    # Find active registered device
    dev_query = select(RegisteredDevice).where(
        RegisteredDevice.employee_id == employee.id,
        RegisteredDevice.is_active.is_(True),
    )
    dev_res = await session.execute(dev_query)
    device = dev_res.scalar_one_or_none()
    if not device:
        raise AppError(
            code="DEVICE_NOT_ACTIVE",
            message="Device is revoked or not registered. Re-login required.",
            status_code=403,
        )

    device.last_seen_at = datetime.now(UTC)
    await session.flush()

    return user, employee, device


async def get_current_mobile_worker(
    auth_ctx: tuple[User, Employee, RegisteredDevice] = Depends(get_mobile_auth_context),
) -> tuple[User, Employee, RegisteredDevice]:
    return auth_ctx


async def get_mobile_worker_for_password_change(
    authorization: str | None = Header(None),
    session: AsyncSession = Depends(get_db),
) -> tuple[User, Employee, RegisteredDevice]:
    return await get_mobile_auth_context(
        authorization=authorization,
        session=session,
        allow_password_change_pending=True,
    )


# 1. Login & Auth
@router.post("/auth/login", response_model=MobileLoginResponse)
async def mobile_login(
    request: MobileLoginRequest,
    session: AsyncSession = Depends(get_db),
) -> MobileLoginResponse:
    (
        user,
        access_token,
        refresh_token,
        employee,
        _device,
    ) = await SyncService.authenticate_mobile_worker(session=session, request=request)
    now = datetime.now(UTC)
    return MobileLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=900,
        server_time_utc=now,
        must_change_password=user.must_change_password,
        employee=MobileEmployeeInfo(
            employee_id=employee.id,
            tally_id=employee.tally_id,
            name=employee.name,
            role=user.role,
        ),
    )


@router.post("/auth/change-password")
async def mobile_change_password(
    request: MobileChangePasswordRequest,
    ctx: tuple[User, Employee, RegisteredDevice] = Depends(get_mobile_worker_for_password_change),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user, _emp, _dev = ctx
    await SyncService.change_mobile_password(
        session=session,
        user_id=user.id,
        request=request,
    )
    return {"status": "PASSWORD_CHANGED", "server_time_utc": datetime.now(UTC)}


@router.post("/auth/refresh")
async def mobile_refresh(
    request: MobileRefreshRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _user, access_token, new_refresh_token = await AuthService.refresh_tokens(
        session=session,
        raw_refresh_token=request.refresh_token,
    )
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "expires_in": 900,
        "server_time_utc": datetime.now(UTC),
    }


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def mobile_logout(
    request: MobileRefreshRequest,
    session: AsyncSession = Depends(get_db),
) -> None:
    await AuthService.revoke_session(session=session, raw_refresh_token=request.refresh_token)


# 2. Consent & Policy
@router.post("/consent")
async def mobile_record_consent(
    request: MobileConsentRequest,
    ctx: tuple[User, Employee, RegisteredDevice] = Depends(get_current_mobile_worker),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _user, emp, _dev = ctx
    await SyncService.record_consent(
        session=session,
        employee_id=emp.id,
        policy_version=request.policy_version,
        consented_at_utc=request.consented_at_utc,
    )
    return {"status": "CONSENT_RECORDED", "server_time_utc": datetime.now(UTC)}


@router.get("/policy/location", response_model=MobilePolicyResponse)
async def get_mobile_location_policy(
    language: str = Query(default="en"),
    session: AsyncSession = Depends(get_db),
) -> MobilePolicyResponse:
    return await SyncService.get_consent_policy(session=session, language=language)


# 3. Device & Heartbeat
@router.put("/device")
async def update_mobile_device(
    request: MobileDeviceUpdateRequest,
    ctx: tuple[User, Employee, RegisteredDevice] = Depends(get_current_mobile_worker),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _user, emp, _dev = ctx
    await SyncService.update_device_info(
        session=session,
        employee_id=emp.id,
        request=request,
    )
    return {"status": "DEVICE_UPDATED", "server_time_utc": datetime.now(UTC)}


@router.post("/heartbeat", response_model=MobileHeartbeatResponse)
async def mobile_heartbeat(
    request: MobileHeartbeatRequest,
    ctx: tuple[User, Employee, RegisteredDevice] = Depends(get_current_mobile_worker),
    session: AsyncSession = Depends(get_db),
) -> MobileHeartbeatResponse:
    _user, emp, _dev = ctx
    return await SyncService.record_heartbeat(
        session=session,
        employee_id=emp.id,
        request=request,
    )


# 4. Sync Handshake, Delta & Ack
@router.get("/sync/snapshot", response_model=SyncSnapshotResponse)
async def get_sync_snapshot(
    ctx: tuple[User, Employee, RegisteredDevice] = Depends(get_current_mobile_worker),
    session: AsyncSession = Depends(get_db),
) -> SyncSnapshotResponse:
    _user, emp, _dev = ctx
    return await SyncService.build_snapshot(
        session=session,
        employee_id=emp.id,
        window_days=30,
    )


@router.get("/sync/changes", response_model=SyncChangesResponse)
async def get_sync_changes(
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    ctx: tuple[User, Employee, RegisteredDevice] = Depends(get_current_mobile_worker),
    session: AsyncSession = Depends(get_db),
) -> SyncChangesResponse:
    _user, emp, _dev = ctx
    return await SyncService.get_changes(
        session=session,
        employee_id=emp.id,
        cursor=cursor,
        limit=limit,
    )


@router.post("/sync/ack", response_model=SyncAckResponse)
async def post_sync_ack(
    request: SyncAckRequest,
    ctx: tuple[User, Employee, RegisteredDevice] = Depends(get_current_mobile_worker),
    session: AsyncSession = Depends(get_db),
) -> SyncAckResponse:
    _user, emp, _dev = ctx
    return await SyncService.acknowledge_sync(
        session=session,
        employee_id=emp.id,
        cursor=request.cursor,
    )


# 5. Events Ingestion
@router.post("/events/batch", response_model=EventBatchResponse)
async def ingest_event_batch(
    batch: EventBatchRequest,
    ctx: tuple[User, Employee, RegisteredDevice] = Depends(get_current_mobile_worker),
    session: AsyncSession = Depends(get_db),
) -> EventBatchResponse:
    """Ingest a batch of up to 200 raw location events from a mobile device."""
    _user, employee, device = ctx
    now = datetime.now(UTC)
    results = await EventsService.ingest_batch(
        session=session,
        employee_id=employee.id,
        device_id=device.id,
        batch=batch,
    )
    latest_cursor = await SyncService.get_latest_cursor(session, employee.id)
    return EventBatchResponse(
        batch_id=batch.batch_id,
        server_time_utc=now,
        latest_cursor=latest_cursor,
        results=results,
    )
