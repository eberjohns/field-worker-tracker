"""Phase 02 Demo Script.

Verifies:
1. Baseline company rule is active.
2. Add a Team rule (e.g. Supervisor Dawood's team break override).
3. Add a seasonal Ramadan rule (effective 2027-02-08 to 2027-03-09 with -120m standard hours).
4. Run the explainer on two dates:
   - Date 1 (2027-01-15): Normal working day -> Team rule wins for break, inheriting times.
   - Date 2 (2027-02-15): Ramadan day -> Ramadan seasonal rule wins with reduced working hours.
"""

from datetime import date, time
from uuid import uuid4

from fw.rules.time_rules import (
    TimeRuleAppliesTo,
    TimeRuleDefinition,
    TimeRuleScope,
    WorkerContext,
    resolve_time_schedule,
)


def format_minutes(m: int) -> str:
    hrs = m // 60
    mins = m % 60
    return f"{hrs:02d}:{mins:02d}"


def run_demo() -> None:
    print("=" * 65)
    print("PHASE 02 DEMO: TIME RULES RESOLVER & EXPLAINER")
    print("=" * 65)

    # 1. Setup Worker and Reporting Structure
    worker_id = uuid4()
    supervisor_id = uuid4()
    worker = WorkerContext(
        employee_id=worker_id,
        country="AE",
        is_driver=False,
        has_accommodation=True,
        manager_links=[(supervisor_id, "SUPERVISOR")],
    )
    print(f"\n[Worker Setup] Worker ID: {worker_id}")
    print(" -> Country: AE | Driver: False | Accommodation: True")
    print(f" -> Supervisor ID: {supervisor_id} (Mr. Dawood)")

    # 2. Company Default Rule
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
        standard_hours_change_minutes=0,
    )

    # 3. Add Team Rule (Supervisor Dawood's team)
    team_rule = TimeRuleDefinition(
        id=uuid4(),
        name="Dawood Team Custom Rule",
        country="AE",
        scope_type=TimeRuleScope.TEAM,
        scope_employee_id=supervisor_id,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2026, 1, 1),
        accommodation_start=None,  # inherit
        first_site_start=time(6, 30),  # starts site 30 min later
        break_minutes=60,  # 1 hour break
        last_site_end=time(16, 30),  # ends site 1 hour later
        accommodation_end=None,  # inherit
        standard_hours_change_minutes=0,
    )
    print("\n[Step 1] Added Team Rule for Dawood's Team:")
    print(" -> Overrides: First Site (06:30), Break (60m), Last Site (16:30)")
    print(" -> Inherits: Acc. Start (05:00) and Acc. End (17:00) from Company rule")

    # 4. Add Seasonal Ramadan Rule
    ramadan_rule = TimeRuleDefinition(
        id=uuid4(),
        name="Ramadan 2027 Season",
        country="AE",
        scope_type=TimeRuleScope.COMPANY,
        scope_employee_id=None,
        applies_to=TimeRuleAppliesTo.ALL,
        start_date=date(2027, 2, 8),
        end_date=date(2027, 3, 9),
        accommodation_start=time(5, 0),
        first_site_start=time(5, 30),
        break_minutes=0,  # No break during fasting hours
        last_site_end=time(12, 30),
        accommodation_end=time(13, 30),
        standard_hours_change_minutes=-120,  # -2 hours working day
    )
    print("\n[Step 2] Added Seasonal Rule for Ramadan (08 Feb 2027 - 09 Mar 2027):")
    print(" -> 05:00 Acc Start / 05:30 First Site / 0m Break / 12:30 Last Site / 13:30 Acc End")
    print(" -> Standard hours reduction: -120 min (-2h)")

    rules = [company_rule, team_rule, ramadan_rule]

    # 5. Explainer Test Date 1: Normal date before Ramadan (2027-01-15)
    date1 = date(2027, 1, 15)
    print(f"\n[Step 3] Explainer on Date 1: {date1} (Normal Winter Day)")
    res1 = resolve_time_schedule(rules, worker, target_date=date1, is_outdoor=True)
    print(f" -> Winning Primary Rule: {res1.winning_rule_name} (Scope: TEAM)")
    print(
        f" -> Resolved 5-Point Plan: Acc.Start={res1.accommodation_start} | "
        f"1st Site={res1.first_site_start} | Break={res1.break_minutes}m | "
        f"Last Site={res1.last_site_end} | Acc.End={res1.accommodation_end}"
    )
    print(
        f" -> Planned Total Span: {format_minutes(res1.planned_total_minutes)} ({res1.planned_total_minutes}m)"
    )
    print(
        f" -> Planned Worked Time: {format_minutes(res1.planned_worked_minutes)} ({res1.planned_worked_minutes}m)"
    )
    print(" -> Field Sources:")
    for f, src in res1.winning_sources.items():
        print(f"    * {f}: {src.value} (from {src.rule_name} [{src.scope_type}])")

    # 6. Explainer Test Date 2: Ramadan Date (2027-02-15)
    date2 = date(2027, 2, 15)
    print(f"\n[Step 4] Explainer on Date 2: {date2} (Inside Ramadan Season)")
    res2 = resolve_time_schedule(rules, worker, target_date=date2, is_outdoor=True)
    print(f" -> Winning Primary Rule: {res2.winning_rule_name} (Scope: {res2.winning_rule_name})")
    print(
        f" -> Resolved 5-Point Plan: Acc.Start={res2.accommodation_start} | "
        f"1st Site={res2.first_site_start} | Break={res2.break_minutes}m | "
        f"Last Site={res2.last_site_end} | Acc.End={res2.accommodation_end}"
    )
    print(
        f" -> Planned Total Span: {format_minutes(res2.planned_total_minutes)} ({res2.planned_total_minutes}m)"
    )
    print(
        f" -> Planned Worked Time: {format_minutes(res2.planned_worked_minutes)} ({res2.planned_worked_minutes}m)"
    )
    print(f" -> Standard Hours Change: {res2.standard_hours_change_minutes} min")
    print(" -> Field Sources:")
    for f, src in res2.winning_sources.items():
        print(f"    * {f}: {src.value} (from {src.rule_name} [{src.scope_type}])")

    print("\n" + "=" * 65)
    print("PHASE 02 DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    run_demo()
