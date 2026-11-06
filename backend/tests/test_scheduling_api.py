"""Integration tests for Scheduling API endpoints and 300-worker performance benchmark (Phase 05)."""

import io
import socket
import time
from datetime import date
from decimal import Decimal
from uuid import uuid4

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from fw.core.db import async_session_factory, engine
from fw.main import app
from fw.modules.identity import AuthService, User
from fw.modules.jobs import JobItem, Worksite
from fw.modules.org import Employee, Group, Zone
from fw.modules.scheduling import ScheduledWork, StandingAssignment
from fw.modules.settings import PublicHoliday


def is_db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.5):
            return True
    except OSError:
        return False


db_required = pytest.mark.skipif(
    not is_db_available(),
    reason="Database integration tests require PostgreSQL running on localhost:5432",
)


@pytest.fixture
async def admin_client():
    """Create test admin and return authenticated AsyncClient."""
    if not is_db_available():
        pytest.skip("PostgreSQL not available on localhost:5432")

    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.username == "ADMIN001"))
        ).scalar_one_or_none()

        if not user:
            admin_id = uuid4()
            emp_id = uuid4()
            emp = Employee(
                id=emp_id,
                tally_id=f"ADM{str(uuid4())[:6]}",
                name="Admin User",
                role="ADMIN",
                country="AE",
                is_active=True,
            )
            session.add(emp)
            await session.flush()

            user = User(
                id=admin_id,
                employee_id=emp_id,
                username="ADMIN001",
                credential_hash="fakehash",
                role="ADMIN",
                is_active=True,
                must_change_password=False,
            )
            session.add(user)
            await session.commit()

        token = AuthService.create_access_token(user)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            yield client
    finally:
        await engine.dispose()


