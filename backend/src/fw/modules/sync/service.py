import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import geoalchemy2.shape
import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.adapters.push import get_push_provider
from fw.core.config import get_settings
from fw.core.errors import AppError
from fw.modules.identity import (
    AuthService,
    User,
    UserSession,
    hash_password,
    verify_password,
)
from fw.modules.jobs import JobItem, Worksite
from fw.modules.org import Accommodation, Employee, EmployeeReportingLine, RegisteredDevice
from fw.modules.scheduling import LeaveRequest, ScheduledWork
from fw.modules.settings import (
    CompanySettingValue,
    ConsentPolicy,
    PublicHoliday,
    SettingsService,
    TimeRule,
)
from fw.modules.sync.geo import compute_geofence_circle
from fw.modules.sync.models import ConsentRecord, SyncChange
from fw.modules.sync.schemas import (
    AccommodationPayload,
    DayPlanPayload,
    DayPlanPlannedTimes,
    DeviceStatusRead,
    GeofenceCircle,
    JobItemSummary,
    JobPayload,
    MobileChangePasswordRequest,
    MobileDeviceUpdateRequest,
    MobileHeartbeatRequest,
    MobileHeartbeatResponse,
    MobileLoginRequest,
    MobilePolicyResponse,
    ProfilePayload,
    ProfileSupervisor,
    ScheduleItemPayload,
    SettingsPayload,
    SnapshotEntity,
    SyncAckResponse,
    SyncChangeItem,
    SyncChangesResponse,
    SyncSnapshotResponse,
)
from fw.rules.password import is_default_password_expired, validate_password_strength

logger = structlog.get_logger(__name__)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _subtract_minutes_from_time_str(time_str: str, minutes_to_subtract: int) -> str:
    """Subtract minutes from 'HH:MM' time string, wrapping appropriately."""
    parts = time_str.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    dt = datetime(2026, 1, 1, hours, minutes, tzinfo=UTC) - timedelta(minutes=minutes_to_subtract)
    return dt.strftime("%H:%M")


def _geometry_to_geojson(geom: Any) -> dict[str, Any] | None:
    if geom is None:
        return None
    try:
        from shapely import geometry

        if isinstance(geom, dict):
            return geom
        # If it's a WKBElement or spatial column
        shapely_geom = geoalchemy2.shape.to_shape(geom)
        return geometry.mapping(shapely_geom)
    except Exception:
        return None


def _parse_int_setting(val: Any, default: int) -> int:
    if isinstance(val, dict):
        val = val.get("value", default)
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


