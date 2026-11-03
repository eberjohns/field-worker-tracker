from datetime import date, time
from uuid import uuid4

from fw.rules.time_rules import (
    TimeRuleAppliesTo,
    TimeRuleDefinition,
    TimeRuleScope,
    WorkerContext,
    resolve_time_schedule,
)


def test_client_example_computation():
    """Verify exact client example: 05:00 / 06:00 / 0:30 / 15:30 / 17:00 => 12:00 total, 09:00 worked."""
    worker = WorkerContext(
        employee_id=uuid4(),
        country="AE",
        is_driver=False,
        has_accommodation=True,
    )
    rule = TimeRuleDefinition(
        id=uuid4(),
        name="Company Standard",
        country="AE",
        scope_type=TimeRuleScope.COMPANY,
        scope_employee_id=None,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2026, 1, 1),
        accommodation_start=time(5, 0),
        first_site_start=time(6, 0),
        break_minutes=30,
        last_site_end=time(15, 30),
        accommodation_end=time(17, 0),
    )

    resolved = resolve_time_schedule([rule], worker, target_date=date(2026, 11, 3))

    assert resolved.accommodation_start == time(5, 0)
    assert resolved.first_site_start == time(6, 0)
    assert resolved.break_minutes == 30
    assert resolved.last_site_end == time(15, 30)
    assert resolved.accommodation_end == time(17, 0)
    # Total time: 17:00 - 05:00 = 12h = 720 minutes
    assert resolved.planned_total_minutes == 720
    # Worked time: (15:30 - 06:00) = 570m - 30m break = 540m = 9h
    assert resolved.planned_worked_minutes == 540
    assert resolved.winning_rule_id == rule.id


def test_worker_without_company_accommodation():
    """Worker without company accommodation: total time = first site to last site (BR-AT-16)."""
    worker = WorkerContext(
        employee_id=uuid4(),
        country="AE",
        is_driver=False,
        has_accommodation=False,  # No accommodation
    )
    rule = TimeRuleDefinition(
        id=uuid4(),
        name="Company Standard",
        country="AE",
        scope_type=TimeRuleScope.COMPANY,
        scope_employee_id=None,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2026, 1, 1),
        accommodation_start=time(5, 0),
        first_site_start=time(6, 0),
        break_minutes=30,
        last_site_end=time(15, 30),
        accommodation_end=time(17, 0),
    )

    resolved = resolve_time_schedule([rule], worker, target_date=date(2026, 11, 3))

    assert not resolved.has_accommodation
    # Planned total time = 15:30 - 06:00 = 570 minutes (9h 30m)
    assert resolved.planned_total_minutes == 570
    assert resolved.planned_worked_minutes == 540


