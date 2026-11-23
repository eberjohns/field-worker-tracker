"""Batch 5.1 B: a worksite with its job items and supervisors, created in one transaction."""

from datetime import timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from fw.core.clock import site_today
from fw.core.db import async_session_factory
from fw.main import create_app
from fw.modules.audit.models import AuditLog
from fw.modules.jobs.models import JobItem, JobOccurrence, Worksite, WorksiteSupervisor
from fw.modules.org.models import Employee, Group, Zone
from tests.ids import unique_job_number
from tests.test_batch6_features import db_required, get_admin_user_and_token
from tests.test_dec57_scope import _h, _person

STAFF_TYPE = "Gardener Helper"


def _item(code: str, **over: object) -> dict[str, object]:
    item: dict[str, object] = {
        "sub_item_code": code,
        "staff_grade_description": STAFF_TYPE,
        "planned_grade_code": "G1A",
        "frequency_unit": "WEEK",
        "occurrences_per_period": 6,
        "period_interval": 1,
        "weekday_pattern": ["MON", "TUE", "WED", "THU", "FRI", "SAT"],
        "required_staff_count": 2,
        "hours_per_occurrence_per_staff": 8,
        "start_date": str(site_today("AE") - timedelta(days=10)),
        "deployment_type": "PERMANENT",
    }
    item.update(over)
    return item


async def _setup() -> tuple[dict[str, str], dict[str, str], dict[str, object], list[str]]:
    """Admin and Engineer headers, a worksite body (no items) and two supervisor ids."""
    async with async_session_factory() as session:
        _, admin_token = await get_admin_user_and_token(session)
        _, eng_token = await _person(session, "ENGINEER", "EngWiz")
        sup1, _ = await _person(session, "SUPERVISOR", "SupWiz1")
        sup2, _ = await _person(session, "SUPERVISOR", "SupWiz2")
        grp = Group(code=f"W{uuid4().hex[:6]}", name=f"Wizard Group {uuid4().hex[:6]}")
        zn = Zone(code=f"W{uuid4().hex[:6]}", name=f"Wizard Zone {uuid4().hex[:6]}")
        session.add_all([grp, zn])
        await session.commit()
        body: dict[str, object] = {
            "job_number": unique_job_number("12A"),
            "job_name": "Wizard site",
            "group_id": str(grp.id),
            "zone_id": str(zn.id),
            "country": "AE",
            "start_date": str(site_today("AE") - timedelta(days=30)),
        }
        return _h(admin_token), _h(eng_token), body, [str(sup1.id), str(sup2.id)]


async def _worksite_exists(job_number: object) -> bool:
    async with async_session_factory() as session:
        found = await session.scalar(select(Worksite.id).where(Worksite.job_number == job_number))
        return found is not None


