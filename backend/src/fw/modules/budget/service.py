"""Job budget, man-hours and planned vs actual (DEC-59, ADR-029).

Everything is loaded in bulk (BudgetRepository): revisions, settings, visits, schedules and
payroll allocations for all requested worksites in a fixed number of queries. The arithmetic is
in ``fw.rules.jobs.budget``.

Money (rates, costs, provision notes, SETTING_MISSING) is computed only for Admin (DEC-47).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import site_today
from fw.core.errors import AppError
from fw.core.progress import yield_every
from fw.modules.budget.repository import BudgetRepository
from fw.modules.budget.schemas import (
    PlannedActualFigures,
    PlannedActualItem,
    PlannedActualMonth,
    WorksiteBudgetVsActualItem,
)
from fw.modules.jobs import (
    BudgetWarning,
    JobItemBudget,
    JobItemCreate,
    Worksite,
    WorksiteBudgetTotals,
)
from fw.modules.payroll import SalaryRevision
from fw.modules.settings import CompanySettingValue
from fw.rules.grades import try_base_grade_code
from fw.rules.jobs import (
    MISSING_GRADE_RATE,
    PROVISIONS_DIFFER_FROM_PAYROLL,
    GradeLine,
    ItemSchedule,
    active_window,
    contract_year_containing,
    grade_hourly_rate,
    is_budget_only_staff_type,
    month_ranges,
    plan_item,
    split_by_weights,
    variance,
    year_fraction,
)
from fw.rules.payroll import round_money

SETTING_MISSING = "SETTING_MISSING"
_PAYROLL_PROVISION_KEYS = (
    "provision_visa",
    "provision_air_ticket",
    "provision_uniform",
    "provision_accommodation",
    "provision_medical",
)
_SETTING_KEYS = [
    "hr_overhead_rate",
    "standard_ot_divisor_hours",
    "budget_only_staff_types",
    "default_salary_revision_code",
    *_PAYROLL_PROVISION_KEYS,
]
_MAX_RANGE_DAYS = 366 * 5
_ZERO = Decimal("0")
_H = Decimal("0.001")


# --- Inputs -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemInput:
    """A job item, saved or not (preview)."""

    id: UUID | None
    sub_item_code: str
    staff_grade_description: str
    planned_grade_code: str
    schedule: ItemSchedule
    is_active: bool = True


def _item_from_model(it: Any) -> ItemInput:
    return ItemInput(
        id=it.id,
        sub_item_code=it.sub_item_code,
        staff_grade_description=it.staff_grade_description,
        planned_grade_code=it.planned_grade_code,
        schedule=ItemSchedule(
            frequency_unit=it.frequency_unit,
            occurrences_per_period=Decimal(str(it.occurrences_per_period)),
            period_interval=int(it.period_interval or 1),
            required_staff_count=int(it.required_staff_count),
            hours_per_occurrence_per_staff=Decimal(str(it.hours_per_occurrence_per_staff)),
            start_date=it.start_date,
            end_date=it.end_date,
        ),
        is_active=bool(it.is_active),
    )


def _item_from_create(p: JobItemCreate) -> ItemInput:
    return _item_from_model(
        type(
            "_Tmp",
            (),
            {
                "id": None,
                "sub_item_code": p.sub_item_code,
                "staff_grade_description": p.staff_grade_description,
                "planned_grade_code": p.planned_grade_code,
                "frequency_unit": p.frequency_unit,
                "occurrences_per_period": p.occurrences_per_period,
                "period_interval": p.period_interval,
                "required_staff_count": p.required_staff_count,
                "hours_per_occurrence_per_staff": p.hours_per_occurrence_per_staff,
                "start_date": p.start_date,
                "end_date": p.end_date,
                "is_active": True,
            },
        )()
    )


@dataclass(frozen=True)
class SiteInput:
    id: UUID | None
    job_number: str
    job_name: str
    country: str
    salary_revision_code: str | None
    contract_start: date | None
    contract_end: date | None
    budget_amount: Decimal | None
    items: tuple[ItemInput, ...]


def _site_from_model(ws: Worksite, items: list[ItemInput] | None = None) -> SiteInput:
    return SiteInput(
        id=ws.id,
        job_number=ws.job_number,
        job_name=ws.job_name,
        country=ws.country,
        salary_revision_code=ws.salary_revision_code,
        contract_start=ws.start_date,
        contract_end=ws.end_date,
        budget_amount=ws.budget_amount,
        items=tuple(items if items is not None else [_item_from_model(i) for i in ws.items]),
    )


# --- Context: revisions and settings, resolved in memory -------------------------------------


class _Context:
    def __init__(self, revisions: list[SalaryRevision], settings: list[CompanySettingValue]):
        self.revisions_by_code = {r.code: r for r in revisions}
        self.revisions_by_country: dict[str, list[SalaryRevision]] = defaultdict(list)
        for r in revisions:
            self.revisions_by_country[r.country].append(r)
        for lst in self.revisions_by_country.values():
            lst.sort(key=lambda r: r.effective_from, reverse=True)
        self.settings: dict[str, list[CompanySettingValue]] = defaultdict(list)
        for s in settings:
            self.settings[s.setting_key].append(s)

    def setting(self, key: str, country: str | None, as_of: date) -> Any:
        """Same resolution as SettingsService.get_setting (country row first, then newest)."""
        rows = [
            s
            for s in self.settings.get(key, [])
            if s.effective_from <= as_of
            and (s.effective_to is None or s.effective_to >= as_of)
            and (s.country is None or s.country == country)
        ]
        if not rows:
            return None
        rows.sort(key=lambda s: (s.country is not None, s.effective_from), reverse=True)
        return rows[0].value

    def decimal_setting(self, key: str, country: str, as_of: date) -> Decimal | None:
        v = self.setting(key, country, as_of)
        return Decimal(str(v)) if v is not None else None

    def revision_for(self, site: SiteInput, as_of: date) -> SalaryRevision | None:
        """Worksite revision if active, else default_salary_revision_code, else latest active."""
        if site.salary_revision_code:
            rev = self.revisions_by_code.get(site.salary_revision_code)
            if rev is not None:
                return rev
        default_code = self.setting("default_salary_revision_code", site.country, as_of)
        if isinstance(default_code, str) and default_code.strip() in self.revisions_by_code:
            return self.revisions_by_code[default_code.strip()]
        lst = self.revisions_by_country.get(site.country) or []
        return lst[0] if lst else None

    def budget_only_types(self, country: str, as_of: date) -> list[str]:
        raw = self.setting("budget_only_staff_types", country, as_of)
        return [str(x) for x in raw] if isinstance(raw, list) else []


async def _load_context(session: AsyncSession) -> _Context:
    return _Context(
        await BudgetRepository.active_revisions(session),
        await BudgetRepository.settings_rows(session, _SETTING_KEYS),
    )


def _grade_line(line: Any) -> GradeLine:
    z = Decimal("0")
    return GradeLine(
        basic_salary=line.basic_salary,
        special_allowance=line.special_allowance or z,
        fixed_ot_amount=line.fixed_ot_amount or z,
        bonus=line.bonus or z,
        telephone_allowance=line.telephone_allowance or z,
        housing_transport_allowance=line.housing_transport_allowance or z,
        visa_provision=line.visa_provision or z,
        air_ticket_provision=line.air_ticket_provision or z,
        uniform_provision=line.uniform_provision or z,
        medical_provision=line.medical_provision or z,
        accommodation_provision=line.accommodation_provision or z,
        transportation_provision=line.transportation_provision or z,
    )


# --- Per-worksite plan --------------------------------------------------------------------------


@dataclass
class _ItemResult:
    item: ItemInput
    grade: str | None
    is_budget_only: bool
    has_line: bool
    activities_per_year: Decimal
    full_year_hours: Decimal
    active_days: int
    hourly_rate: Decimal | None  # rate of the first month with a rate (display)
    month_hours: dict[date, Decimal] = field(default_factory=dict)
    month_cost: dict[date, Decimal | None] = field(default_factory=dict)

    @property
    def hours(self) -> Decimal:
        return sum(self.month_hours.values(), _ZERO)

    @property
    def cost(self) -> Decimal | None:
        if any(v is None for v in self.month_cost.values()):
            return None
        return round_money(sum((v for v in self.month_cost.values() if v is not None), _ZERO))

    @property
    def in_totals(self) -> bool:
        return self.item.is_active and self.has_line


@dataclass
class _SitePlan:
    site: SiteInput
    period_from: date
    period_to: date
    months: list[tuple[date, date]]
    revision: SalaryRevision | None
    items: list[_ItemResult]
    warnings: list[BudgetWarning]
    money_ok: bool


def _missing_setting(key: str, country: str, as_of: date) -> AppError:
    return AppError(
        code=SETTING_MISSING,
        message=f"Company setting '{key}' has no value for {country} on {as_of}.",
        status_code=422,
        extra={"setting_key": key, "country": country, "as_of": str(as_of)},
    )


def _plan_site(
    ctx: _Context,
    site: SiteInput,
    period_from: date,
    period_to: date,
    *,
    with_money: bool,
    strict: bool,
) -> _SitePlan:
    """Planned hours (and cost) per item per month of the period."""
    months = month_ranges(period_from, period_to)
    rev = ctx.revision_for(site, period_from)
    lines = {ln.grade_code: ln for ln in (rev.lines if rev else [])}
    budget_types = ctx.budget_only_types(site.country, period_from)
    warnings: list[BudgetWarning] = []
    money_ok = with_money

    # Rate settings per month (and check they exist).
    month_settings: dict[date, tuple[Decimal, Decimal] | None] = {}
    if with_money:
        for m_from, _m_to in months:
            oh = ctx.decimal_setting("hr_overhead_rate", site.country, m_from)
            div = ctx.decimal_setting("standard_ot_divisor_hours", site.country, m_from)
            missing = (
                "hr_overhead_rate"
                if oh is None
                else ("standard_ot_divisor_hours" if div is None or div <= 0 else None)
            )
            if missing:
                if strict:
                    raise _missing_setting(missing, site.country, m_from)
                money_ok = False
                month_settings[m_from] = None
                if not any(w.code == SETTING_MISSING for w in warnings):
                    warnings.append(
                        BudgetWarning(
                            code=SETTING_MISSING,
                            message=(
                                f"Company setting '{missing}' has no value for {site.country} on "
                                f"{m_from}; costs are not shown."
                            ),
                        )
                    )
            else:
                assert oh is not None and div is not None
                month_settings[m_from] = (oh, div)

    rate_cache: dict[tuple[str, date], Decimal] = {}

    def rate(grade: str, m_from: date) -> Decimal | None:
        st = month_settings.get(m_from)
        if st is None:
            return None
        key = (grade, m_from)
        if key not in rate_cache:
            rate_cache[key] = grade_hourly_rate(_grade_line(lines[grade]), st[0], st[1])
        return rate_cache[key]

    results: list[_ItemResult] = []
    noted_grades: set[str] = set()
    for item in site.items:
        grade = try_base_grade_code(item.planned_grade_code)
        has_line = grade is not None and grade in lines
        r = _ItemResult(
            item=item,
            grade=grade,
            is_budget_only=is_budget_only_staff_type(item.staff_grade_description, budget_types),
            has_line=has_line,
            activities_per_year=_ZERO,
            full_year_hours=_ZERO,
            active_days=0,
            hourly_rate=None,
        )
        for m_from, m_to in months:
            m_rate = rate(grade, m_from) if (has_line and grade and with_money) else None
            plan = plan_item(
                item.schedule, m_rate, m_from, m_to, site.contract_start, site.contract_end
            )
            r.activities_per_year = plan.activities_per_year
            r.full_year_hours = plan.full_year_hours
            r.active_days += plan.active_days
            r.month_hours[m_from] = plan.hours
            r.month_cost[m_from] = plan.cost if (with_money and money_ok) else None
            if r.hourly_rate is None and m_rate is not None:
                r.hourly_rate = m_rate
        results.append(r)

        if not has_line:
            warnings.append(
                BudgetWarning(
                    code=MISSING_GRADE_RATE,
                    job_item_id=item.id,
                    sub_item_code=item.sub_item_code,
                    grade_code=item.planned_grade_code,
                    annual_hours=r.hours,
                    message=(
                        f"Grade '{item.planned_grade_code or '(blank)'}' has no line in revision "
                        f"{rev.code if rev else '(none)'}; item left out of the totals."
                    ),
                )
            )
        elif with_money and grade and grade not in noted_grades:
            noted_grades.add(grade)
            plan_prov = _grade_line(lines[grade]).provisions_total
            vals = [
                ctx.decimal_setting(k, site.country, period_from) for k in _PAYROLL_PROVISION_KEYS
            ]
            if all(v is not None for v in vals):
                pay_prov = round_money(sum((v for v in vals if v is not None), _ZERO))
                if pay_prov != plan_prov:
                    warnings.append(
                        BudgetWarning(
                            code=PROVISIONS_DIFFER_FROM_PAYROLL,
                            grade_code=grade,
                            plan_provisions=plan_prov,
                            payroll_provisions=pay_prov,
                            message=(
                                f"Plan uses revision provisions {plan_prov}/month for {grade}; "
                                f"payroll uses settings {pay_prov}/month. Part of the cost "
                                "variance comes from this difference."
                            ),
                        )
                    )
    return _SitePlan(site, period_from, period_to, months, rev, results, warnings, money_ok)


def _item_budget(plan: _SitePlan, r: _ItemResult, with_money: bool) -> JobItemBudget:
    item_warnings = [
        w
        for w in plan.warnings
        if (w.job_item_id is not None and w.job_item_id == r.item.id and r.item.id is not None)
        or (w.code == MISSING_GRADE_RATE and r.item.id is None and not r.has_line)
        or (w.code == PROVISIONS_DIFFER_FROM_PAYROLL and w.grade_code == r.grade)
        or w.code == SETTING_MISSING
    ]
    return JobItemBudget(
        period_from=plan.period_from,
        period_to=plan.period_to,
        activities_per_year=r.activities_per_year,
        full_year_hours=r.full_year_hours,
        active_days=r.active_days,
        annual_hours=r.hours.quantize(_H),
        hourly_rate=r.hourly_rate if with_money else None,
        annual_cost=r.cost if with_money and r.has_line else None,
        is_budget_only=r.is_budget_only,
        revision_code=plan.revision.code if plan.revision else None,
        warnings=item_warnings if with_money else _hours_only(item_warnings),
    )


def _hours_only(warnings: list[BudgetWarning]) -> list[BudgetWarning]:
    return [w for w in warnings if w.code == MISSING_GRADE_RATE]


def _totals(plan: _SitePlan, with_money: bool) -> WorksiteBudgetTotals:
    in_totals = [r for r in plan.items if r.in_totals]
    cost: Decimal | None = None
    if with_money and plan.money_ok:
        cost = round_money(sum((r.cost or _ZERO for r in in_totals), _ZERO))
    return WorksiteBudgetTotals(
        period_from=plan.period_from,
        period_to=plan.period_to,
        revision_code=plan.revision.code if plan.revision else None,
        total_hours=sum((r.hours for r in in_totals), _ZERO).quantize(_H),
        missing_rate_hours=sum(
            (r.hours for r in plan.items if r.item.is_active and not r.has_line), _ZERO
        ).quantize(_H),
        total_cost=cost,
        warnings=plan.warnings if with_money else _hours_only(plan.warnings),
    )


def default_period(site: SiteInput, today: date | None = None) -> tuple[date, date]:
    """Current contract year (site-local today) from the worksite start date."""
    return contract_year_containing(today or site_today(site.country), site.contract_start)


def _check_range(date_from: date, date_to: date) -> None:
    if date_from > date_to or (date_to - date_from).days > _MAX_RANGE_DAYS:
        raise AppError(
            code="INVALID_DATE_RANGE",
            message="'from' must be on or before 'to', and the range at most 5 years.",
            status_code=422,
        )


def _figures(
    planned_h: Decimal, actual_h: Decimal, planned_c: Decimal | None, actual_c: Decimal | None
) -> dict[str, Any]:
    h_diff, h_pct = variance(planned_h, actual_h)
    out: dict[str, Any] = {
        "planned_hours": planned_h.quantize(_H),
        "actual_hours": actual_h.quantize(_H),
        "hours_diff": h_diff.quantize(_H),
        "hours_diff_pct": h_pct,
    }
    if planned_c is not None and actual_c is not None:
        c_diff, c_pct = variance(planned_c, actual_c)
        out.update(
            planned_cost=round_money(planned_c),
            actual_cost=round_money(actual_c),
            cost_diff=round_money(c_diff),
            cost_diff_pct=c_pct,
        )
    return out


class BudgetService:
    # --- Job items and worksite totals ------------------------------------------------------

    @staticmethod
    async def worksite_budget(
        session: AsyncSession, worksite: Worksite, *, is_admin: bool
    ) -> tuple[dict[UUID, JobItemBudget], WorksiteBudgetTotals]:
        """Per-item budgets and totals for the current contract year (worksite detail)."""
        ctx = await _load_context(session)
        site = _site_from_model(worksite)
        p_from, p_to = default_period(site)
        plan = _plan_site(ctx, site, p_from, p_to, with_money=is_admin, strict=False)
        per_item = {
            r.item.id: _item_budget(plan, r, is_admin) for r in plan.items if r.item.id is not None
        }
        return per_item, _totals(plan, is_admin)

    @staticmethod
    async def worksite_budget_by_id(
        session: AsyncSession, worksite_id: UUID, *, is_admin: bool
    ) -> tuple[dict[UUID, JobItemBudget], WorksiteBudgetTotals] | None:
        rows = await BudgetRepository.worksites_with_items(
            session, worksite_ids=[worksite_id], active_only=False
        )
        if not rows:
            return None
        return await BudgetService.worksite_budget(session, rows[0], is_admin=is_admin)

    @staticmethod
    async def preview_item(
        session: AsyncSession,
        payload: JobItemCreate,
        *,
        is_admin: bool,
        worksite: Worksite | None = None,
        country: str | None = None,
        salary_revision_code: str | None = None,
        contract_start: date | None = None,
        contract_end: date | None = None,
    ) -> JobItemBudget:
        """Budget of an unsaved job item, for the live figures in the form. Saves nothing."""
        ctx = await _load_context(session)
        item = _item_from_create(payload)
        if worksite is not None:
            site = _site_from_model(worksite, [item])
        else:
            site = SiteInput(
                id=None,
                job_number="",
                job_name="",
                country=country or "AE",
                salary_revision_code=salary_revision_code,
                contract_start=contract_start,
                contract_end=contract_end,
                budget_amount=None,
                items=(item,),
            )
        p_from, p_to = default_period(site)
        plan = _plan_site(ctx, site, p_from, p_to, with_money=is_admin, strict=is_admin)
        return _item_budget(plan, plan.items[0], is_admin)

    # --- Planned vs actual ----------------------------------------------------------------------

    @staticmethod
    async def planned_vs_actual(
        session: AsyncSession,
        *,
        is_admin: bool,
        worksite_ids: list[UUID] | None = None,
        country: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        as_of: date | None = None,
    ) -> list[WorksiteBudgetVsActualItem]:
        """Planned vs actual hours (and, for Admin, money) per worksite, item and month.

        Range: ``date_from``/``date_to`` if given; with only ``as_of``, the contract year up to
        that date; otherwise each worksite's current contract year.
        """
        if (date_from is None) != (date_to is None):
            raise AppError(
                code="INVALID_DATE_RANGE",
                message="Give both 'from' and 'to', or neither.",
                status_code=422,
            )
        if date_from is not None and date_to is not None:
            _check_range(date_from, date_to)

        worksites = await BudgetRepository.worksites_with_items(
            session, worksite_ids=worksite_ids, country=country, active_only=worksite_ids is None
        )
        if not worksites:
            return []
        ctx = await _load_context(session)

        sites = [_site_from_model(ws) for ws in worksites]
        ranges: dict[UUID, tuple[date, date]] = {}
        for s in sites:
            assert s.id is not None
            if date_from is not None and date_to is not None:
                ranges[s.id] = (date_from, date_to)
            elif as_of is not None:
                ranges[s.id] = (contract_year_containing(as_of, s.contract_start)[0], as_of)
            else:
                ranges[s.id] = default_period(s)
        lo = min(r[0] for r in ranges.values())
        hi = max(r[1] for r in ranges.values())
        ids = list(ranges)

        visits = await BudgetRepository.approved_visit_minutes(session, ids, lo, hi)
        sched = await BudgetRepository.scheduled_hours(session, ids, lo, hi)
        allocs = (
            await BudgetRepository.approved_allocations(session, ids, lo, hi) if is_admin else []
        )

        def month_key(d: date) -> date:
            return date(d.year, d.month, 1)

        # Scheduled hours: per (employee, worksite, day) -> {item: hours}; per item per month.
        sched_day: dict[tuple[UUID, UUID, date], dict[UUID, Decimal]] = defaultdict(dict)
        sched_item_month: dict[tuple[UUID, date], Decimal] = defaultdict(lambda: _ZERO)
        for emp, ws_id, d, item_id, hrs in sched:
            sched_day[(emp, ws_id, d)][item_id] = (
                sched_day[(emp, ws_id, d)].get(item_id, _ZERO) + hrs
            )
            sched_item_month[(item_id, month_key(d))] += hrs

        # Approved actual hours: split each day's visit minutes over that day's scheduled items.
        actual_item_month: dict[tuple[UUID, date], Decimal] = defaultdict(lambda: _ZERO)
        unplanned_ws_month: dict[tuple[UUID, date], Decimal] = defaultdict(lambda: _ZERO)
        for emp, ws_id, d, minutes in visits:
            hours = Decimal(minutes) / Decimal(60)
            day_items = sched_day.get((emp, ws_id, d))
            if not day_items:
                unplanned_ws_month[(ws_id, month_key(d))] += hours
                continue
            total = sum(day_items.values(), _ZERO)
            for item_id, h in day_items.items():
                actual_item_month[(item_id, month_key(d))] += hours * h / total

        # Approved payroll allocations, pro-rated by days into the worksite's range months.
        alloc_ws_month: dict[tuple[UUID, date], Decimal] = defaultdict(lambda: _ZERO)
        for ws_id, ps, pe, amount in allocs:
            r_from, r_to = ranges[ws_id]
            run_days = (pe - ps).days + 1
            for m_from, m_to in month_ranges(max(ps, r_from), min(pe, r_to)):
                days = (m_to - m_from).days + 1
                alloc_ws_month[(ws_id, month_key(m_from))] += amount * days / run_days

        out: list[WorksiteBudgetVsActualItem] = []
        for site_no, site in enumerate(sites):
            # Planning a site takes 2-5 ms; a turn every 10 lets other requests run (Batch 9).
            await yield_every(site_no, 10)
            assert site.id is not None
            r_from, r_to = ranges[site.id]
            plan = _plan_site(ctx, site, r_from, r_to, with_money=is_admin, strict=is_admin)
            money = is_admin and plan.money_ok
            out.append(
                _worksite_result(
                    site,
                    plan,
                    money,
                    is_admin,
                    actual_item_month,
                    sched_item_month,
                    unplanned_ws_month,
                    alloc_ws_month,
                    ctx,
                )
            )
        return out


def _worksite_result(
    site: SiteInput,
    plan: _SitePlan,
    money: bool,
    is_admin: bool,
    actual_item_month: dict[tuple[UUID, date], Decimal],
    sched_item_month: dict[tuple[UUID, date], Decimal],
    unplanned_ws_month: dict[tuple[UUID, date], Decimal],
    alloc_ws_month: dict[tuple[UUID, date], Decimal],
    ctx: _Context,
) -> WorksiteBudgetVsActualItem:
    assert site.id is not None
    ws_id = site.id
    month_starts = [m for m, _ in plan.months]

    def mk(d: date) -> date:
        return date(d.year, d.month, 1)

    # Actual hours per item per month (budget-only: actual = planned).
    item_actual_h: dict[UUID, dict[date, Decimal]] = {}
    for r in plan.items:
        iid = r.item.id
        assert iid is not None
        item_actual_h[iid] = {
            m: (
                r.month_hours[m] if r.is_budget_only else actual_item_month.get((iid, mk(m)), _ZERO)
            )
            for m in month_starts
        }

    # Actual cost per item per month: split each worksite-month allocation by approved hours
    # (scheduled hours when the month has none); budget-only items: actual = planned.
    item_actual_c: dict[UUID, dict[date, Decimal]] = defaultdict(dict)
    unallocated = _ZERO
    if money:
        field_items = [r for r in plan.items if not r.is_budget_only and r.item.id is not None]
        for m in month_starts:
            amount = alloc_ws_month.get((ws_id, mk(m)), _ZERO)
            if amount:
                weights: dict[object, Decimal] = {
                    r.item.id: item_actual_h[r.item.id][m]  # type: ignore[index]
                    for r in field_items
                    if item_actual_h[r.item.id][m] > 0  # type: ignore[index]
                }
                if not weights:
                    weights = {
                        r.item.id: sched_item_month.get((r.item.id, mk(m)), _ZERO)  # type: ignore[arg-type]
                        for r in field_items
                        if sched_item_month.get((r.item.id, mk(m)), _ZERO) > 0  # type: ignore[arg-type]
                    }
                shares = split_by_weights(amount, weights)
                if not shares:
                    unallocated += amount
                for iid, val in shares.items():
                    item_actual_c[iid][m] = val  # type: ignore[index]
        for r in plan.items:
            if r.is_budget_only and r.item.id is not None:
                for m in month_starts:
                    item_actual_c[r.item.id][m] = r.month_cost.get(m) or _ZERO

    items_out: list[PlannedActualItem] = []
    for r in plan.items:
        iid = r.item.id
        assert iid is not None
        months_out = []
        for m_from, m_to in plan.months:
            pc = r.month_cost.get(m_from) if money and r.has_line else None
            ac = item_actual_c[iid].get(m_from, _ZERO) if money and r.has_line else None
            months_out.append(
                PlannedActualMonth(
                    month_from=m_from,
                    month_to=m_to,
                    **_figures(r.month_hours[m_from], item_actual_h[iid][m_from], pc, ac),
                )
            )
        tot_ac = sum(item_actual_c[iid].values(), _ZERO) if money and r.has_line else None
        items_out.append(
            PlannedActualItem(
                job_item_id=iid,
                sub_item_code=r.item.sub_item_code,
                staff_grade_description=r.item.staff_grade_description,
                grade_code=r.item.planned_grade_code,
                is_budget_only=r.is_budget_only,
                is_active=r.item.is_active,
                excluded_from_totals=not r.has_line,
                hourly_rate=r.hourly_rate if money else None,
                months=months_out,
                **_figures(
                    r.hours,
                    sum(item_actual_h[iid].values(), _ZERO),
                    r.cost if money and r.has_line else None,
                    tot_ac,
                ),
            )
        )

    # Worksite months. Planned: items in totals (or the manual annual budget, pro-rated by day).
    in_totals = [r for r in plan.items if r.in_totals]
    override = site.budget_amount if site.budget_amount and site.budget_amount > 0 else None
    ws_months: list[PlannedActualMonth] = []
    tot_ph = tot_ah = _ZERO
    tot_pc = tot_ac_ws = _ZERO
    unplanned_total = _ZERO
    for m_from, m_to in plan.months:
        ph = sum((r.month_hours[m_from] for r in in_totals), _ZERO)
        unpl = unplanned_ws_month.get((ws_id, mk(m_from)), _ZERO)
        unplanned_total += unpl
        ah = (
            sum(
                (item_actual_h[r.item.id][m_from] for r in plan.items if r.item.id is not None),
                _ZERO,
            )
            + unpl
        )
        pc: Decimal | None = None
        ac: Decimal | None = None
        if money:
            if override is not None:
                win = active_window(
                    m_from, m_to, None, None, site.contract_start, site.contract_end
                )
                frac = year_fraction(win[0], win[1], site.contract_start) if win else _ZERO
                pc = round_money(override * frac)
            else:
                pc = round_money(sum((r.month_cost.get(m_from) or _ZERO for r in in_totals), _ZERO))
            budget_only_c = sum(
                (
                    r.month_cost.get(m_from) or _ZERO
                    for r in plan.items
                    if r.is_budget_only and r.item.is_active
                ),
                _ZERO,
            )
            ac = round_money(alloc_ws_month.get((ws_id, mk(m_from)), _ZERO) + budget_only_c)
            tot_pc += pc
            tot_ac_ws += ac
        tot_ph += ph
        tot_ah += ah
        ws_months.append(
            PlannedActualMonth(month_from=m_from, month_to=m_to, **_figures(ph, ah, pc, ac))
        )

    # Annual figures (current contract year containing the range start), kept for old callers.
    annual_from, annual_to = contract_year_containing(plan.period_from, site.contract_start)
    if (annual_from, annual_to) == (plan.period_from, plan.period_to):
        annual_hours = tot_ph
        annual_cost = tot_pc if money else None
    else:
        annual_plan = _plan_site(ctx, site, annual_from, annual_to, with_money=money, strict=False)
        annual_hours = sum((r.hours for r in annual_plan.items if r.in_totals), _ZERO)
        annual_cost = (
            round_money(sum((r.cost or _ZERO for r in annual_plan.items if r.in_totals), _ZERO))
            if money
            else None
        )
    if money and override is not None:
        annual_cost = override

    totals = _figures(tot_ph, tot_ah, tot_pc if money else None, tot_ac_ws if money else None)
    rev_code = site.salary_revision_code or (plan.revision.code if plan.revision else None)
    var = totals.get("cost_diff")
    return WorksiteBudgetVsActualItem(
        worksite_id=ws_id,
        job_number=site.job_number,
        job_name=site.job_name,
        country=site.country,
        period_from=plan.period_from,
        period_to=plan.period_to,
        revision_code=plan.revision.code if plan.revision else None,
        unplanned_hours=unplanned_total.quantize(_H),
        unallocated_actual_cost=round_money(unallocated) if money else None,
        items=items_out,
        months=ws_months,
        warnings=plan.warnings if is_admin else _hours_only(plan.warnings),
        missing_rate_hours=sum(
            (r.hours for r in plan.items if r.item.is_active and not r.has_line), _ZERO
        ).quantize(_H),
        salary_revision_code=rev_code,
        assigned_revision_code=rev_code,
        annual_planned_man_hours=annual_hours.quantize(_H),
        annual_labor_budget=annual_cost,
        prorated_budget=totals.get("planned_cost"),
        pro_rated_budget=totals.get("planned_cost"),
        actual_cost_allocated=totals.get("actual_cost"),
        actual_allocated_cost=totals.get("actual_cost"),
        variance=var,
        variance_amount=var,
        variance_percent=totals.get("cost_diff_pct"),
        is_over_budget=(var > 0) if var is not None else None,
        is_under_budget=(var < 0) if var is not None else None,
        manual_budget_override=site.budget_amount if is_admin else None,
        is_custom_budget_override=bool(override) and is_admin,
        **totals,
    )


__all__ = ["BudgetService", "ItemInput", "PlannedActualFigures", "default_period"]