def test_scope_precedence_employee_over_team_over_driver_over_company():
    """EMPLOYEE > TEAM > DRIVERS > COMPANY precedence check."""
    worker_id = uuid4()
    supervisor_id = uuid4()
    worker = WorkerContext(
        employee_id=worker_id,
        country="AE",
        is_driver=True,
        has_accommodation=True,
        manager_links=[(supervisor_id, "SUPERVISOR")],
    )

    company_rule = TimeRuleDefinition(
        id=uuid4(),
        name="Company Rule",
        country="AE",
        scope_type=TimeRuleScope.COMPANY,
        scope_employee_id=None,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2026, 1, 1),
        first_site_start=time(6, 0),
        break_minutes=30,
        last_site_end=time(15, 30),
    )
    driver_rule = TimeRuleDefinition(
        id=uuid4(),
        name="Driver Rule",
        country="AE",
        scope_type=TimeRuleScope.DRIVERS,
        scope_employee_id=None,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2026, 1, 1),
        first_site_start=time(5, 45),
        break_minutes=45,
        last_site_end=time(16, 0),
    )
    team_rule = TimeRuleDefinition(
        id=uuid4(),
        name="Supervisor Dawood Team",
        country="AE",
        scope_type=TimeRuleScope.TEAM,
        scope_employee_id=supervisor_id,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2026, 1, 1),
        first_site_start=time(6, 30),
        break_minutes=60,
        last_site_end=time(16, 30),
    )
    employee_rule = TimeRuleDefinition(
        id=uuid4(),
        name="Ali Individual Rule",
        country="AE",
        scope_type=TimeRuleScope.EMPLOYEE,
        scope_employee_id=worker_id,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2026, 1, 1),
        first_site_start=time(7, 0),
        break_minutes=90,
        last_site_end=time(17, 0),
    )

    # 1. With all rules present, EMPLOYEE rule wins
    rules = [company_rule, driver_rule, team_rule, employee_rule]
    res1 = resolve_time_schedule(rules, worker, date(2026, 5, 1))
    assert res1.winning_rule_id == employee_rule.id
    assert res1.first_site_start == time(7, 0)
    assert res1.break_minutes == 90

    # 2. Without employee rule, TEAM rule wins over driver and company
    res2 = resolve_time_schedule([company_rule, driver_rule, team_rule], worker, date(2026, 5, 1))
    assert res2.winning_rule_id == team_rule.id
    assert res2.first_site_start == time(6, 30)
    assert res2.break_minutes == 60

    # 3. Without team rule, DRIVER rule wins over company rule for driver
    res3 = resolve_time_schedule([company_rule, driver_rule], worker, date(2026, 5, 1))
    assert res3.winning_rule_id == driver_rule.id
    assert res3.first_site_start == time(5, 45)
    assert res3.break_minutes == 45

    # 4. For non-driver, DRIVER rule is excluded and COMPANY rule wins
    non_driver = WorkerContext(
        employee_id=worker_id,
        country="AE",
        is_driver=False,
        has_accommodation=True,
    )
    res4 = resolve_time_schedule([company_rule, driver_rule], non_driver, date(2026, 5, 1))
    assert res4.winning_rule_id == company_rule.id
    assert res4.first_site_start == time(6, 0)


def test_outdoor_indoor_precedence_and_season():
    """Narrower applies_to (OUTDOOR_ONLY) wins over ALL on outdoor jobs; seasonal dates apply."""
    worker = WorkerContext(
        employee_id=uuid4(),
        country="AE",
        is_driver=False,
        has_accommodation=True,
    )

    company_std = TimeRuleDefinition(
        id=uuid4(),
        name="Company Standard",
        country="AE",
        scope_type=TimeRuleScope.COMPANY,
        scope_employee_id=None,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2026, 1, 1),
        break_minutes=30,
        first_site_start=time(6, 0),
        last_site_end=time(15, 30),
    )
    summer_outdoor = TimeRuleDefinition(
        id=uuid4(),
        name="Summer Outdoor",
        country="AE",
        scope_type=TimeRuleScope.COMPANY,
        scope_employee_id=None,
        applies_to=TimeRuleAppliesTo.OUTDOOR_ONLY,
        start_date=date(2026, 6, 15),
        end_date=date(2026, 9, 15),
        break_minutes=150,  # 2.5 hours break for outdoor summer
        first_site_start=time(5, 0),
        last_site_end=time(16, 30),
    )

    rules = [company_std, summer_outdoor]

    # Date in summer, outdoor job: Summer Outdoor rule wins
    res_summer_outdoor = resolve_time_schedule(
        rules, worker, target_date=date(2026, 7, 1), is_outdoor=True
    )
    assert res_summer_outdoor.winning_rule_id == summer_outdoor.id
    assert res_summer_outdoor.break_minutes == 150

    # Date in summer, indoor job: Summer Outdoor excluded, standard wins
    res_summer_indoor = resolve_time_schedule(
        rules, worker, target_date=date(2026, 7, 1), is_outdoor=False
    )
    assert res_summer_indoor.winning_rule_id == company_std.id
    assert res_summer_indoor.break_minutes == 30

    # Date outside summer (e.g. October), outdoor job: Summer expired, standard wins
    res_oct_outdoor = resolve_time_schedule(
        rules, worker, target_date=date(2026, 10, 1), is_outdoor=True
    )
    assert res_oct_outdoor.winning_rule_id == company_std.id
    assert res_oct_outdoor.break_minutes == 30


