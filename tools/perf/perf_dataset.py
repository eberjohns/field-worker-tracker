"""Pure builders for the scaled mock dataset used to measure speed (Batch 9 step 1).

MOCK DATA ONLY: invented names ("Perf Worker 0001"), Tally IDs (PF00001…), salaries and square
polygons inside a Dubai / Riyadh box. Nothing here comes from client files. The builders are
deterministic for a given seed and touch no database; ``seed_perf_dataset.py`` writes them.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

# Fridays off for everyone; 6-day items cover the other six days, 3-day items alternate.
WEEKLY_OFF = "FRIDAY"
SIX_DAYS = ["SAT", "SUN", "MON", "TUE", "WED", "THU"]
ALT_A = ["SAT", "MON", "WED"]
ALT_B = ["SUN", "TUE", "THU"]
PY_WEEKDAY = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}

STAFF_TYPES = (
    "Gardener Helper",
    "Gardener Expert",
    "Irrigation Technician",
    "Palm Tree Technician",
    "Team Leader",
)
GRADE_CODES = ("G1A", "G1B", "G2A", "G2B", "G3A")
GRADE_BASIC = {"G1A": 900, "G1B": 1000, "G2A": 1200, "G2B": 1400, "G3A": 1800}

# (min lon, min lat, max lon, max lat)
BOX = {"AE": (55.05, 24.95, 55.45, 25.30), "SA": (46.55, 24.60, 46.85, 24.85)}
SITE_HALF_SIDE_DEG = 0.0006  # about 65 m


@dataclass(frozen=True)
class Scale:
    employees: int = 600  # workers + supervisors + engineers
    worksites: int = 400
    job_items: int = 1500
    groups: int = 20
    zones: int = 30
    supervisors: int = 25
    engineers: int = 5
    sa_share: float = 0.10  # share of SA worksites
    six_day_share: float = 0.30  # share of 6-day job items
    single_item_share: float = 0.40  # workers on one 6-day item (the rest take an A and a B item)
    leave_share: float = 0.03  # workers with one approved week of leave
    absent_rate: float = 0.04  # past worker-days with no visit at all

    def scaled(self, factor: float) -> Scale:
        """A smaller copy for tests and dry runs (at least one of everything)."""

        def n(v: int) -> int:
            return max(1, round(v * factor))

        return Scale(
            employees=max(4, n(self.employees)),
            worksites=n(self.worksites),
            job_items=max(2, n(self.job_items)),
            groups=n(self.groups),
            zones=n(self.zones),
            supervisors=n(self.supervisors),
            engineers=n(self.engineers),
            sa_share=self.sa_share,
            six_day_share=self.six_day_share,
            single_item_share=self.single_item_share,
            leave_share=self.leave_share,
            absent_rate=self.absent_rate,
        )


@dataclass
class SiteSpec:
    index: int
    job_number: str
    job_name: str
    country: str
    group_index: int
    zone_index: int
    lon: float
    lat: float
    budget: Decimal

    @property
    def wkt(self) -> str:
        d = SITE_HALF_SIDE_DEG
        x0, y0, x1, y1 = self.lon - d, self.lat - d, self.lon + d, self.lat + d
        return (
            f"POLYGON(({x0:.6f} {y0:.6f}, {x1:.6f} {y0:.6f}, {x1:.6f} {y1:.6f}, {x0:.6f} {y1:.6f}, {x0:.6f} {y0:.6f}))"
        )


@dataclass
class ItemSpec:
    index: int
    site_index: int
    sub_item_code: str
    staff_type: str
    grade_code: str
    weekdays: list[str]
    required_staff: int
    hours: Decimal


@dataclass
class EmployeeSpec:
    index: int
    tally_id: str
    name: str
    role: str  # WORKER | SUPERVISOR | ENGINEER
    country: str
    grade_code: str
    staff_type: str
    basic: Decimal


@dataclass
class AssignmentSpec:
    employee_index: int
    item_index: int
    weekdays: list[str]
    hours: Decimal


@dataclass
class Dataset:
    scale: Scale
    sites: list[SiteSpec] = field(default_factory=list)
    items: list[ItemSpec] = field(default_factory=list)
    employees: list[EmployeeSpec] = field(default_factory=list)
    assignments: list[AssignmentSpec] = field(default_factory=list)
    supervisors_by_site: dict[int, list[int]] = field(default_factory=dict)
    leave_weeks: dict[int, date] = field(default_factory=dict)  # employee index -> first leave day

    @property
    def workers(self) -> list[EmployeeSpec]:
        return [e for e in self.employees if e.role == "WORKER"]


def stable_uuid(rng: random.Random) -> UUID:
    """A UUID from the seeded generator, so ids repeat between runs with the same seed."""
    return UUID(int=rng.getrandbits(128), version=4)


def _sub_code(n: int) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return letters[n] if n < 26 else letters[n // 26 - 1] + letters[n % 26]


def build_dataset(scale: Scale, seed: int = 42, history_start: date = date(2026, 9, 1)) -> Dataset:
    rng = random.Random(seed)
    ds = Dataset(scale=scale)

    n_sa = round(scale.worksites * scale.sa_share)
    for i in range(scale.worksites):
        country = "SA" if i >= scale.worksites - n_sa else "AE"
        x0, y0, x1, y1 = BOX[country]
        ds.sites.append(
            SiteSpec(
                index=i,
                job_number=f"77P{i + 1:05d}",
                job_name=f"Perf Site {i + 1:04d}",
                country=country,
                group_index=i % scale.groups,
                zone_index=i % scale.zones,
                lon=round(rng.uniform(x0, x1), 6),
                lat=round(rng.uniform(y0, y1), 6),
                budget=Decimal(rng.randrange(60_000, 900_000, 500)),
            )
        )

    per_site: dict[int, int] = {}
    n_six = round(scale.job_items * scale.six_day_share)
    for j in range(scale.job_items):
        site = j % scale.worksites
        k = per_site.get(site, 0)
        per_site[site] = k + 1
        if j < n_six:
            weekdays = SIX_DAYS
        else:
            weekdays = ALT_A if (j - n_six) % 2 == 0 else ALT_B
        ds.items.append(
            ItemSpec(
                index=j,
                site_index=site,
                sub_item_code=_sub_code(k),
                staff_type=STAFF_TYPES[j % len(STAFF_TYPES)],
                grade_code=GRADE_CODES[j % len(GRADE_CODES)],
                weekdays=list(weekdays),
                required_staff=1 if rng.random() < 0.8 else 2,
                hours=Decimal("8.0"),
            )
        )

    n_workers = scale.employees - scale.supervisors - scale.engineers
    six = [it for it in ds.items if it.weekdays == SIX_DAYS]
    alt_a = [it for it in ds.items if it.weekdays == ALT_A]
    alt_b = [it for it in ds.items if it.weekdays == ALT_B]
    n_single = round(n_workers * scale.single_item_share)
    for w in range(n_workers):
        if (w < n_single and six) or not (alt_a and alt_b):
            first = six[w % len(six)]
            ds.assignments.append(AssignmentSpec(w, first.index, list(SIX_DAYS), first.hours))
        else:
            k = w - n_single
            first = alt_a[k % len(alt_a)]
            second = alt_b[k % len(alt_b)]
            ds.assignments.append(AssignmentSpec(w, first.index, list(ALT_A), first.hours))
            ds.assignments.append(AssignmentSpec(w, second.index, list(ALT_B), second.hours))
        grade = first.grade_code
        ds.employees.append(
            EmployeeSpec(
                index=w,
                tally_id=f"PF{w + 1:05d}",
                name=f"Perf Worker {w + 1:04d}",
                role="WORKER",
                country=ds.sites[first.site_index].country,
                grade_code=grade,
                staff_type=first.staff_type,
                basic=Decimal(GRADE_BASIC[grade]),
            )
        )

    for s in range(scale.supervisors):
        idx = n_workers + s
        ds.employees.append(
            EmployeeSpec(
                index=idx,
                tally_id=f"PF{idx + 1:05d}",
                name=f"Perf Supervisor {s + 1:02d}",
                role="SUPERVISOR",
                country="AE",
                grade_code="G3A",
                staff_type="Supervisor",
                basic=Decimal(3500),
            )
        )
    for e in range(scale.engineers):
        idx = n_workers + scale.supervisors + e
        ds.employees.append(
            EmployeeSpec(
                index=idx,
                tally_id=f"PF{idx + 1:05d}",
                name=f"Perf Engineer {e + 1:02d}",
                role="ENGINEER",
                country="AE",
                grade_code="G3A",
                staff_type="Superintendent",
                basic=Decimal(6000),
            )
        )

    first_supervisor = n_workers
    for site in ds.sites:
        a = first_supervisor + site.index % scale.supervisors
        b = first_supervisor + (site.index + 7) % scale.supervisors
        ds.supervisors_by_site[site.index] = sorted({a, b})

    n_leave = round(n_workers * scale.leave_share)
    for w in rng.sample(range(n_workers), n_leave):
        ds.leave_weeks[w] = history_start + timedelta(days=rng.randrange(0, 70))

    return ds


def work_dates(weekdays: list[str], start: date, end: date) -> list[date]:
    """The dates from start to end (inclusive) that fall on these weekdays."""
    wanted = {PY_WEEKDAY[d] for d in weekdays}
    out: list[date] = []
    d = start
    while d <= end:
        if d.weekday() in wanted:
            out.append(d)
        d += timedelta(days=1)
    return out


def on_leave(ds: Dataset, employee_index: int, day: date) -> bool:
    first = ds.leave_weeks.get(employee_index)
    return first is not None and first <= day < first + timedelta(days=7)