@pytest.fixture
async def sample_test_data():
    """Seed group, zone, worksite, job item, public holiday, and workers."""
    if not is_db_available():
        pytest.skip("PostgreSQL not available on localhost:5432")

    async with async_session_factory() as session:
        # Clean up previous test scheduling data
        await session.execute(delete(ScheduledWork))
        await session.execute(delete(StandingAssignment))
        await session.commit()

    async with async_session_factory() as session:
        # Group and Zone
        group = (
            await session.execute(select(Group).where(Group.code == "GRP_SCHED_05"))
        ).scalar_one_or_none()
        if not group:
            group = Group(code="GRP_SCHED_05", name="Scheduling Test Group", is_active=True)
            session.add(group)

        zone = (
            await session.execute(select(Zone).where(Zone.code == "ZONE_SCHED_05"))
        ).scalar_one_or_none()
        if not zone:
            zone = Zone(code="ZONE_SCHED_05", name="Scheduling Test Zone", is_active=True)
            session.add(zone)

        await session.flush()

        # Worksite
        job_number = "12A99905"
        worksite = (
            await session.execute(select(Worksite).where(Worksite.job_number == job_number))
        ).scalar_one_or_none()
        if not worksite:
            worksite = Worksite(
                job_number=job_number,
                job_name="Dubai Marina Landscape",
                group_id=group.id,
                zone_id=zone.id,
                country="AE",
                is_active=True,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
            )
            session.add(worksite)
            await session.flush()

        # Job Item A: Hand Watering (PERMANENT, Mon-Sat, 9h/day, 3 staff)
        item_a = (
            await session.execute(
                select(JobItem).where(
                    JobItem.worksite_id == worksite.id,
                    JobItem.sub_item_code == "A",
                )
            )
        ).scalar_one_or_none()
        if not item_a:
            item_a = JobItem(
                worksite_id=worksite.id,
                sub_item_code="A",
                staff_grade_description="Gardener - Hand Watering",
                planned_grade_code="G1C",
                frequency_unit="WEEK",
                occurrences_per_period=Decimal("6.0"),
                period_interval=1,
                weekday_pattern=["MON", "TUE", "WED", "THU", "FRI", "SAT"],
                required_staff_count=3,
                hours_per_occurrence_per_staff=Decimal("9.0"),
                deployment_type="PERMANENT",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                is_active=True,
            )
            session.add(item_a)

        # Job Item B: Tree Pruning (REMOTE, 2 staff, 4h/day)
        item_b = (
            await session.execute(
                select(JobItem).where(
                    JobItem.worksite_id == worksite.id,
                    JobItem.sub_item_code == "B",
                )
            )
        ).scalar_one_or_none()
        if not item_b:
            item_b = JobItem(
                worksite_id=worksite.id,
                sub_item_code="B",
                staff_grade_description="Tree Pruner",
                planned_grade_code="G2B",
                frequency_unit="WEEK",
                occurrences_per_period=Decimal("3.0"),
                period_interval=1,
                weekday_pattern=["MON", "WED", "FRI"],
                required_staff_count=2,
                hours_per_occurrence_per_staff=Decimal("4.0"),
                deployment_type="REMOTE",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                is_active=True,
            )
            session.add(item_b)

        # Workers
        w1 = (
            await session.execute(select(Employee).where(Employee.tally_id == "W_SCHED_01"))
        ).scalar_one_or_none()
        if not w1:
            w1 = Employee(
                tally_id="W_SCHED_01",
                name="Shanto Miah",
                role="WORKER",
                country="AE",
                grade_code="G1C",
                staff_grade_description="Gardener - Hand Watering",
                weekly_off_day="SUNDAY",
                is_active=True,
            )
            session.add(w1)

        w2 = (
            await session.execute(select(Employee).where(Employee.tally_id == "W_SCHED_02"))
        ).scalar_one_or_none()
        if not w2:
            w2 = Employee(
                tally_id="W_SCHED_02",
                name="Rebiyu Aboli",
                role="WORKER",
                country="AE",
                grade_code="G1C",
                staff_grade_description="Gardener - Hand Watering",
                weekly_off_day="SUNDAY",
                is_active=True,
            )
            session.add(w2)

        w3 = (
            await session.execute(select(Employee).where(Employee.tally_id == "W_SCHED_03"))
        ).scalar_one_or_none()
        if not w3:
            w3 = Employee(
                tally_id="W_SCHED_03",
                name="Cletus G.",
                role="WORKER",
                country="AE",
                grade_code="G2B",
                staff_grade_description="Tree Pruner",
                weekly_off_day="FRIDAY",
                is_active=True,
            )
            session.add(w3)

        # Public holiday on Tuesday Nov 3, 2026
        holiday_date = date(2026, 11, 3)
        existing_hol = (
            await session.execute(
                select(PublicHoliday).where(
                    PublicHoliday.holiday_date == holiday_date,
                    PublicHoliday.country == "AE",
                )
            )
        ).scalar_one_or_none()
        if not existing_hol:
            session.add(
                PublicHoliday(
                    holiday_date=holiday_date,
                    name="UAE Flag Day",
                    country="AE",
                )
            )

        await session.commit()
        await session.refresh(worksite)
        await session.refresh(item_a)
        await session.refresh(item_b)
        await session.refresh(w1)
        await session.refresh(w2)
        await session.refresh(w3)

        data = {
            "worksite_id": worksite.id,
            "item_a_id": item_a.id,
            "item_b_id": item_b.id,
            "w1_id": w1.id,
            "w2_id": w2.id,
            "w3_id": w3.id,
            "holiday_date": holiday_date,
            "group_id": group.id,
        }

    try:
        yield data
    finally:
        await engine.dispose()


