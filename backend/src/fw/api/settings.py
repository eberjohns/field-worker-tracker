from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.audit import AuditService
from fw.modules.identity import User, get_current_user, hash_password, require_role
from fw.modules.org import OrgService, ScopeService
from fw.modules.settings import (
    CompanySettingRead,
    CompanySettingUpdate,
    ConsentPolicyCreate,
    ConsentPolicyRead,
    MatchedRuleExplanationRead,
    PublicHolidayCreate,
    PublicHolidayRead,
    SettingsService,
    TimeRuleCreate,
    TimeRuleRead,
    TimeRuleResolveResponse,
    TimeRuleUpdate,
    WinningFieldSourceRead,
)
from fw.rules.time_rules import WorkerContext

router = APIRouter(tags=["settings"])


# --- Company Settings ---


@router.get("/settings", response_model=list[CompanySettingRead])
async def list_resolved_settings(
    country: str | None = None,
    as_of: date | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[CompanySettingRead]:
    settings = await SettingsService.list_settings_resolved(
        session=session, country=country, as_of=as_of
    )
    return [CompanySettingRead.model_validate(s) for s in settings]


@router.put("/settings/{key}", response_model=CompanySettingRead)
async def update_setting(
    key: str,
    payload: CompanySettingUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> CompanySettingRead:
    row = await SettingsService.set_setting(
        session=session,
        key=key,
        value=payload.value,
        country=payload.country,
        effective_from=payload.effective_from,
        unit=payload.unit,
        created_by_user_id=current_user.id,
    )
    await AuditService.log_action(
        session=session,
        action="UPDATE_SETTING",
        entity_type="company_setting",
        entity_id=f"{key}:{payload.country or 'GLOBAL'}",
        diff={
            "key": key,
            "country": payload.country,
            "value": payload.value,
            "effective_from": str(row.effective_from),
        },
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    await session.commit()
    return CompanySettingRead.model_validate(row)


@router.get("/settings/{key}/history", response_model=list[CompanySettingRead])
async def get_setting_history(
    key: str,
    country: str | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[CompanySettingRead]:
    rows = await SettingsService.get_setting_history(session=session, key=key, country=country)
    return [CompanySettingRead.model_validate(r) for r in rows]


# --- Time Rules ---


@router.get("/time-rules", response_model=list[TimeRuleRead])
async def list_time_rules(
    scope_type: str | None = None,
    country: str | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TimeRuleRead]:
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    rules = await SettingsService.list_time_rules(
        session=session,
        scope_type=scope_type,
        country=country,
        scoped_employee_ids=scoped_ids,
    )
    return [TimeRuleRead.model_validate(r) for r in rules]


@router.post("/time-rules", response_model=TimeRuleRead, status_code=status.HTTP_201_CREATED)
async def create_time_rule(
    payload: TimeRuleCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TimeRuleRead:
    if current_user.role not in ("ADMIN", "ENGINEER"):
        raise AppError(
            code="FORBIDDEN",
            message="Only Admin or Engineers can create time rules.",
            status_code=403,
        )

    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    rule = await SettingsService.create_time_rule(
        session=session,
        payload=payload,
        user_id=current_user.id,
        user_role=current_user.role,
        scoped_employee_ids=scoped_ids,
    )
    await AuditService.log_action(
        session=session,
        action="CREATE_TIME_RULE",
        entity_type="time_rule",
        entity_id=str(rule.id),
        diff={
            "name": rule.name,
            "scope_type": rule.scope_type,
            "scope_employee_id": str(rule.scope_employee_id) if rule.scope_employee_id else None,
            "start_date": str(rule.start_date),
            "applies_to": rule.applies_to,
        },
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    await session.commit()
    return TimeRuleRead.model_validate(rule)


@router.patch("/time-rules/{rule_id}", response_model=TimeRuleRead)
async def update_time_rule(
    rule_id: UUID,
    payload: TimeRuleUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TimeRuleRead:
    if current_user.role not in ("ADMIN", "ENGINEER"):
        raise AppError(
            code="FORBIDDEN",
            message="Only Admin or Engineers can edit time rules.",
            status_code=403,
        )

    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    rule = await SettingsService.update_time_rule(
        session=session,
        rule_id=rule_id,
        payload=payload,
        user_role=current_user.role,
        scoped_employee_ids=scoped_ids,
    )
    await AuditService.log_action(
        session=session,
        action="UPDATE_TIME_RULE",
        entity_type="time_rule",
        entity_id=str(rule.id),
        diff=payload.model_dump(exclude_unset=True),
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    await session.commit()
    return TimeRuleRead.model_validate(rule)


@router.delete("/time-rules/{rule_id}", response_model=TimeRuleRead)
async def delete_time_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TimeRuleRead:
    if current_user.role not in ("ADMIN", "ENGINEER"):
        raise AppError(
            code="FORBIDDEN",
            message="Only Admin or Engineers can delete time rules.",
            status_code=403,
        )

    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    rule = await SettingsService.delete_time_rule(
        session=session,
        rule_id=rule_id,
        user_role=current_user.role,
        scoped_employee_ids=scoped_ids,
    )
    await AuditService.log_action(
        session=session,
        action="DEACTIVATE_TIME_RULE",
        entity_type="time_rule",
        entity_id=str(rule.id),
        diff={"is_active": False},
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    await session.commit()
    return TimeRuleRead.model_validate(rule)


@router.get("/time-rules/resolve", response_model=TimeRuleResolveResponse)
async def resolve_time_rules(
    employee_id: UUID = Query(...),
    date_val: date = Query(default_factory=lambda: datetime.now(UTC).date(), alias="date"),
    is_outdoor: bool | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TimeRuleResolveResponse:
    """Resolve 5-point planned schedule and explain which rule won."""
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    employee = await OrgService.get_employee(
        session=session, employee_id=employee_id, scoped_ids=scoped_ids
    )
    reporting_lines = await OrgService.list_reporting_lines(
        session=session, employee_id=employee_id
    )

    worker_ctx = WorkerContext(
        employee_id=employee.id,
        country=employee.country,
        is_driver=employee.is_driver,
        has_accommodation=employee.accommodation_id is not None,
        manager_links=[(rl.manager_id, rl.relationship) for rl in reporting_lines],
    )

    resolved = await SettingsService.resolve_worker_schedule(
        session=session,
        worker=worker_ctx,
        target_date=date_val,
        is_outdoor=is_outdoor,
    )

    winning_sources_read = {
        k: WinningFieldSourceRead(
            rule_id=v.rule_id,
            rule_name=v.rule_name,
            scope_type=v.scope_type,
            field_name=v.field_name,
            value=v.value,
        )
        for k, v in resolved.winning_sources.items()
    }

    matched_rules_read = [
        MatchedRuleExplanationRead(
            rule_id=m.rule_id,
            rule_name=m.rule_name,
            scope_type=m.scope_type,
            applies_to=m.applies_to,
            priority_score=m.priority_score,
            is_match=m.is_match,
            status=m.status,
            reasons=m.reasons,
        )
        for m in resolved.matched_rules
    ]

    return TimeRuleResolveResponse(
        employee_id=employee.id,
        date=date_val,
        is_outdoor=is_outdoor,
        accommodation_start=resolved.accommodation_start,
        first_site_start=resolved.first_site_start,
        break_minutes=resolved.break_minutes,
        last_site_end=resolved.last_site_end,
        accommodation_end=resolved.accommodation_end,
        planned_total_minutes=resolved.planned_total_minutes,
        planned_worked_minutes=resolved.planned_worked_minutes,
        standard_hours_change_minutes=resolved.standard_hours_change_minutes,
        has_accommodation=resolved.has_accommodation,
        winning_rule_id=resolved.winning_rule_id,
        winning_rule_name=resolved.winning_rule_name,
        winning_sources=winning_sources_read,
        matched_rules=matched_rules_read,
    )


# --- Public Holidays ---


@router.get("/public-holidays", response_model=list[PublicHolidayRead])
async def list_public_holidays(
    country: str | None = None,
    year: int | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[PublicHolidayRead]:
    holidays = await SettingsService.list_public_holidays(
        session=session, country=country, year=year
    )
    return [PublicHolidayRead.model_validate(h) for h in holidays]


@router.post(
    "/public-holidays", response_model=PublicHolidayRead, status_code=status.HTTP_201_CREATED
)
async def create_public_holiday(
    payload: PublicHolidayCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> PublicHolidayRead:
    holiday = await SettingsService.create_public_holiday(
        session=session, payload=payload, user_id=current_user.id
    )
    await AuditService.log_action(
        session=session,
        action="CREATE_PUBLIC_HOLIDAY",
        entity_type="public_holiday",
        entity_id=str(holiday.id),
        diff={
            "holiday_date": str(holiday.holiday_date),
            "name": holiday.name,
            "country": holiday.country,
        },
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    await session.commit()
    return PublicHolidayRead.model_validate(holiday)


@router.delete("/public-holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_public_holiday(
    holiday_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> None:
    await SettingsService.delete_public_holiday(session=session, holiday_id=holiday_id)
    await AuditService.log_action(
        session=session,
        action="DELETE_PUBLIC_HOLIDAY",
        entity_type="public_holiday",
        entity_id=str(holiday_id),
        diff={"deleted": True},
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    await session.commit()


# --- Consent Policies ---


@router.get("/consent-policies", response_model=list[ConsentPolicyRead])
async def list_consent_policies(
    language: str | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ConsentPolicyRead]:
    policies = await SettingsService.list_consent_policies(session=session, language=language)
    return [ConsentPolicyRead.model_validate(p) for p in policies]


@router.post(
    "/consent-policies", response_model=ConsentPolicyRead, status_code=status.HTTP_201_CREATED
)
async def create_consent_policy(
    payload: ConsentPolicyCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ConsentPolicyRead:
    policy = await SettingsService.create_consent_policy(
        session=session, payload=payload, user_id=current_user.id
    )
    await AuditService.log_action(
        session=session,
        action="PUBLISH_CONSENT_POLICY",
        entity_type="consent_policy",
        entity_id=str(policy.id),
        diff={
            "version": policy.version,
            "language": policy.language,
            "title": policy.title,
        },
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    await session.commit()
    return ConsentPolicyRead.model_validate(policy)


@router.post("/settings/reset-database", response_model=dict[str, str])
async def reset_database(
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Reset database to clean bootstrap state. Retains only ADMIN001 and company settings."""
    # 1. Nullify user reference in audit logs and bypass event immutability for bootstrap reset
    await session.execute(text("UPDATE audit_logs SET actor_user_id = NULL;"))
    await session.execute(text("SET LOCAL fwt.bypass_immutability = 'on';"))

    # 2. Clear transactional and master tables in strict foreign-key dependency order
    tables = [
        "pending_visits",
        "attendance_approvals",
        "attendance_comments",
        "attendance_calculations",
        "attendance_records",
        "tracking_gaps",
        "site_visits",
        "employee_last_position",
        "mobile_event_logs",
        "consent_records",
        "sync_changes",
        "alerts",
        "reassignment_requests",
        "leave_requests",
        "scheduled_work",
        "standing_assignments",
        "import_rows",
        "import_batches",
        "job_occurrences",
        "job_items",
        "worksites",
        "employee_salary",
        "employee_grade_history",
        "employee_documents",
        "employee_reporting_lines",
        "registered_devices",
        "user_sessions",
        "consent_policies",
        "time_rules",
        "company_setting_values",
        "public_holidays",
        "users",
        "employees",
        "accommodations",
        "groups",
        "zones",
    ]
    for table in tables:
        await session.execute(text(f"DELETE FROM {table};"))

    now = datetime.now(UTC)
    emp_res = await session.execute(
        text(
            """
            INSERT INTO employees (
                id, tally_id, name, email, role, country, is_driver,
                join_date, is_active, version, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), 'ADMIN001', 'System Administrator', 'admin@fieldworkertracker.local',
                'ADMIN', 'AE', false, '2026-01-01', true, 1, :now, :now
            ) RETURNING id
        """
        ),
        {"now": now},
    )
    admin_emp_id = emp_res.scalar()

    default_pwd = "ChangeMe123!"
    cred_hash = hash_password(default_pwd)
    await session.execute(
        text(
            """
            INSERT INTO users (
                id, employee_id, username, credential_hash, role,
                must_change_password, password_changed_at, is_active, version, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), :emp_id, 'ADMIN001', :cred_hash, 'ADMIN',
                false, :now, true, 1, :now, :now
            )
        """
        ),
        {"emp_id": admin_emp_id, "cred_hash": cred_hash, "now": now},
    )

    await SettingsService.set_setting(
        session,
        key="default_password",
        value=default_pwd,
        effective_from=date(2026, 1, 1),
    )
    await SettingsService.set_setting(
        session,
        key="default_password_max_days",
        value=7,
        effective_from=date(2026, 1, 1),
    )

    await session.commit()
    return {
        "status": "success",
        "message": "Database reset to clean bootstrap state. Only ADMIN001 is retained.",
    }