@db_required
@pytest.mark.asyncio
async def test_worksite_items_and_supervisors_in_one_create() -> None:
    admin, eng, body, sups = await _setup()
    body = {**body, "job_items": [_item("A"), _item("B"), _item("C")], "supervisor_ids": sups}
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        # Admin only (DEC-61).
        assert (await c.post("/api/v1/worksites", headers=eng, json=body)).status_code == 403
        r = await c.post("/api/v1/worksites", headers=admin, json=body)
        assert r.status_code == 201, r.text
        ws_id = r.json()["id"]
        # The row checks expect as many occurrences as the create generated.
        checks = await c.post(
            "/api/v1/job-items/validation-preview",
            headers=admin,
            json={"country": "AE", "item": _item("A")},
        )
        assert checks.status_code == 200, checks.text

    async with async_session_factory() as session:
        items = (
            (await session.execute(select(JobItem).where(JobItem.worksite_id == ws_id)))
            .scalars()
            .all()
        )
        assert sorted(i.sub_item_code for i in items) == ["A", "B", "C"]
        item_a = next(i for i in items if i.sub_item_code == "A")
        occurrences = await session.scalar(
            select(func.count(JobOccurrence.id)).where(JobOccurrence.job_item_id == item_a.id)
        )
        assert occurrences and occurrences == checks.json()["expected_occurrences_count"]
        assigned = (
            (
                await session.execute(
                    select(WorksiteSupervisor.supervisor_id).where(
                        WorksiteSupervisor.worksite_id == ws_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert sorted(map(str, assigned)) == sorted(sups)
        actions = (
            (
                await session.execute(
                    select(AuditLog.action).where(
                        AuditLog.entity_id.in_([str(ws_id), *[str(i.id) for i in items]])
                    )
                )
            )
            .scalars()
            .all()
        )
        assert actions.count("CREATE_WORKSITE") == 1
        assert actions.count("CREATE_JOB_ITEM") == 3
        assert actions.count("ASSIGN_WORKSITE_SUPERVISOR") == 2


@db_required
@pytest.mark.asyncio
async def test_a_bad_row_saves_nothing_and_names_the_row() -> None:
    admin, _, body, sups = await _setup()
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        # A grade with no line in an active revision, in row 2.
        bad = {**body, "job_items": [_item("A"), _item("B", planned_grade_code="G99Z")]}
        r = await c.post("/api/v1/worksites", headers=admin, json=bad)
        assert r.status_code == 422, r.text
        err = r.json()
        assert err["code"] == "UNKNOWN_GRADE_CODE"
        assert err["field"] == "job_items[1].planned_grade_code" and err["row"] == 1
        assert err["detail"].startswith("Job item 2 (B):")
        assert not await _worksite_exists(body["job_number"])

        # The same sub-item code twice.
        dup = {**body, "job_items": [_item("A"), _item("A")]}
        r = await c.post("/api/v1/worksites", headers=admin, json=dup)
        assert r.status_code == 409 and r.json()["field"] == "job_items[1].sub_item_code"
        assert not await _worksite_exists(body["job_number"])

        # A field the schema refuses: the location names the row.
        zero = {**body, "job_items": [_item("A"), _item("B"), _item("C", required_staff_count=0)]}
        r = await c.post("/api/v1/worksites", headers=admin, json=zero)
        assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"
        fields = [p["field"] for p in r.json()["invalid_params"]]
        assert "body.job_items.2.required_staff_count" in fields

        # Someone who is not a Supervisor.
        async with async_session_factory() as session:
            worker, _ = await _person(session, "WORKER", "WorkerWiz")
            await session.commit()
        r = await c.post(
            "/api/v1/worksites",
            headers=admin,
            json={**body, "job_items": [_item("A")], "supervisor_ids": [sups[0], str(worker.id)]},
        )
        assert r.status_code >= 400 and r.json()["field"] == "supervisor_ids"
        assert not await _worksite_exists(body["job_number"])

        # A malformed job number is a 422 naming the field, not a server error.
        r = await c.post("/api/v1/worksites", headers=admin, json={**body, "job_number": "12-A"})
        assert r.status_code == 422 and r.json()["code"] == "INVALID_JOB_NUMBER"
        assert r.json()["field"] == "job_number"

        # Zero items is fine.
        r = await c.post("/api/v1/worksites", headers=admin, json=body)
        assert r.status_code == 201, r.text


@db_required
@pytest.mark.asyncio
async def test_job_number_check() -> None:
    admin, eng, body, _ = await _setup()
    free = unique_job_number("12B")
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        url = "/api/v1/worksites/job-number-check"
        assert (await c.get(url, headers=eng, params={"job_number": free})).status_code == 403

        r = (await c.get(url, headers=admin, params={"job_number": "12X1"})).json()
        assert r["valid"] is False and r["exists"] is False and "format" in r["message"]

        r = (await c.get(url, headers=admin, params={"job_number": f" {free.lower()} "})).json()
        assert r == {
            "job_number": free,
            "valid": True,
            "exists": False,
            "message": None,
            "is_outdoor": False,
            "kind": "Indoor",
        }

        assert (await c.post("/api/v1/worksites", headers=admin, json=body)).status_code == 201
        r = (await c.get(url, headers=admin, params={"job_number": str(body["job_number"])})).json()
        assert r["exists"] is True and r["valid"] is False and r["kind"] == "Outdoor"


@db_required
@pytest.mark.asyncio
async def test_row_checks_count_eligible_employees() -> None:
    admin, eng, _, _ = await _setup()
    staff_type = f"Wizard Type {uuid4().hex[:6]}"
    payload = {"country": "AE", "item": _item("A", staff_grade_description=staff_type)}
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        r = await c.post("/api/v1/job-items/validation-preview", headers=eng, json=payload)
        assert r.status_code == 200, r.text
        assert r.json()["eligible_workers_count"] == 0
        # 6 a week x 2 staff x 8 h: hours and activities follow the item rules.
        assert float(r.json()["calculated_annual_hours"]) > 0
        assert r.json()["days_per_occurrence"] == 1

        async with async_session_factory() as session:
            session.add_all(
                [
                    Employee(
                        tally_id=f"T{uuid4().hex[:7]}",
                        name="Wizard Worker",
                        role="WORKER",
                        is_active=True,
                        country=country,
                        staff_grade_description=staff_type,
                    )
                    for country in ("AE", "SA")
                ]
            )
            await session.commit()
        r = await c.post("/api/v1/job-items/validation-preview", headers=admin, json=payload)
        assert r.json()["eligible_workers_count"] == 1  # only the AE one