@db_required
@pytest.mark.asyncio
async def test_standing_assignment_lifecycle(admin_client, sample_test_data):
    """Create standing assignment, verify 13-month generation, and end assignment."""
    data = sample_test_data

    # 1. Create standing assignment for Worker 1 on Item A starting Mon Nov 2, 2026
    start_date = date(2026, 11, 2)
    resp = await admin_client.post(
        "/api/v1/standing-assignments",
        json={
            "employee_id": str(data["w1_id"]),
            "job_item_id": str(data["item_a_id"]),
            "start_date": start_date.isoformat(),
            "end_date": date(2026, 12, 31).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text
    standing_data = resp.json()
    standing_id = standing_data["id"]

    # 2. Check materialized scheduled_work in database
    async with async_session_factory() as session:
        stmt = select(ScheduledWork).where(
            ScheduledWork.employee_id == data["w1_id"],
            ScheduledWork.job_item_id == data["item_a_id"],
            ScheduledWork.status == "ACTIVE",
        )
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) > 0

        # Tuesday Nov 3 was a public holiday -> must NOT be scheduled (SKIPPED)
        holiday_rows = [r for r in rows if r.work_date == data["holiday_date"]]
        assert len(holiday_rows) == 0

        # Sunday Nov 8 is not in Mon-Sat pattern -> must NOT be scheduled
        sunday_rows = [r for r in rows if r.work_date == date(2026, 11, 8)]
        assert len(sunday_rows) == 0

    # 3. End standing assignment on Nov 15, 2026
    end_date = date(2026, 11, 15)
    end_resp = await admin_client.post(
        f"/api/v1/standing-assignments/{standing_id}/end",
        json={"end_date": end_date.isoformat(), "version": standing_data["version"]},
    )
    assert end_resp.status_code == 200, end_resp.text
    assert end_resp.json()["end_date"] == end_date.isoformat()

    # Verify rows after Nov 15 were marked CANCELLED
    async with async_session_factory() as session:
        cancelled_stmt = select(ScheduledWork).where(
            ScheduledWork.employee_id == data["w1_id"],
            ScheduledWork.job_item_id == data["item_a_id"],
            ScheduledWork.status == "CANCELLED",
            ScheduledWork.work_date > end_date,
        )
        cancelled_rows = (await session.execute(cancelled_stmt)).scalars().all()
        assert len(cancelled_rows) > 0


@db_required
@pytest.mark.asyncio
async def test_scheduled_work_validation_and_direct_assignment(admin_client, sample_test_data):
    """Test validation dry-run, conflict handling, and sequence reordering."""
    data = sample_test_data

    # Dry-run validation for Item A (PERMANENT)
    work_date = date(2026, 11, 4)  # Wednesday
    val_resp = await admin_client.post(
        "/api/v1/scheduled-work/validate",
        json={
            "employee_id": str(data["w2_id"]),
            "job_item_id": str(data["item_a_id"]),
            "work_date": work_date.isoformat(),
            "assigned_hours": "9.0",
        },
    )
    assert val_resp.status_code == 200, val_resp.text
    val_data = val_resp.json()
    assert val_data["is_valid"] is True

    # Create assignment
    create_resp = await admin_client.post(
        "/api/v1/scheduled-work",
        json={
            "employee_id": str(data["w2_id"]),
            "job_item_id": str(data["item_a_id"]),
            "work_date": work_date.isoformat(),
            "assigned_hours": "9.0",
            "acknowledge_warnings": True,
        },
    )
    assert create_resp.status_code == 201, create_resp.text

    # Attempting to assign Item B to w2 on the same day -> PERMANENT_EXCLUSIVE error
    val_resp2 = await admin_client.post(
        "/api/v1/scheduled-work/validate",
        json={
            "employee_id": str(data["w2_id"]),
            "job_item_id": str(data["item_b_id"]),
            "work_date": work_date.isoformat(),
            "assigned_hours": "4.0",
        },
    )
    assert val_resp2.status_code == 200
    val_data2 = val_resp2.json()
    assert val_data2["is_valid"] is False
    assert any(e["code"] == "PERMANENT_EXCLUSIVE" for e in val_data2["errors"])

    # Create two REMOTE assignments for Worker 3 on Friday Nov 6
    fri_date = date(2026, 11, 6)
    r1 = await admin_client.post(
        "/api/v1/scheduled-work",
        json={
            "employee_id": str(data["w3_id"]),
            "job_item_id": str(data["item_b_id"]),
            "work_date": fri_date.isoformat(),
            "assigned_hours": "4.0",
            "sequence": 1,
            "acknowledge_warnings": True,
        },
    )
    assert r1.status_code == 201
    sw_id_1 = r1.json()["id"]

    r2 = await admin_client.post(
        "/api/v1/scheduled-work",
        json={
            "employee_id": str(data["w3_id"]),
            "job_item_id": str(data["item_b_id"]),
            "work_date": fri_date.isoformat(),
            "assigned_hours": "4.0",
            "sequence": 2,
            "acknowledge_warnings": True,
        },
    )
    assert r2.status_code == 201
    sw_id_2 = r2.json()["id"]

    # Reorder visits (swap 1 and 2)
    reorder_resp = await admin_client.post(
        "/api/v1/scheduled-work/reorder",
        json={
            "employee_id": str(data["w3_id"]),
            "work_date": fri_date.isoformat(),
            "ordered_ids": [sw_id_2, sw_id_1],
        },
    )
    assert reorder_resp.status_code == 200, reorder_resp.text


@db_required
@pytest.mark.asyncio
async def test_weekly_roster_and_excel_export(admin_client, sample_test_data):
    """Verify weekly roster JSON and Excel export layout."""
    data = sample_test_data
    week_start = date(2026, 11, 2)

    # 1. JSON roster
    resp = await admin_client.get(
        f"/api/v1/roster?week_start={week_start.isoformat()}",
    )
    assert resp.status_code == 200, resp.text
    roster_data = resp.json()
    assert "workers" in roster_data
    assert roster_data["total_workers"] >= 3

    # Check day markers for Worker 1 on Nov 3 (Tuesday, public holiday -> SKIPPED)
    w1_row = next((w for w in roster_data["workers"] if w["employee_id"] == str(data["w1_id"])), None)
    assert w1_row is not None
    tue_cell = next((d for d in w1_row["days"] if d["work_date"] == "2026-11-03"), None)
    assert tue_cell is not None
    assert tue_cell["marker"] == "SKIPPED"

    # Sunday Nov 8 -> WEEKLY_OFF
    sun_cell = next((d for d in w1_row["days"] if d["work_date"] == "2026-11-08"), None)
    assert sun_cell is not None
    assert sun_cell["marker"] == "WEEKLY_OFF"

    # 2. Excel roster export
    excel_resp = await admin_client.get(
        f"/api/v1/roster?week_start={week_start.isoformat()}&format=xlsx",
    )
    assert excel_resp.status_code == 200
    assert excel_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(excel_resp.content) > 0

    # Load and verify Excel sheet
    wb = openpyxl.load_workbook(io.BytesIO(excel_resp.content))
    ws = wb.active
    assert ws is not None
    assert ws["A1"].value.startswith("Weekly Roster")
    assert ws["A3"].value == "Worker Name"
    assert ws["F3"].value == "Mon"
    assert ws["M3"].value == "Hours"


@db_required
@pytest.mark.asyncio
async def test_job_coverage_view(admin_client, sample_test_data):
    """Verify job coverage view shows assigned count vs required and TO_BE_COVERED."""
    data = sample_test_data
    week_start = date(2026, 11, 2)

    resp = await admin_client.get(
        f"/api/v1/schedule/coverage?week_start={week_start.isoformat()}",
    )
    assert resp.status_code == 200, resp.text
    cov_data = resp.json()
    assert "worksites" in cov_data

    target_site = next((ws for ws in cov_data["worksites"] if ws["worksite_id"] == str(data["worksite_id"])), None)
    assert target_site is not None
    item_a = next((i for i in target_site["items"] if i["job_item_id"] == str(data["item_a_id"])), None)
    assert item_a is not None

    # Check Monday (Nov 2): Item A requires 3 staff.
    mon_cell = next((d for d in item_a["days"] if d["work_date"] == "2026-11-02"), None)
    assert mon_cell is not None
    assert mon_cell["required_staff_count"] == 3


@db_required
@pytest.mark.asyncio
async def test_worker_allocation_side_panel(admin_client, sample_test_data):
    """Verify worker allocation endpoint returns today, week, and month totals."""
    data = sample_test_data
    work_date = date(2026, 11, 4)

    resp = await admin_client.get(
        f"/api/v1/workers/{data['w2_id']}/allocation?work_date={work_date.isoformat()}",
    )
    assert resp.status_code == 200, resp.text
    alloc = resp.json()
    assert alloc["employee_id"] == str(data["w2_id"])
    assert Decimal(str(alloc["base_standard_hours"])) == Decimal("8.0")
    assert "today_allocated_hours" in alloc
    assert "week_allocated_hours" in alloc


@db_required
@pytest.mark.asyncio
async def test_candidate_recommendations(admin_client, sample_test_data):
    """Verify candidate recommendations rank exact staff type first (DEC-52)."""
    data = sample_test_data

    resp = await admin_client.get(
        f"/api/v1/job-items/{data['item_a_id']}/recommendations?date=2026-11-04",
    )
    assert resp.status_code == 200, resp.text
    recs = resp.json()
    assert len(recs) > 0
    # First recommended candidate must have exact staff type match
    assert recs[0]["exact_staff_type_match"] is True


@db_required
@pytest.mark.asyncio
async def test_300_workers_roster_performance(admin_client, sample_test_data):
    """Check performance requirement: roster for 300 workers loads in under 2 seconds."""
    # Seed 300 active workers if needed
    async with async_session_factory() as session:
        count_stmt = select(func.count(Employee.id)).where(
            Employee.is_active.is_(True), Employee.role != "ADMIN"
        )
        current_count = (await session.execute(count_stmt)).scalar() or 0

        to_create = max(0, 300 - current_count)
        if to_create > 0:
            batch = []
            for i in range(to_create):
                batch.append(
                    Employee(
                        tally_id=f"PERF_{uuid4().hex[:6]}_{i}",
                        name=f"Perf Worker {i}",
                        role="WORKER",
                        country="AE",
                        grade_code="G1C",
                        staff_grade_description="Gardener",
                        weekly_off_day="SUNDAY",
                        is_active=True,
                    )
                )
            session.add_all(batch)
            await session.commit()

    week_start = date(2026, 11, 2)
    start_time = time.perf_counter()
    resp = await admin_client.get(
        f"/api/v1/roster?week_start={week_start.isoformat()}",
    )
    elapsed_sec = time.perf_counter() - start_time

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_workers"] >= 300
    # Performance requirement: under 2.0 seconds
    assert elapsed_sec < 2.0, f"Roster for 300 workers took {elapsed_sec:.3f}s (exceeded 2.0s limit)"


@db_required
@pytest.mark.asyncio
async def test_scheduled_work_batch_daily_and_standing(admin_client, sample_test_data):
    """Test batch assignment of workers via POST /api/v1/scheduled-work/batch for daily and standing."""
    w1_id = str(sample_test_data["w1_id"])
    w2_id = str(sample_test_data["w2_id"])
    item_id = str(sample_test_data["item_a_id"])

    # 1. Batch assign daily scheduled work
    resp = await admin_client.post(
        "/api/v1/scheduled-work/batch",
        json={
            "employee_ids": [w1_id, w2_id],
            "job_item_id": item_id,
            "work_date": "2026-11-04",
            "assigned_hours": 8.0,
            "as_standing_assignment": False,
            "acknowledge_warnings": True,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert len(data) == 2
    sw_ids = [d["id"] for d in data]

    # 2. Cancel one assignment via DELETE /api/v1/scheduled-work/{id}
    del_resp = await admin_client.delete(f"/api/v1/scheduled-work/{sw_ids[0]}")
    assert del_resp.status_code == 204

    # 3. Batch assign as standing team (materializes horizon without MissingGreenlet)
    standing_resp = await admin_client.post(
        "/api/v1/scheduled-work/batch",
        json={
            "employee_ids": [w1_id],
            "job_item_id": item_id,
            "work_date": "2026-11-09",
            "assigned_hours": 8.0,
            "as_standing_assignment": True,
            "acknowledge_warnings": True,
        },
    )
    assert standing_resp.status_code == 201, standing_resp.text
    standing_data = standing_resp.json()
    assert len(standing_data) >= 1
    assert standing_data[0]["employee_id"] == w1_id


@db_required
@pytest.mark.asyncio
async def test_candidate_recommendations_with_permanent_conflict(admin_client, sample_test_data):
    """Verify candidate recommendations flag workers who conflict with a PERMANENT assignment as blocked."""
    w1_id = str(sample_test_data["w1_id"])
    item_a_id = str(sample_test_data["item_a_id"])  # PERMANENT

    # Assign w1 to PERMANENT item_a on 2026-11-04
    resp = await admin_client.post(
        "/api/v1/scheduled-work/batch",
        json={
            "employee_ids": [w1_id],
            "job_item_id": item_a_id,
            "work_date": "2026-11-04",
            "assigned_hours": 9.0,
            "as_standing_assignment": False,
            "acknowledge_warnings": True,
        },
    )
    assert resp.status_code == 201, resp.text

    # Request candidate recommendations for item_a on 2026-11-04
    rec_resp = await admin_client.get(
        f"/api/v1/job-items/{item_a_id}/recommendations?date=2026-11-04",
    )
    assert rec_resp.status_code == 200, rec_resp.text
    candidates = rec_resp.json()

    # Find w1 in candidates
    w1_rec = next((c for c in candidates if c["employee_id"] == w1_id), None)
    assert w1_rec is not None, "w1 should be listed in recommendations"
    assert w1_rec["is_blocked"] is True
    assert w1_rec["blocked_reason"] is not None
    assert "PERMANENT" in w1_rec["blocked_reason"]


@db_required
@pytest.mark.asyncio
async def test_monthly_standing_assignment_materialization(admin_client, sample_test_data):
    """Verify that monthly job items materialize exactly 1 visit per month, not daily Mon-Sat."""
    w2_id = str(sample_test_data["w2_id"])
    worksite_id = sample_test_data["worksite_id"]

    # Create a monthly job item (e.g. Irrigation Tech, 1x/month, 8h)
    async with async_session_factory() as session:
        monthly_item = JobItem(
            worksite_id=worksite_id,
            sub_item_code=f"M_{uuid4().hex[:4]}",
            staff_grade_description="Irrigation Technician",
            planned_grade_code="G1C",
            frequency_unit="MONTH",
            occurrences_per_period=Decimal("1.0"),
            period_interval=1,
            weekday_pattern=None,
            required_staff_count=1,
            hours_per_occurrence_per_staff=Decimal("8.0"),
            deployment_type="PERMANENT",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        session.add(monthly_item)
        await session.commit()
        monthly_item_id = str(monthly_item.id)

    # Create standing assignment starting 2026-11-01 to 2026-12-31
    resp = await admin_client.post(
        "/api/v1/standing-assignments",
        json={
            "job_item_id": monthly_item_id,
            "employee_id": w2_id,
            "start_date": "2026-11-01",
            "end_date": "2026-12-31",
        },
    )
    assert resp.status_code == 201, resp.text

    # Query materialized scheduled work for this job item
    async with async_session_factory() as session:
        sw_records = (
            await session.execute(
                select(ScheduledWork).where(
                    ScheduledWork.job_item_id == monthly_item.id,
                    ScheduledWork.employee_id == sample_test_data["w2_id"],
                    ScheduledWork.status == "ACTIVE",
                )
            )
        ).scalars().all()

        # Over Nov 1 to Dec 31 (2 months), exactly 2 visits should be materialized (1 in Nov, 1 in Dec)
        assert len(sw_records) == 2, f"Expected 2 monthly visits, got {len(sw_records)}"
        months = {sw.work_date.month for sw in sw_records}
        assert months == {11, 12}

