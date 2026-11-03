from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import extract, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.errors import AppError
from fw.modules.settings.models import CompanySettingValue, ConsentPolicy, PublicHoliday, TimeRule
from fw.modules.settings.schemas import (
    ConsentPolicyCreate,
    PublicHolidayCreate,
    TimeRuleCreate,
    TimeRuleUpdate,
)
from fw.rules.time_rules import (
    ResolvedTimeSchedule,
    TimeRuleDefinition,
    WorkerContext,
)
from fw.rules.time_rules import (
    resolve_time_schedule as domain_resolve_time_schedule,
)


class SettingsService:
    @staticmethod
    async def get_setting(
        session: AsyncSession,
        key: str,
        country: str | None = None,
        as_of: date | None = None,
        default: Any = None,
    ) -> Any:
        """Resolve effective-dated company setting value for (key, country, date)."""
        target_date = as_of or datetime.now(UTC).date()

        query = (
            select(CompanySettingValue)
            .where(
                CompanySettingValue.setting_key == key,
                CompanySettingValue.effective_from <= target_date,
                or_(
                    CompanySettingValue.effective_to.is_(None),
                    CompanySettingValue.effective_to >= target_date,
                ),
            )
            .order_by(
                CompanySettingValue.country.desc().nulls_last(),
                CompanySettingValue.effective_from.desc(),
            )
        )
        if country:
            query = query.where(
                or_(
                    CompanySettingValue.country == country,
                    CompanySettingValue.country.is_(None),
                )
            )
        else:
            query = query.where(CompanySettingValue.country.is_(None))

        res = await session.execute(query)
        setting = res.scalars().first()
        if setting:
            return setting.value
        return default

    @staticmethod
    async def set_setting(
        session: AsyncSession,
        key: str,
        value: Any,
        country: str | None = None,
        effective_from: date | None = None,
        unit: str | None = None,
        created_by_user_id: UUID | None = None,
    ) -> CompanySettingValue:
        """Insert a new effective-dated setting row and close previous row on new_date - 1 day."""
        eff_from = effective_from or datetime.now(UTC).date()

        # Close existing active row if any (inclusive non-overlapping date boundary)
        query = select(CompanySettingValue).where(
            CompanySettingValue.setting_key == key,
            CompanySettingValue.country == country,
            CompanySettingValue.effective_to.is_(None),
        )
        res = await session.execute(query)
        prev = res.scalar_one_or_none()
        if prev and prev.effective_from < eff_from:
            prev.effective_to = eff_from - timedelta(days=1)
        elif prev and prev.effective_from == eff_from:
            # Overwrite current day's setting if effective_from is identical
            prev.value = value
            if unit is not None:
                prev.unit = unit
            await session.flush()
            return prev

        row = CompanySettingValue(
            setting_key=key,
            country=country,
            value=value,
            unit=unit,
            effective_from=eff_from,
            created_by_user_id=created_by_user_id,
        )
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def list_settings_resolved(
        session: AsyncSession,
        country: str | None = None,
        as_of: date | None = None,
    ) -> list[CompanySettingValue]:
        """List all resolved settings in effect as of the given date."""
        target_date = as_of or datetime.now(UTC).date()

        query = select(CompanySettingValue).where(
            CompanySettingValue.effective_from <= target_date,
            or_(
                CompanySettingValue.effective_to.is_(None),
                CompanySettingValue.effective_to >= target_date,
            ),
        )
        if country:
            query = query.where(
                or_(
                    CompanySettingValue.country == country,
                    CompanySettingValue.country.is_(None),
                )
            )

        res = await session.execute(query)
        all_matches = list(res.scalars().all())

        # Disambiguate by (setting_key): country-specific wins over NULL country
        resolved_map: dict[str, CompanySettingValue] = {}
        # Sort so country-specific rows processed last and override NULL-country rows
        all_matches.sort(
            key=lambda r: (
                1 if r.country else 0,
                r.effective_from.toordinal(),
            )
        )
        for r in all_matches:
            resolved_map[r.setting_key] = r

        return list(resolved_map.values())

    @staticmethod
    async def get_setting_history(
        session: AsyncSession,
        key: str,
        country: str | None = None,
    ) -> list[CompanySettingValue]:
        """Fetch chronological audit history of a setting."""
        query = select(CompanySettingValue).where(CompanySettingValue.setting_key == key)
        if country:
            query = query.where(
                or_(
                    CompanySettingValue.country == country,
                    CompanySettingValue.country.is_(None),
                )
            )
        query = query.order_by(CompanySettingValue.effective_from.desc())
        res = await session.execute(query)
        return list(res.scalars().all())

    # --- Time Rules ---

    @staticmethod
    async def list_time_rules(
        session: AsyncSession,
        scope_type: str | None = None,
        country: str | None = None,
        scoped_employee_ids: set[UUID] | None = None,
    ) -> list[TimeRule]:
        """List time rules, filtered by user reporting scope."""
        query = select(TimeRule).where(TimeRule.is_active.is_(True))

        if scope_type:
            query = query.where(TimeRule.scope_type == scope_type)
        if country:
            query = query.where(or_(TimeRule.country == country, TimeRule.country.is_(None)))

        # For Engineer scope: they can view COMPANY/DRIVERS and their scoped TEAM/EMPLOYEE rules
        if scoped_employee_ids is not None:
            query = query.where(
                or_(
                    TimeRule.scope_type.in_(["COMPANY", "DRIVERS"]),
                    TimeRule.scope_employee_id.in_(scoped_employee_ids),
                )
            )

        query = query.order_by(TimeRule.start_date.desc(), TimeRule.name.asc())
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def get_time_rule(session: AsyncSession, rule_id: UUID) -> TimeRule:
        query = select(TimeRule).where(TimeRule.id == rule_id)
        res = await session.execute(query)
        rule = res.scalar_one_or_none()
        if not rule:
            raise AppError(code="NOT_FOUND", message="Time rule not found.", status_code=404)
        return rule

    @staticmethod
    async def create_time_rule(
        session: AsyncSession,
        payload: TimeRuleCreate,
        user_id: UUID | None,
        user_role: str,
        scoped_employee_ids: set[UUID] | None,
    ) -> TimeRule:
        """Create a new time rule with scope enforcement."""
        scope_upper = payload.scope_type.upper()

        if user_role == "ENGINEER":
            if scope_upper in ("COMPANY", "DRIVERS"):
                raise AppError(
                    code="OUT_OF_SCOPE",
                    message="Engineers cannot create company or driver time rules.",
                    status_code=403,
                )
            if not payload.scope_employee_id or payload.scope_employee_id not in (
                scoped_employee_ids or set()
            ):
                raise AppError(
                    code="OUT_OF_SCOPE",
                    message="Target employee or manager is outside your reporting scope.",
                    status_code=403,
                )

        rule = TimeRule(
            name=payload.name,
            country=payload.country,
            scope_type=scope_upper,
            scope_employee_id=payload.scope_employee_id,
            applies_to=payload.applies_to.upper(),
            start_date=payload.start_date,
            end_date=payload.end_date,
            accommodation_start=payload.accommodation_start,
            first_site_start=payload.first_site_start,
            break_minutes=payload.break_minutes,
            last_site_end=payload.last_site_end,
            accommodation_end=payload.accommodation_end,
            standard_hours_change_minutes=payload.standard_hours_change_minutes,
            notes=payload.notes,
            created_by_user_id=user_id,
        )
        session.add(rule)
        await session.flush()
        return rule

    @staticmethod
    async def update_time_rule(
        session: AsyncSession,
        rule_id: UUID,
        payload: TimeRuleUpdate,
        user_role: str,
        scoped_employee_ids: set[UUID] | None,
    ) -> TimeRule:
        """Update an existing time rule with optimistic locking and scope check."""
        rule = await SettingsService.get_time_rule(session, rule_id)

        if rule.version != payload.version:
            raise AppError(
                code="VERSION_CONFLICT",
                message="Time rule was modified concurrently. Refresh and retry.",
                status_code=409,
            )

        if user_role == "ENGINEER":
            if rule.scope_type in ("COMPANY", "DRIVERS"):
                raise AppError(
                    code="OUT_OF_SCOPE",
                    message="Engineers cannot edit company or driver time rules.",
                    status_code=403,
                )
            if rule.scope_employee_id not in (scoped_employee_ids or set()):
                raise AppError(
                    code="OUT_OF_SCOPE",
                    message="Time rule is outside your reporting scope.",
                    status_code=403,
                )
            if payload.scope_employee_id is not None and payload.scope_employee_id not in (
                scoped_employee_ids or set()
            ):
                raise AppError(
                    code="OUT_OF_SCOPE",
                    message="New target employee/manager is outside your reporting scope.",
                    status_code=403,
                )

        for attr in (
            "name",
            "country",
            "scope_type",
            "scope_employee_id",
            "applies_to",
            "start_date",
            "end_date",
            "accommodation_start",
            "first_site_start",
            "break_minutes",
            "last_site_end",
            "accommodation_end",
            "standard_hours_change_minutes",
            "notes",
            "is_active",
        ):
            val = getattr(payload, attr)
            if val is not None:
                setattr(rule, attr, val)

        rule.version += 1
        await session.flush()
        return rule

    @staticmethod
    async def delete_time_rule(
        session: AsyncSession,
        rule_id: UUID,
        user_role: str,
        scoped_employee_ids: set[UUID] | None,
    ) -> TimeRule:
        rule = await SettingsService.get_time_rule(session, rule_id)
        if user_role == "ENGINEER":
            if rule.scope_type in ("COMPANY", "DRIVERS") or rule.scope_employee_id not in (
                scoped_employee_ids or set()
            ):
                raise AppError(
                    code="OUT_OF_SCOPE",
                    message="Cannot deactivate a rule outside your reporting scope.",
                    status_code=403,
                )
        rule.is_active = False
        await session.flush()
        return rule

    @staticmethod
    async def resolve_worker_schedule(
        session: AsyncSession,
        worker: WorkerContext,
        target_date: date,
        is_outdoor: bool | None = None,
    ) -> ResolvedTimeSchedule:
        """Resolve effective planned schedule using pure domain rule resolver."""
        query = select(TimeRule).where(
            TimeRule.is_active.is_(True),
            or_(TimeRule.country == worker.country, TimeRule.country.is_(None)),
        )
        res = await session.execute(query)
        orm_rules = list(res.scalars().all())

        rule_defs = [
            TimeRuleDefinition(
                id=r.id,
                name=r.name,
                country=r.country,
                scope_type=r.scope_type,
                scope_employee_id=r.scope_employee_id,
                applies_to=r.applies_to,
                start_date=r.start_date,
                end_date=r.end_date,
                accommodation_start=r.accommodation_start,
                first_site_start=r.first_site_start,
                break_minutes=r.break_minutes,
                last_site_end=r.last_site_end,
                accommodation_end=r.accommodation_end,
                standard_hours_change_minutes=r.standard_hours_change_minutes,
                notes=r.notes,
                is_active=r.is_active,
            )
            for r in orm_rules
        ]

        return domain_resolve_time_schedule(
            rules=rule_defs,
            worker=worker,
            target_date=target_date,
            is_outdoor=is_outdoor,
        )

    # --- Public Holidays ---

    @staticmethod
    async def list_public_holidays(
        session: AsyncSession,
        country: str | None = None,
        year: int | None = None,
    ) -> list[PublicHoliday]:
        query = select(PublicHoliday)
        if country:
            query = query.where(PublicHoliday.country == country.upper())
        if year:
            query = query.where(extract("year", PublicHoliday.holiday_date) == year)
        query = query.order_by(PublicHoliday.holiday_date.asc())
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def create_public_holiday(
        session: AsyncSession,
        payload: PublicHolidayCreate,
        user_id: UUID | None = None,
    ) -> PublicHoliday:
        query = select(PublicHoliday).where(
            PublicHoliday.holiday_date == payload.holiday_date,
            PublicHoliday.country == payload.country.upper(),
        )
        res = await session.execute(query)
        if res.scalar_one_or_none():
            raise AppError(
                code="DUPLICATE_HOLIDAY",
                message=f"Public holiday already exists on {payload.holiday_date} for {payload.country}.",
                status_code=409,
            )

        holiday = PublicHoliday(
            holiday_date=payload.holiday_date,
            name=payload.name,
            country=payload.country.upper(),
            created_by_user_id=user_id,
        )
        session.add(holiday)
        await session.flush()
        return holiday

    @staticmethod
    async def delete_public_holiday(session: AsyncSession, holiday_id: UUID) -> None:
        query = select(PublicHoliday).where(PublicHoliday.id == holiday_id)
        res = await session.execute(query)
        holiday = res.scalar_one_or_none()
        if not holiday:
            raise AppError(code="NOT_FOUND", message="Public holiday not found.", status_code=404)
        await session.delete(holiday)
        await session.flush()

    # --- Consent Policies ---

    @staticmethod
    async def list_consent_policies(
        session: AsyncSession,
        language: str | None = None,
    ) -> list[ConsentPolicy]:
        query = select(ConsentPolicy)
        if language:
            query = query.where(ConsentPolicy.language == language)
        query = query.order_by(ConsentPolicy.version.desc(), ConsentPolicy.published_at.desc())
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def create_consent_policy(
        session: AsyncSession,
        payload: ConsentPolicyCreate,
        user_id: UUID | None = None,
    ) -> ConsentPolicy:
        query = select(ConsentPolicy).where(
            ConsentPolicy.version == payload.version,
            ConsentPolicy.language == payload.language,
        )
        res = await session.execute(query)
        if res.scalar_one_or_none():
            raise AppError(
                code="DUPLICATE_POLICY",
                message=f"Consent policy version {payload.version} ({payload.language}) already exists.",
                status_code=409,
            )

        policy = ConsentPolicy(
            version=payload.version,
            language=payload.language,
            title=payload.title,
            body=payload.body,
            published_by_user_id=user_id,
        )
        session.add(policy)
        await session.flush()
        return policy