class SyncService:
    """Core domain service for mobile sync, authentication, and change tracking."""

    @staticmethod
    async def get_latest_cursor(session: AsyncSession, employee_id: UUID) -> int:
        cursor_query = select(func.coalesce(func.max(SyncChange.id), 0)).where(
            SyncChange.employee_id == employee_id
        )
        cursor_res = await session.execute(cursor_query)
        return int(cursor_res.scalar() or 0)

    @staticmethod
    async def get_default_password(session: AsyncSession) -> str:
        query = select(CompanySettingValue).where(
            CompanySettingValue.setting_key == "mobile_default_password"
        )
        res = await session.execute(query)
        setting = res.scalar_one_or_none()
        if setting and isinstance(setting.value, dict) and "value" in setting.value:
            return str(setting.value["value"])
        if setting and isinstance(setting.value, str):
            return setting.value
        return "Welcome123!"

    @staticmethod
    async def get_sync_cursor_floor(session: AsyncSession) -> int:
        query = select(CompanySettingValue).where(
            CompanySettingValue.setting_key == "sync_cursor_floor"
        )
        res = await session.execute(query)
        setting = res.scalar_one_or_none()
        if setting and isinstance(setting.value, dict) and "value" in setting.value:
            try:
                return int(setting.value["value"])
            except (ValueError, TypeError):
                return 0
        return 0

    @staticmethod
    async def authenticate_mobile_worker(
        session: AsyncSession,
        request: MobileLoginRequest,
        default_password_max_days: int = 7,
    ) -> tuple[User, str, str, Employee, RegisteredDevice]:
        """Authenticate worker by tally ID and password, handling single-device binding."""
        now = datetime.now(UTC)
        settings = get_settings()

        # Find employee by tally_id
        emp_query = select(Employee).where(
            Employee.tally_id == request.tally_id,
            Employee.is_active.is_(True),
        )
        emp_res = await session.execute(emp_query)
        employee = emp_res.scalar_one_or_none()
        if not employee:
            raise AppError(
                code="INVALID_CREDENTIALS",
                message="Invalid employee ID or password.",
                status_code=401,
            )

        # Find user account
        user_query = select(User).where(User.username == request.tally_id)
        user_res = await session.execute(user_query)
        user = user_res.scalar_one_or_none()

        default_pwd = await SyncService.get_default_password(session)

        # Auto-provision user if employee exists and password matches default password
        if not user:
            if request.password == default_pwd:
                user = User(
                    username=employee.tally_id,
                    credential_hash=hash_password(request.password),
                    role=employee.role or "WORKER",
                    employee_id=employee.id,
                    must_change_password=True,
                    is_active=True,
                )
                session.add(user)
                await session.flush()
            else:
                raise AppError(
                    code="INVALID_CREDENTIALS",
                    message="Invalid employee ID or password.",
                    status_code=401,
                )
        else:
            # Check user password
            if not verify_password(request.password, user.credential_hash):
                raise AppError(
                    code="INVALID_CREDENTIALS",
                    message="Invalid employee ID or password.",
                    status_code=401,
                )

        if not user.is_active:
            raise AppError(
                code="ACCOUNT_DISABLED",
                message="This account is deactivated.",
                status_code=403,
            )

        if user.locked_until and user.locked_until > now:
            raise AppError(
                code="ACCOUNT_LOCKED",
                message="This account is locked. Please contact Admin.",
                status_code=403,
            )

        # Check default password expiry
        if is_default_password_expired(
            user.must_change_password,
            user.created_at,
            now,
            max_days=default_password_max_days,
        ):
            user.locked_until = now + timedelta(days=365)
            await session.flush()
            raise AppError(
                code="ACCOUNT_LOCKED",
                message="Default password was not changed in time. Account is locked.",
                status_code=403,
            )

        # Device binding verification
        dev_query = select(RegisteredDevice).where(
            RegisteredDevice.employee_id == employee.id,
            RegisteredDevice.is_active.is_(True),
        )
        dev_res = await session.execute(dev_query)
        active_device = dev_res.scalar_one_or_none()

        if active_device is None:
            # First device binding
            active_device = RegisteredDevice(
                employee_id=employee.id,
                device_identifier=request.device.device_identifier,
                platform=request.device.platform.value,
                device_model=request.device.device_model,
                app_version=request.device.app_version,
                os_version=request.device.os_version,
                push_token=request.device.push_token,
                registered_at=now,
                last_seen_at=now,
                last_acked_cursor=0,
                is_active=True,
            )
            session.add(active_device)
            await session.flush()
            logger.info(
                "device_bound_first_login",
                employee_id=str(employee.id),
                device_identifier=request.device.device_identifier,
            )
        else:
            # Check for device mismatch
            if active_device.device_identifier != request.device.device_identifier:
                logger.warning(
                    "device_mismatch_detected",
                    employee_id=str(employee.id),
                    bound_device=active_device.device_identifier,
                    attempted_device=request.device.device_identifier,
                )
                raise AppError(
                    code="DEVICE_MISMATCH",
                    message="This account is bound to another device. Contact Admin to reset binding.",
                    status_code=403,
                )
            # Update existing active device attributes
            active_device.last_seen_at = now
            if request.device.push_token is not None:
                active_device.push_token = request.device.push_token
            if request.device.app_version is not None:
                active_device.app_version = request.device.app_version
            if request.device.os_version is not None:
                active_device.os_version = request.device.os_version
            if request.device.device_model is not None:
                active_device.device_model = request.device.device_model
            await session.flush()

        user.last_login_at = now
        await session.flush()

        # Generate tokens

        access_token = AuthService.create_access_token(user)
        import secrets

        raw_refresh_token = secrets.token_urlsafe(32)
        refresh_session = UserSession(
            user_id=user.id,
            token_hash=_hash_token(raw_refresh_token),
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_DAYS),
        )
        session.add(refresh_session)
        await session.flush()

        return user, access_token, raw_refresh_token, employee, active_device

    @staticmethod
    async def change_mobile_password(
        session: AsyncSession,
        user_id: UUID,
        request: MobileChangePasswordRequest,
    ) -> User:
        query = select(User).where(User.id == user_id)
        res = await session.execute(query)
        user = res.scalar_one_or_none()
        if not user:
            raise AppError(code="USER_NOT_FOUND", message="User not found.", status_code=404)

        if not verify_password(request.old_password, user.credential_hash):
            raise AppError(
                code="INVALID_CURRENT_PASSWORD",
                message="Old password is incorrect.",
                status_code=400,
            )

        default_pwd = await SyncService.get_default_password(session)
        validate_password_strength(request.new_password, default_password=default_pwd)

        user.credential_hash = hash_password(request.new_password)
        user.must_change_password = False
        user.password_changed_at = datetime.now(UTC)
        user.locked_until = None
        user.version += 1
        await session.flush()
        return user

    @staticmethod
    async def record_heartbeat(
        session: AsyncSession,
        employee_id: UUID,
        request: MobileHeartbeatRequest,
    ) -> MobileHeartbeatResponse:
        now = datetime.now(UTC)
        # Find active device
        query = select(RegisteredDevice).where(
            RegisteredDevice.employee_id == employee_id,
            RegisteredDevice.is_active.is_(True),
        )
        res = await session.execute(query)
        device = res.scalar_one_or_none()
        if device:
            device.last_seen_at = now
            device.app_version = request.app_version
            if request.location_permission_state:
                device.location_permission_state = request.location_permission_state.value
            await session.flush()

        # Query latest cursor for this employee
        cursor_query = select(func.coalesce(func.max(SyncChange.id), 0)).where(
            SyncChange.employee_id == employee_id
        )
        cursor_res = await session.execute(cursor_query)
        latest_cursor = int(cursor_res.scalar() or 0)

        has_pending = latest_cursor > request.cursor
        return MobileHeartbeatResponse(
            server_time_utc=now,
            latest_cursor=latest_cursor,
            min_app_version="1.0.0",
            has_pending_changes=has_pending,
        )

    @staticmethod
    async def update_device_info(
        session: AsyncSession,
        employee_id: UUID,
        request: MobileDeviceUpdateRequest,
    ) -> None:
        query = select(RegisteredDevice).where(
            RegisteredDevice.employee_id == employee_id,
            RegisteredDevice.is_active.is_(True),
        )
        res = await session.execute(query)
        device = res.scalar_one_or_none()
        if not device:
            raise AppError(
                code="DEVICE_NOT_ACTIVE",
                message="No active registered device found.",
                status_code=403,
            )

        now = datetime.now(UTC)
        device.last_seen_at = now
        if request.push_token is not None:
            device.push_token = request.push_token
        if request.app_version is not None:
            device.app_version = request.app_version
        if request.os_version is not None:
            device.os_version = request.os_version
        if request.location_permission_state is not None:
            device.location_permission_state = request.location_permission_state.value
        await session.flush()

    @staticmethod
    async def record_consent(
        session: AsyncSession,
        employee_id: UUID,
        policy_version: int,
        consented_at_utc: datetime,
    ) -> ConsentRecord:
        dev_query = select(RegisteredDevice).where(
            RegisteredDevice.employee_id == employee_id,
            RegisteredDevice.is_active.is_(True),
        )
        dev_res = await session.execute(dev_query)
        device = dev_res.scalar_one_or_none()
        if not device:
            raise AppError(
                code="DEVICE_NOT_ACTIVE",
                message="No active device bound for consent recording.",
                status_code=403,
            )

        record = ConsentRecord(
            employee_id=employee_id,
            device_id=device.id,
            policy_version=policy_version,
            consented_at=consented_at_utc,
            recorded_at=datetime.now(UTC),
        )
        session.add(record)
        await session.flush()
        return record

    @staticmethod
    async def get_consent_policy(
        session: AsyncSession,
        language: str = "en",
    ) -> MobilePolicyResponse:
        query = (
            select(ConsentPolicy)
            .where(ConsentPolicy.language == language)
            .order_by(ConsentPolicy.version.desc())
        )
        res = await session.execute(query)
        policy = res.scalar_one_or_none()
        if not policy:
            # Fallback to 'en'
            fallback_query = (
                select(ConsentPolicy)
                .where(ConsentPolicy.language == "en")
                .order_by(ConsentPolicy.version.desc())
            )
            fallback_res = await session.execute(fallback_query)
            policy = fallback_res.scalar_one_or_none()

        if not policy:
            # Default placeholder policy
            return MobilePolicyResponse(
                version=1,
                language=language,
                title="Location Tracking Consent",
                body="Field Worker Tracker collects location data during working hours to verify worksite attendance.",
                published_at=datetime.now(UTC),
            )

        return MobilePolicyResponse(
            version=policy.version,
            language=policy.language,
            title=policy.title,
            body=policy.body,
            published_at=policy.published_at,
        )

    @staticmethod
    async def build_snapshot(
        session: AsyncSession,
        employee_id: UUID,
        window_days: int = 30,
    ) -> SyncSnapshotResponse:
        """Construct full current 30-day window snapshot of all synced entities."""
        now = datetime.now(UTC)

        # 1. Read cursor BEFORE assembling entities to guarantee no missed delta changes
        cursor_query = select(func.coalesce(func.max(SyncChange.id), 0)).where(
            SyncChange.employee_id == employee_id
        )
        cursor_res = await session.execute(cursor_query)
        cursor = int(cursor_res.scalar() or 0)

        # Date window
        today = now.date()
        to_date = today + timedelta(days=window_days)

        entities: list[SnapshotEntity] = []

        # 2. PROFILE
        emp_query = select(Employee).where(Employee.id == employee_id)
        emp_res = await session.execute(emp_query)
        employee = emp_res.scalar_one_or_none()
        if not employee:
            raise AppError(code="EMPLOYEE_NOT_FOUND", message="Employee not found", status_code=404)

        # Find supervisor
        rep_query = (
            select(Employee)
            .join(EmployeeReportingLine, EmployeeReportingLine.manager_id == Employee.id)
            .where(
                EmployeeReportingLine.employee_id == employee_id,
                EmployeeReportingLine.relationship == "SUPERVISOR",
            )
        )
        rep_res = await session.execute(rep_query)
        supervisor_emp = rep_res.scalar_one_or_none()
        supervisor_payload = None
        if supervisor_emp:
            supervisor_payload = ProfileSupervisor(
                name=supervisor_emp.name,
                phone=supervisor_emp.phone,
            )

        profile_payload = ProfilePayload(
            employee_id=employee.id,
            tally_id=employee.tally_id,
            name=employee.name,
            role=employee.role or "WORKER",
            staff_grade_description=employee.staff_grade_description,
            weekly_off_day=employee.weekly_off_day or "FRIDAY",
            is_driver=employee.is_driver or False,
            supervisor=supervisor_payload,
            accommodation_id=employee.accommodation_id,
        )
        entities.append(
            SnapshotEntity(
                entity_type="PROFILE",
                entity_id=str(employee.id),
                entity_version=employee.version or 1,
                payload=profile_payload.model_dump(mode="json"),
            )
        )

        # 3. SETTINGS
        raw_alarm_lead = await SettingsService.get_setting(
            session, key="day_plan_alarm_lead_minutes", country=employee.country, default=30
        )
        alarm_lead_minutes = _parse_int_setting(raw_alarm_lead, 30)

        raw_geofence_radius = await SettingsService.get_setting(
            session, key="geofence_circle_radius_m", country=employee.country, default=300
        )
        geofence_circle_radius_m = _parse_int_setting(raw_geofence_radius, 300)

        raw_approach = await SettingsService.get_setting(
            session, key="approach_polling_interval_s", country=employee.country, default=60
        )
        approach_polling_interval_s = _parse_int_setting(raw_approach, 60)

        raw_conf = await SettingsService.get_setting(
            session, key="confirmation_polling_interval_s", country=employee.country, default=300
        )
        confirmation_polling_interval_s = _parse_int_setting(raw_conf, 300)

        settings_payload = SettingsPayload(
            geofence_circle_radius_m=geofence_circle_radius_m,
            approach_polling_interval_s=approach_polling_interval_s,
            confirmation_polling_interval_s=confirmation_polling_interval_s,
            schedule_sync_window_days=window_days,
            location_policy_version=1,
            alarm_lead_minutes=alarm_lead_minutes,
            timezone="Asia/Dubai" if employee.country == "AE" else "Asia/Riyadh",
            upcoming=[],
        )
        entities.append(
            SnapshotEntity(
                entity_type="SETTINGS",
                entity_id="self",
                entity_version=1,
                payload=settings_payload.model_dump(mode="json"),
            )
        )

        # 4. ACCOMMODATION
        if employee.accommodation_id:
            acc_query = select(Accommodation).where(Accommodation.id == employee.accommodation_id)
            acc_res = await session.execute(acc_query)
            acc = acc_res.scalar_one_or_none()
            if acc:
                boundary_geojson = _geometry_to_geojson(acc.boundary)
                circle = compute_geofence_circle(boundary_geojson, extra_radius_m=300.0)
                acc_payload = AccommodationPayload(
                    accommodation_id=acc.id,
                    name=acc.name,
                    address=acc.address,
                    boundary=boundary_geojson,
                    geofence_circle=GeofenceCircle(**circle) if circle else None,
                )
                entities.append(
                    SnapshotEntity(
                        entity_type="ACCOMMODATION",
                        entity_id=str(acc.id),
                        entity_version=acc.version or 1,
                        payload=acc_payload.model_dump(mode="json"),
                    )
                )

        # 5. SCHEDULE_ITEM & JOB
        sw_query = (
            select(ScheduledWork, JobItem, Worksite)
            .join(JobItem, ScheduledWork.job_item_id == JobItem.id)
            .join(Worksite, ScheduledWork.worksite_id == Worksite.id)
            .where(
                ScheduledWork.employee_id == employee_id,
                ScheduledWork.work_date >= today,
                ScheduledWork.work_date <= to_date,
                ScheduledWork.status == "ACTIVE",
            )
            .order_by(ScheduledWork.work_date.asc(), ScheduledWork.sequence.asc())
        )
        sw_res = await session.execute(sw_query)
        rows = sw_res.all()

        seen_jobs: dict[UUID, Worksite] = {}
        working_dates: set[date] = set()

        for sw, ji, ws in rows:
            working_dates.add(sw.work_date)
            seen_jobs[ws.id] = ws

            item_summary = JobItemSummary(
                staff_grade_description=ji.staff_grade_description,
                deployment_type=ji.deployment_type or "PERMANENT",
                required_staff_count=ji.required_staff_count or 1,
                hours_per_occurrence_per_staff=float(ji.hours_per_occurrence_per_staff or 9.0),
            )

            sch_payload = ScheduleItemPayload(
                scheduled_work_id=sw.id,
                work_date=sw.work_date.isoformat(),
                sequence=sw.sequence,
                assigned_hours=float(sw.assigned_hours or 0.0),
                status=sw.status,
                job_id=sw.worksite_id,
                job_item_id=sw.job_item_id,
                sub_item_code=ji.sub_item_code,
                occurrence_id=sw.occurrence_id,
                job_item_summary=item_summary,
                source=sw.source or "PLANNED",
                is_reassignment=bool(sw.reassignment_request_id is not None),
            )
            entities.append(
                SnapshotEntity(
                    entity_type="SCHEDULE_ITEM",
                    entity_id=str(sw.id),
                    entity_version=sw.version or 1,
                    payload=sch_payload.model_dump(mode="json"),
                )
            )

        # Add unique JOB entities
        for ws in seen_jobs.values():
            boundary_geojson = _geometry_to_geojson(ws.boundary)
            circle = compute_geofence_circle(boundary_geojson, extra_radius_m=300.0)
            job_payload = JobPayload(
                job_id=ws.id,
                job_number=ws.job_number,
                job_name=ws.job_name,
                boundary=boundary_geojson,
                geofence_circle=GeofenceCircle(**circle) if circle else None,
                boundary_missing=(boundary_geojson is None),
            )
            entities.append(
                SnapshotEntity(
                    entity_type="JOB",
                    entity_id=str(ws.id),
                    entity_version=ws.version or 1,
                    payload=job_payload.model_dump(mode="json"),
                )
            )

        # 6. DAY_PLAN for each date in window
        # Query approved leaves in window
        leaves_query = select(LeaveRequest).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "APPROVED",
            LeaveRequest.from_date <= to_date,
            LeaveRequest.to_date >= today,
        )
        leaves_res = await session.execute(leaves_query)
        approved_leaves = list(leaves_res.scalars().all())

        # Query public holidays in window
        holidays_query = select(PublicHoliday).where(
            PublicHoliday.country == employee.country,
            PublicHoliday.holiday_date >= today,
            PublicHoliday.holiday_date <= to_date,
        )
        holidays_res = await session.execute(holidays_query)
        holiday_dates = {h.holiday_date for h in holidays_res.scalars().all()}

        # Load time rules for employee country
        rules_query = select(TimeRule).where(
            TimeRule.is_active.is_(True),
            or_(TimeRule.country == employee.country, TimeRule.country.is_(None)),
        )
        rules_res = await session.execute(rules_query)
        time_rules = list(rules_res.scalars().all())

        cur_date = today
        while cur_date <= to_date:
            day_str = cur_date.isoformat()
            is_leave = any(
                leave_req.from_date <= cur_date <= leave_req.to_date
                for leave_req in approved_leaves
            )
            is_holiday = cur_date in holiday_dates
            is_weekly_off = (
                cur_date.strftime("%A").upper() == (employee.weekly_off_day or "FRIDAY").upper()
            )
            is_scheduled = cur_date in working_dates

            if is_leave:
                day_payload = DayPlanPayload(
                    work_date=day_str,
                    status="LEAVE",
                    marker=None,
                    planned=None,
                    standard_hours=8,
                    alarm_time=None,
                )
            elif is_holiday:
                day_payload = DayPlanPayload(
                    work_date=day_str,
                    status="SKIPPED",
                    marker="PUBLIC_HOLIDAY",
                    planned=None,
                    standard_hours=8,
                    alarm_time=None,
                )
            elif is_weekly_off:
                day_payload = DayPlanPayload(
                    work_date=day_str,
                    status="OFF",
                    marker="WEEKLY_OFF",
                    planned=None,
                    standard_hours=8,
                    alarm_time=None,
                )
            elif is_scheduled:
                # Find matching time rule
                # Simple resolution: matching start_date/end_date if present
                acc_start = "05:00"
                site_start = "06:00"
                break_mins = 30
                site_end = "15:30"
                acc_end = "17:00"
                std_hours = 8

                for r in time_rules:
                    if r.start_date and r.end_date:
                        if not (r.start_date <= cur_date <= r.end_date):
                            continue
                    if r.accommodation_start:
                        acc_start = r.accommodation_start.strftime("%H:%M")
                    if r.first_site_start:
                        site_start = r.first_site_start.strftime("%H:%M")
                    if r.break_minutes is not None:
                        break_mins = r.break_minutes
                    if r.last_site_end:
                        site_end = r.last_site_end.strftime("%H:%M")
                    if r.accommodation_end:
                        acc_end = r.accommodation_end.strftime("%H:%M")
                    break

                alarm_time = _subtract_minutes_from_time_str(acc_start, 30)
                day_payload = DayPlanPayload(
                    work_date=day_str,
                    status="WORKING",
                    marker=None,
                    planned=DayPlanPlannedTimes(
                        accommodation_start=acc_start,
                        first_site_start=site_start,
                        break_minutes=break_mins,
                        last_site_end=site_end,
                        accommodation_end=acc_end,
                    ),
                    standard_hours=std_hours,
                    alarm_time=alarm_time,
                )
            else:
                day_payload = DayPlanPayload(
                    work_date=day_str,
                    status="FREE",
                    marker=None,
                    planned=None,
                    standard_hours=8,
                    alarm_time=None,
                )

            entities.append(
                SnapshotEntity(
                    entity_type="DAY_PLAN",
                    entity_id=day_str,
                    entity_version=1,
                    payload=day_payload.model_dump(mode="json"),
                )
            )
            cur_date += timedelta(days=1)

        return SyncSnapshotResponse(
            cursor=cursor,
            generated_at=now,
            server_time_utc=now,
            window={"from": today.isoformat(), "to": to_date.isoformat()},
            entities=entities,
        )

    @staticmethod
    async def get_changes(
        session: AsyncSession,
        employee_id: UUID,
        cursor: int,
        limit: int = 200,
    ) -> SyncChangesResponse:
        """Fetch coalesced delta changes since the provided cursor."""
        now = datetime.now(UTC)
        floor = await SyncService.get_sync_cursor_floor(session)

        # Check compaction floor
        if cursor < floor:
            return SyncChangesResponse(
                from_cursor=cursor,
                next_cursor=cursor,
                has_more=False,
                resync_required=True,
                server_time_utc=now,
                changes=[],
            )

        # Query changes for this employee
        query = (
            select(SyncChange)
            .where(
                SyncChange.employee_id == employee_id,
                SyncChange.id > cursor,
            )
            .order_by(SyncChange.id.asc())
            .limit(limit)
        )
        res = await session.execute(query)
        raw_changes = list(res.scalars().all())

        has_more = len(raw_changes) == limit
        next_cursor = raw_changes[-1].id if raw_changes else cursor

        # Coalesce changes: keep only the latest change per (entity_type, entity_id)
        coalesced: dict[tuple[str, str], SyncChange] = {}
        for c in raw_changes:
            coalesced[(c.entity_type, c.entity_id)] = c

        changes_list = [
            SyncChangeItem(
                cursor=c.id,
                entity_type=c.entity_type,
                entity_id=c.entity_id,
                entity_version=c.entity_version,
                op=c.op,
                priority=c.priority,
                payload=c.payload,
            )
            for c in coalesced.values()
        ]
        # Preserve sorted cursor order
        changes_list.sort(key=lambda x: x.cursor)

        return SyncChangesResponse(
            from_cursor=cursor,
            next_cursor=next_cursor,
            has_more=has_more,
            resync_required=False,
            server_time_utc=now,
            changes=changes_list,
        )

    @staticmethod
    async def acknowledge_sync(
        session: AsyncSession,
        employee_id: UUID,
        cursor: int,
    ) -> SyncAckResponse:
        now = datetime.now(UTC)
        query = select(RegisteredDevice).where(
            RegisteredDevice.employee_id == employee_id,
            RegisteredDevice.is_active.is_(True),
        )
        res = await session.execute(query)
        device = res.scalar_one_or_none()
        if device:
            if cursor > device.last_acked_cursor:
                device.last_acked_cursor = cursor
            device.last_seen_at = now
            await session.flush()

        return SyncAckResponse(
            status="ACKNOWLEDGED",
            last_acked_cursor=cursor,
            server_time_utc=now,
        )

    @staticmethod
    async def write_sync_change(
        session: AsyncSession,
        employee_id: UUID,
        entity_type: str,
        entity_id: str,
        op: str,
        payload: dict[str, Any] | None,
        entity_version: int = 1,
        priority: int = 0,
    ) -> SyncChange:
        """Write a sync_changes row synchronously inside the caller's transaction."""
        change = SyncChange(
            employee_id=employee_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_version=entity_version,
            op=op,
            payload=payload,
            priority=priority,
            created_at=datetime.now(UTC),
        )
        session.add(change)
        await session.flush()

        # Attempt silent push nudge
        dev_query = select(RegisteredDevice).where(
            RegisteredDevice.employee_id == employee_id,
            RegisteredDevice.is_active.is_(True),
        )
        dev_res = await session.execute(dev_query)
        device = dev_res.scalar_one_or_none()
        if device and device.push_token:
            push = get_push_provider()
            await push.send_silent(
                device.push_token,
                {"type": "SYNC", "latest_cursor": change.id, "priority": priority},
            )

        return change

    @staticmethod
    async def list_devices_status(
        session: AsyncSession,
    ) -> list[DeviceStatusRead]:
        """List registered devices for dashboard tracking."""
        query = (
            select(RegisteredDevice, Employee)
            .join(Employee, RegisteredDevice.employee_id == Employee.id)
            .order_by(RegisteredDevice.registered_at.desc())
        )
        res = await session.execute(query)
        rows = res.all()

        results: list[DeviceStatusRead] = []
        for dev, emp in rows:
            # Query max cursor for employee
            c_query = select(func.coalesce(func.max(SyncChange.id), 0)).where(
                SyncChange.employee_id == emp.id
            )
            c_res = await session.execute(c_query)
            current_cursor = int(c_res.scalar() or 0)
            sync_lag = max(0, current_cursor - dev.last_acked_cursor)

            results.append(
                DeviceStatusRead(
                    device_id=dev.id,
                    employee_id=emp.id,
                    tally_id=emp.tally_id,
                    employee_name=emp.name,
                    platform=dev.platform,
                    device_model=dev.device_model,
                    app_version=dev.app_version,
                    os_version=dev.os_version,
                    last_seen_at=dev.last_seen_at,
                    last_acked_cursor=dev.last_acked_cursor,
                    current_cursor=current_cursor,
                    sync_lag=sync_lag,
                    location_permission_state=dev.location_permission_state,
                    is_active=dev.is_active,
                    revoked_at=dev.revoked_at,
                )
            )
        return results

    @staticmethod
    async def reset_device_binding(
        session: AsyncSession,
        device_id: UUID,
        admin_user_id: UUID,
    ) -> RegisteredDevice:
        """Admin resets a device binding so a worker can register a new phone."""
        query = select(RegisteredDevice).where(RegisteredDevice.id == device_id)
        res = await session.execute(query)
        device = res.scalar_one_or_none()
        if not device:
            raise AppError(code="DEVICE_NOT_FOUND", message="Device not found", status_code=404)

        now = datetime.now(UTC)
        device.is_active = False
        device.revoked_at = now
        device.revoked_by_user_id = admin_user_id
        await session.flush()

        logger.info(
            "device_binding_reset_by_admin",
            device_id=str(device_id),
            employee_id=str(device.employee_id),
            admin_user_id=str(admin_user_id),
        )
        return device
