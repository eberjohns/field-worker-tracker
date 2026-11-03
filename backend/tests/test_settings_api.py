from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from fw.core.errors import AppError
from fw.modules.settings.models import CompanySettingValue, ConsentPolicy, PublicHoliday, TimeRule
from fw.modules.settings.schemas import (
    ConsentPolicyCreate,
    PublicHolidayCreate,
    TimeRuleCreate,
    TimeRuleUpdate,
)
from fw.modules.settings.service import SettingsService


@pytest.mark.asyncio
async def test_effective_dated_settings_resolution_and_history():
    """Verify that a change adds a new dated row and past dates still resolve to old value."""
    session = AsyncMock()

    d1 = date(2026, 1, 1)
    d2 = date(2026, 6, 1)

    # 1. Existing row from d1
    row1 = CompanySettingValue(
        id=uuid4(),
        setting_key="grace_period_minutes",
        country=None,
        value=10,
        unit="min",
        effective_from=d1,
        effective_to=None,
    )

    mock_res1 = MagicMock()
    mock_res1.scalars.return_value.all.return_value = [row1]
    mock_res1.scalar_one_or_none.return_value = row1
    session.execute.return_value = mock_res1

    # 2. Add new setting effective from d2
    row2 = await SettingsService.set_setting(
        session=session,
        key="grace_period_minutes",
        value=15,
        effective_from=d2,
    )

    # Old row is closed on d2 - 1 day
    assert row1.effective_to == d2 - timedelta(days=1)
    assert row2.effective_from == d2
    assert row2.value == 15
    assert row2.effective_to is None

    # 3. Simulate resolve: querying as of May 1st (before d2)
    past_date = date(2026, 5, 1)
    mock_res_past = MagicMock()
    mock_res_past.scalars.return_value.first.return_value = row1
    session.execute.return_value = mock_res_past

    val_past = await SettingsService.get_setting(session, "grace_period_minutes", as_of=past_date)
    assert val_past == 10

    # 4. Querying as of July 1st (after d2)
    future_date = date(2026, 7, 1)
    mock_res_future = MagicMock()
    mock_res_future.scalars.return_value.first.return_value = row2
    session.execute.return_value = mock_res_future

    val_future = await SettingsService.get_setting(
        session, "grace_period_minutes", as_of=future_date
    )
    assert val_future == 15


@pytest.mark.asyncio
async def test_engineer_cannot_create_company_or_driver_rule():
    """Engineer cannot create COMPANY or DRIVERS rules."""
    session = AsyncMock()
    engineer_user_id = uuid4()
    engineer_scope = {uuid4()}

    payload = TimeRuleCreate(
        name="Engineer Global Attempt",
        scope_type="COMPANY",
        start_date=date(2026, 1, 1),
    )

    with pytest.raises(AppError) as exc:
        await SettingsService.create_time_rule(
            session=session,
            payload=payload,
            user_id=engineer_user_id,
            user_role="ENGINEER",
            scoped_employee_ids=engineer_scope,
        )

    assert exc.value.code == "OUT_OF_SCOPE"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_engineer_cannot_edit_another_engineers_team_rule():
    """Engineer cannot edit another engineer's team rule."""
    session = AsyncMock()
    engineer_a_scope = {uuid4(), uuid4()}
    engineer_b_mgr_id = uuid4()  # not in engineer A's scope

    other_team_rule = TimeRule(
        id=uuid4(),
        name="Team Dawood Rule",
        scope_type="TEAM",
        scope_employee_id=engineer_b_mgr_id,
        applies_to="ALL",
        start_date=date(2026, 1, 1),
        break_minutes=60,
        version=1,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = other_team_rule
    session.execute.return_value = mock_res

    update_payload = TimeRuleUpdate(
        version=1,
        break_minutes=45,
    )

    with pytest.raises(AppError) as exc:
        await SettingsService.update_time_rule(
            session=session,
            rule_id=other_team_rule.id,
            payload=update_payload,
            user_role="ENGINEER",
            scoped_employee_ids=engineer_a_scope,
        )

    assert exc.value.code == "OUT_OF_SCOPE"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_optimistic_locking_version_conflict_on_time_rule():
    """Updating a time rule with a stale version returns 409 VERSION_CONFLICT."""
    session = AsyncMock()
    rule = TimeRule(
        id=uuid4(),
        name="Test Rule",
        scope_type="COMPANY",
        start_date=date(2026, 1, 1),
        version=2,  # Current DB version is 2
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = rule
    session.execute.return_value = mock_res

    # Client sends stale version 1
    stale_payload = TimeRuleUpdate(version=1, break_minutes=45)

    with pytest.raises(AppError) as exc:
        await SettingsService.update_time_rule(
            session=session,
            rule_id=rule.id,
            payload=stale_payload,
            user_role="ADMIN",
            scoped_employee_ids=None,
        )

    assert exc.value.code == "VERSION_CONFLICT"
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_public_holidays_duplicate_protection():
    """Duplicate public holiday on the same date and country raises 409."""
    session = AsyncMock()
    existing_holiday = PublicHoliday(
        id=uuid4(),
        holiday_date=date(2026, 1, 1),
        name="New Year",
        country="AE",
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_holiday
    session.execute.return_value = mock_res

    payload = PublicHolidayCreate(
        holiday_date=date(2026, 1, 1),
        name="Duplicate New Year",
        country="AE",
    )

    with pytest.raises(AppError) as exc:
        await SettingsService.create_public_holiday(session=session, payload=payload)

    assert exc.value.code == "DUPLICATE_HOLIDAY"
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_consent_policies_duplicate_protection():
    """Duplicate consent policy version and language raises 409."""
    session = AsyncMock()
    existing_policy = ConsentPolicy(
        id=uuid4(),
        version=1,
        language="en",
        title="Privacy Notice",
        body="Body text",
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_policy
    session.execute.return_value = mock_res

    payload = ConsentPolicyCreate(
        version=1,
        language="en",
        title="Another Notice",
        body="Body text",
    )

    with pytest.raises(AppError) as exc:
        await SettingsService.create_consent_policy(session=session, payload=payload)

    assert exc.value.code == "DUPLICATE_POLICY"
    assert exc.value.status_code == 409
