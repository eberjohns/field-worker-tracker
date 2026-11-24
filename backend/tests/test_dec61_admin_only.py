"""DEC-61 (owner decision, 23 Nov 2026): Admin-only actions.

Admin only: creating a worksite, the whole Master Data Import and the boundary file import,
creating an employee, adding a group or zone, and every deactivation or reactivation. Engineers
keep job item edits and supervisor assignments on worksites in their scope (DEC-57), exports,
and accommodation create and edit.
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.db import async_session_factory
from fw.main import create_app
from fw.modules.jobs.models import JobItem
from fw.modules.org.models import Accommodation
from tests.test_batch6_features import db_required
from tests.test_dec57_scope import _build, _h

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _item_of(worksite_id) -> JobItem:
    async with async_session_factory() as session:
        item = (
            await session.execute(select(JobItem).where(JobItem.worksite_id == worksite_id))
        ).scalar_one()
        return item


@db_required
@pytest.mark.asyncio
async def test_engineer_loses_admin_only_actions() -> None:
    s = await _build()
    eng, admin = _h(s.eng_token), _h(s.admin_token)
    item_a = await _item_of(s.site_a.id)
    async with async_session_factory() as session:
        acc = Accommodation(accommodation_code=f"ACC{uuid4().hex[:6]}", name="Camp 61")
        session.add(acc)
        await session.commit()
        acc_id = acc.id

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        # Master Data Import and the boundary file import: Admin only.
        assert (await c.get("/api/v1/imports/template", headers=eng)).status_code == 403
        assert (await c.get("/api/v1/imports", headers=eng)).status_code == 403
        up = await c.post(
            "/api/v1/imports", headers=eng, files={"file": ("x.xlsx", b"not a workbook", XLSX)}
        )
        assert up.status_code == 403
        r = await c.post("/api/v1/boundaries/import", headers=eng, json={"items": []})
        assert r.status_code == 403
        r = await c.post("/api/v1/boundaries/import", headers=admin, json={"items": []})
        assert r.status_code == 200, r.text

        # Creating a worksite or an employee, adding a group or zone: Admin only.
        assert (await c.post("/api/v1/worksites", headers=eng, json={})).status_code == 403
        assert (await c.post("/api/v1/employees", headers=eng, json={})).status_code == 403
        assert (await c.post("/api/v1/groups", headers=eng, json={"name": "X"})).status_code == 403
        r = await c.post("/api/v1/zones", headers=eng, json={"code": "Z61", "name": "Z"})
        assert r.status_code == 403

        # Deactivating through PATCH is closed too.
        r = await c.patch(
            f"/api/v1/job-items/{item_a.id}",
            headers=eng,
            json={"is_active": False, "version": item_a.version},
        )
        assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"
        r = await c.patch(
            f"/api/v1/accommodations/{acc_id}", headers=eng, json={"is_active": False, "version": 1}
        )
        assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"

        # Engineers keep accommodation create and edit, and exports.
        r = await c.patch(
            f"/api/v1/accommodations/{acc_id}", headers=eng, json={"name": "Camp 61B", "version": 1}
        )
        assert r.status_code == 200, r.text
        r = await c.post(
            "/api/v1/accommodations",
            headers=eng,
            json={"accommodation_code": f"ACC{uuid4().hex[:6]}", "name": "Camp E"},
        )
        assert r.status_code == 201, r.text
        assert (await c.get("/api/v1/worksites/export", headers=eng)).status_code == 200

        # Admin can still deactivate both.
        r = await c.patch(
            f"/api/v1/accommodations/{acc_id}",
            headers=admin,
            json={"is_active": False, "version": 2},
        )
        assert r.status_code == 200, r.text


@db_required
@pytest.mark.asyncio
async def test_engineer_edits_job_items_and_supervisors_in_scope_only() -> None:
    s = await _build()
    eng = _h(s.eng_token)
    item_a = await _item_of(s.site_a.id)  # site A: its supervisor reports to the Engineer
    item_b = await _item_of(s.site_b.id)  # site B: another crew, out of scope

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        r = await c.patch(
            f"/api/v1/job-items/{item_a.id}",
            headers=eng,
            json={"required_staff_count": 2, "version": item_a.version},
        )
        assert r.status_code == 200, r.text
        r = await c.patch(
            f"/api/v1/job-items/{item_b.id}",
            headers=eng,
            json={"required_staff_count": 2, "version": item_b.version},
        )
        assert r.status_code == 404

        new_item = {
            "sub_item_code": "B",
            "staff_grade_description": "Gardener Helper",
            "planned_grade_code": "G1A",
            "frequency_unit": "WEEK",
            "occurrences_per_period": 6,
            "required_staff_count": 1,
            "hours_per_occurrence_per_staff": 8,
            "start_date": "2026-01-01",
            "deployment_type": "PERMANENT",
        }
        r = await c.post(f"/api/v1/worksites/{s.site_a.id}/job-items", headers=eng, json=new_item)
        assert r.status_code == 201, r.text
        r = await c.post(f"/api/v1/worksites/{s.site_b.id}/job-items", headers=eng, json=new_item)
        assert r.status_code == 404

        # Supervisor assignments: on worksites in scope only.
        body = {"supervisor_id": str(s.sup_b.id)}
        r = await c.post(f"/api/v1/worksites/{s.site_a.id}/supervisors", headers=eng, json=body)
        assert r.status_code == 201, r.text
        r = await c.post(f"/api/v1/worksites/{s.site_u.id}/supervisors", headers=eng, json=body)
        assert r.status_code == 404
        r = await c.delete(f"/api/v1/worksites/{s.site_a.id}/supervisors/{s.sup_b.id}", headers=eng)
        assert r.status_code == 204