def test_field_inheritance_from_lower_precedence_rules():
    """Team rule specifies only break and standard hours change; inherits times from Company rule."""
    worker_id = uuid4()
    supervisor_id = uuid4()
    worker = WorkerContext(
        employee_id=worker_id,
        country="AE",
        is_driver=False,
        has_accommodation=True,
        manager_links=[(supervisor_id, "SUPERVISOR")],
    )

    company_rule = TimeRuleDefinition(
        id=uuid4(),
        name="Company Standard",
        country="AE",
        scope_type=TimeRuleScope.COMPANY,
        scope_employee_id=None,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2026, 1, 1),
        accommodation_start=time(5, 0),
        first_site_start=time(6, 0),
        break_minutes=30,
        last_site_end=time(15, 30),
        accommodation_end=time(17, 0),
    )
    # Team rule only overrides break
    team_rule = TimeRuleDefinition(
        id=uuid4(),
        name="Team Custom Break",
        country="AE",
        scope_type=TimeRuleScope.TEAM,
        scope_employee_id=supervisor_id,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2026, 1, 1),
        accommodation_start=None,  # inherit
        first_site_start=None,  # inherit
        break_minutes=60,  # override
        last_site_end=None,  # inherit
        accommodation_end=None,  # inherit
        standard_hours_change_minutes=-60,
    )

    resolved = resolve_time_schedule(
        [company_rule, team_rule], worker, target_date=date(2026, 5, 1)
    )

    # Primary winner is team rule
    assert resolved.winning_rule_id == team_rule.id
    # Break and standard hours from team rule
    assert resolved.break_minutes == 60
    assert resolved.standard_hours_change_minutes == -60
    assert resolved.winning_sources["break_minutes"].rule_id == team_rule.id

    # Times inherited from company rule
    assert resolved.accommodation_start == time(5, 0)
    assert resolved.first_site_start == time(6, 0)
    assert resolved.last_site_end == time(15, 30)
    assert resolved.accommodation_end == time(17, 0)
    assert resolved.winning_sources["accommodation_start"].rule_id == company_rule.id
    assert resolved.winning_sources["first_site_start"].rule_id == company_rule.id

    # Total planned: 17:00 - 05:00 = 720 minutes
    assert resolved.planned_total_minutes == 720
    # Worked: (15:30 - 06:00) = 570 - 60 break = 510 minutes (8h 30m)
    assert resolved.planned_worked_minutes == 510


def test_ramadan_rule_standard_hours_reduction():
    """Ramadan season rule with standard hours reduction (-120 min) and zero break."""
    worker = WorkerContext(
        employee_id=uuid4(),
        country="AE",
        is_driver=False,
        has_accommodation=True,
    )
    company_rule = TimeRuleDefinition(
        id=uuid4(),
        name="Company Standard",
        country="AE",
        scope_type=TimeRuleScope.COMPANY,
        scope_employee_id=None,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2026, 1, 1),
        accommodation_start=time(5, 0),
        first_site_start=time(6, 0),
        break_minutes=30,
        last_site_end=time(15, 30),
        accommodation_end=time(17, 0),
    )
    ramadan_rule = TimeRuleDefinition(
        id=uuid4(),
        name="Ramadan 2027",
        country="AE",
        scope_type=TimeRuleScope.COMPANY,
        scope_employee_id=None,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2027, 2, 8),
        end_date=date(2027, 3, 9),
        accommodation_start=time(5, 0),
        first_site_start=time(5, 30),
        break_minutes=0,
        last_site_end=time(12, 30),
        accommodation_end=time(13, 30),
        standard_hours_change_minutes=-120,
    )

    rules = [company_rule, ramadan_rule]

    # Target date inside Ramadan: ramadan rule wins (more recent start_date)
    res_ramadan = resolve_time_schedule(rules, worker, target_date=date(2027, 2, 15))
    assert res_ramadan.winning_rule_id == ramadan_rule.id
    assert res_ramadan.break_minutes == 0
    assert res_ramadan.standard_hours_change_minutes == -120
    # Worked time: 12:30 - 05:30 = 7h = 420 min - 0 = 420 min
    assert res_ramadan.planned_worked_minutes == 420
    # Total time: 13:30 - 05:00 = 8h 30m = 510 min
    assert res_ramadan.planned_total_minutes == 510

    # Target date before Ramadan: company rule wins
    res_before = resolve_time_schedule(rules, worker, target_date=date(2027, 1, 15))
    assert res_before.winning_rule_id == company_rule.id
    assert res_before.standard_hours_change_minutes == 0
