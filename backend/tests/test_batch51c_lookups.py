"""Batch 5.1 C: managed lists for staff types and grade codes (DEC-60, ADR-030).

Owner decision 23 Nov 2026: Admin alone adds staff types (Settings); grade codes exist only as
lines of an ACTIVE salary revision.
"""

import io
from datetime import date
from uuid import uuid4

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.db import async_session_factory
from fw.main import create_app
from fw.modules.audit import AuditLog
from fw.modules.imports import ImportRow, ImportService, generate_import_template_bytes
from fw.modules.jobs.models import JobItem, Worksite
from fw.modules.lookups import LookupService, LookupValue
from fw.modules.org.models import Employee, Group, Zone
from fw.modules.payroll import PayrollService, SalaryRevision
from fw.rules.grades import InvalidGradeCodeError
from fw.rules.lookups import (
    GRADE_CODE,
    SEED_STAFF_TYPES,
    STAFF_GRADE_DESCRIPTION,
    clean_value,
    find_existing,
    near_matches,
    sort_values,
    value_key,
)
from tests.test_batch6_features import db_required, get_admin_user_and_token
from tests.test_dec57_scope import _person

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _unique(prefix: str) -> str:
    """A staff type no test has used: letters only, far from every seed value."""
    letters = "".join(chr(ord("a") + int(c, 16)) for c in uuid4().hex[:8])
    return f"{prefix} {letters.title()}"


# --- Pure rules -----------------------------------------------------------------------------------


def test_value_key_ignores_case_and_spaces() -> None:
    assert value_key("Gardener  Helper") == value_key("gardenerhelper") == "gardenerhelper"
    assert find_existing(" gardener helper ", SEED_STAFF_TYPES) == "Gardener Helper"
    assert find_existing("Gardener Helpers", SEED_STAFF_TYPES) is None


def test_near_matches_alias_first_then_spelling() -> None:
    assert near_matches(STAFF_GRADE_DESCRIPTION, "Gardner Helper", SEED_STAFF_TYPES)[0] == (
        "Gardener Helper"
    )
    assert "Irrigation Technician" in near_matches(
        STAFF_GRADE_DESCRIPTION, "Irigation Technician", SEED_STAFF_TYPES
    )
    assert near_matches(STAFF_GRADE_DESCRIPTION, "Drone Pilot", SEED_STAFF_TYPES) == []
    # Close grade codes are different grades: no hints.
    assert near_matches(GRADE_CODE, "G3D", ["G3C"]) == []


def test_clean_value_and_natural_sort() -> None:
    assert clean_value(GRADE_CODE, " g3c-2026 ") == "G3C"
    assert clean_value(STAFF_GRADE_DESCRIPTION, "  Team   Leader ") == "Team Leader"
    assert clean_value(STAFF_GRADE_DESCRIPTION, "  ") is None
    with pytest.raises(InvalidGradeCodeError):
        clean_value(GRADE_CODE, "G3C26")
    assert sort_values(GRADE_CODE, ["G10A", "G2A", "G1C", "G25"]) == ["G1C", "G2A", "G10A", "G25"]


# --- API: add, duplicates, near matches, roles -------------------------------------------------


@db_required
@pytest.mark.asyncio
async def test_add_value_duplicates_near_matches_and_roles() -> None:
    async with async_session_factory() as session:
        _, admin_token = await get_admin_user_and_token(session)
        _, eng_token = await _person(session, "ENGINEER", "Eng51c")
        _, sup_token = await _person(session, "SUPERVISOR", "Sup51c")
        await session.commit()
    admin = {"Authorization": f"Bearer {admin_token}"}
    eng = {"Authorization": f"Bearer {eng_token}"}
    sup = {"Authorization": f"Bearer {sup_token}"}
    new_type = _unique("Fountain")
    url = "/api/v1/lookups/staff_grade_description"

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        # Everyone signed in can read the list.
        r = await c.get(url, headers=sup)
        assert r.status_code == 200
        assert "Gardener Helper" in [v["value"] for v in r.json()]

        # Only Admin adds staff types (Settings > Managed Lists).
        assert (await c.post(url, headers=sup, json={"value": new_type})).status_code == 403
        assert (await c.post(url, headers=eng, json={"value": new_type})).status_code == 403

        # Spaces are collapsed.
        r = await c.post(url, headers=admin, json={"value": f"  {new_type.replace(' ', '   ')} "})
        assert r.status_code == 201, r.text
        added = r.json()
        assert added["value"] == new_type and added["source"] == "SCREEN"

        # Duplicates are refused ignoring case and spaces.
        r = await c.post(url, headers=admin, json={"value": new_type.upper().replace(" ", "")})
        assert r.status_code == 409 and r.json()["code"] == "LOOKUP_DUPLICATE"
        assert r.json()["existing"] == new_type

        # A known alias or near spelling needs "Add anyway".
        r = await c.post(url, headers=admin, json={"value": "Gardner Helper"})
        assert r.status_code == 422 and r.json()["code"] == "LOOKUP_NEAR_MATCH"
        assert r.json()["suggestions"][0] == "Gardener Helper"
        near = new_type[:-1] + ("x" if new_type[-1] != "x" else "y")
        r = await c.post(url, headers=admin, json={"value": near})
        assert r.status_code == 422 and r.json()["suggestions"] == [new_type]
        r = await c.post(url, headers=admin, json={"value": near, "confirm_near_match": True})
        assert r.status_code == 201

        # Engineers cannot deactivate; Admin can, and the value leaves the default list.
        patch = {"is_active": False, "version": added["version"]}
        r = await c.patch(f"{url}/{added['id']}", headers=eng, json=patch)
        assert r.status_code == 403
        r = await c.patch(f"{url}/{added['id']}", headers=admin, json=patch)
        assert r.status_code == 200 and r.json()["is_active"] is False
        values = [v["value"] for v in (await c.get(url, headers=admin)).json()]
        assert new_type not in values
        listed = (await c.get(f"{url}?include_inactive=true", headers=admin)).json()
        assert any(v["value"] == new_type and not v["is_active"] for v in listed)

    async with async_session_factory() as session:
        actions = (
            (
                await session.execute(
                    select(AuditLog.action).where(AuditLog.entity_id == added["id"])
                )
            )
            .scalars()
            .all()
        )
        assert {"LOOKUP_VALUE_ADDED", "LOOKUP_VALUE_DEACTIVATED"} <= set(actions)


async def _unused_grade() -> str:
    async with async_session_factory() as session:
        taken = {
            v.value
            for v in await LookupService.list_values(session, GRADE_CODE, include_inactive=True)
        }
    return next(f"G{n}{b}" for n in range(30, 100) for b in "ABC" if f"G{n}{b}" not in taken)


async def _archive_revision(code: str) -> None:
    """Take a test revision out of the active ones, and its grades out of the list."""
    async with async_session_factory() as session:
        rev = (
            await session.execute(select(SalaryRevision).where(SalaryRevision.code == code))
        ).scalar_one()
        rev.status = "ARCHIVED"
        await PayrollService.refresh_grade_list(session)
        await session.commit()


@db_required
@pytest.mark.asyncio
async def test_grade_list_follows_active_revisions() -> None:
    async with async_session_factory() as session:
        _, admin_token = await get_admin_user_and_token(session)
        await session.commit()
    admin = {"Authorization": f"Bearer {admin_token}"}
    url = "/api/v1/lookups/grade_code"
    code = await _unused_grade()
    rev_code = f"T51C-{uuid4().hex[:6]}"
    emp = {
        "tally_id": f"T{uuid4().hex[:7]}",
        "name": "Grade Worker",
        "role": "WORKER",
        "grade_code": code,
        "staff_grade_description": "Gardener Helper",
        "country": "AE",
    }
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        # Grades cannot be added or deactivated as list values.
        r = await c.post(url, headers=admin, json={"value": code})
        assert r.status_code == 422 and r.json()["code"] == "GRADE_FROM_REVISION_ONLY"
        listed = (await c.get(url, headers=admin)).json()
        r = await c.patch(
            f"{url}/{listed[0]['id']}", headers=admin, json={"is_active": False, "version": 1}
        )
        assert r.status_code == 422 and r.json()["code"] == "GRADE_FROM_REVISION_ONLY"

        # Not in an active revision -> refused on screen, with the reason.
        r = await c.post("/api/v1/employees", headers=admin, json=emp)
        assert r.status_code == 422 and r.json()["code"] == "UNKNOWN_GRADE_CODE"
        assert "no line in an active salary revision" in r.json()["detail"]

        # A revision line brings the grade into the list.
        r = await c.post(
            "/api/v1/salary-revisions",
            headers=admin,
            json={
                "code": rev_code,
                "name": "Grade list test",
                "country": "ZZ",
                "effective_from": "2000-01-01",
                "lines": [{"grade_code": f"{code}-2026", "basic_salary": "1000"}],
            },
        )
        assert r.status_code == 201, r.text
        values = {v["value"]: v for v in (await c.get(url, headers=admin)).json()}
        assert values[code]["source"] == "REVISION"
        grades = (await c.get("/api/v1/grades", headers=admin)).json()
        assert code in grades and grades == sort_values(GRADE_CODE, grades)
        r = await c.post("/api/v1/employees", headers=admin, json=emp)
        assert r.status_code in (200, 201), r.text

    # The revision is no longer active -> the grade leaves the list; records keep it.
    await _archive_revision(rev_code)
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        assert code not in [v["value"] for v in (await c.get(url, headers=admin)).json()]
        r = await c.post(
            "/api/v1/employees",
            headers=admin,
            json={**emp, "tally_id": f"T{uuid4().hex[:7]}"},
        )
        assert r.status_code == 422 and r.json()["code"] == "UNKNOWN_GRADE_CODE"
    async with async_session_factory() as session:
        saved = (
            await session.execute(select(Employee).where(Employee.tally_id == emp["tally_id"]))
        ).scalar_one()
        assert saved.grade_code == code
        synced = (
            (
                await session.execute(
                    select(AuditLog.diff).where(AuditLog.action == "GRADE_LIST_SYNCED")
                )
            )
            .scalars()
            .all()
        )
        assert any(code in (d or {}).get("deactivated", []) for d in synced)


# --- Screens validate against the list -------------------------------------------------------


@db_required
@pytest.mark.asyncio
async def test_job_items_and_employees_use_the_lists() -> None:
    async with async_session_factory() as session:
        _, admin_token = await get_admin_user_and_token(session)
        grp = Group(name=f"G {uuid4().hex[:6]}", code=f"G{uuid4().hex[:6]}")
        zn = Zone(name=f"Z {uuid4().hex[:6]}", code=f"Z{uuid4().hex[:6]}")
        session.add_all([grp, zn])
        await session.flush()
        ws = Worksite(
            job_number=f"12A{uuid4().int % 100000:05d}",
            job_name="Lookup site",
            group_id=grp.id,
            zone_id=zn.id,
            country="AE",
            start_date=date(2026, 1, 1),
        )
        session.add(ws)
        await session.commit()
        ws_id = ws.id
    admin = {"Authorization": f"Bearer {admin_token}"}
    new_type = _unique("Pond")
    item = {
        "sub_item_code": "A",
        "staff_grade_description": new_type,
        "planned_grade_code": "G1A",
        "start_date": "2026-01-01",
        "frequency_unit": "WEEK",
        "occurrences_per_period": 1,
        "period_interval": 1,
        "required_staff_count": 1,
        "hours_per_occurrence_per_staff": 4,
        "deployment_type": "PERMANENT",
    }
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        r = await c.post(f"/api/v1/worksites/{ws_id}/job-items", headers=admin, json=item)
        assert r.status_code == 422 and r.json()["code"] == "INVALID_STAFF_GRADE_DESCRIPTION"
        r = await c.post(
            f"/api/v1/worksites/{ws_id}/job-items",
            headers=admin,
            json={**item, "staff_grade_description": "Gardner Helper"},
        )
        assert r.status_code == 422 and r.json()["suggestions"] == ["Gardener Helper"]
        assert "Did you mean Gardener Helper?" in r.json()["detail"]
        r = await c.post(
            f"/api/v1/worksites/{ws_id}/job-items",
            headers=admin,
            json={
                **item,
                "staff_grade_description": "Gardener Helper",
                "planned_grade_code": "G97C",
            },
        )
        assert r.status_code == 422 and r.json()["code"] == "UNKNOWN_GRADE_CODE"

        # Added on screen -> usable at once; case is taken from the list.
        added = await c.post(
            "/api/v1/lookups/staff_grade_description", headers=admin, json={"value": new_type}
        )
        assert added.status_code == 201
        r = await c.post(
            f"/api/v1/worksites/{ws_id}/job-items",
            headers=admin,
            json={**item, "staff_grade_description": new_type.lower()},
        )
        assert r.status_code == 201, r.text
        assert r.json()["staff_grade_description"] == new_type
        item_id, version = r.json()["id"], r.json()["version"]

        # Deactivated: existing record keeps it and can still be saved; new uses are refused.
        r = await c.patch(
            f"/api/v1/lookups/staff_grade_description/{added.json()['id']}",
            headers=admin,
            json={"is_active": False, "version": added.json()["version"]},
        )
        assert r.status_code == 200
        r = await c.patch(
            f"/api/v1/job-items/{item_id}",
            headers=admin,
            json={"staff_grade_description": new_type, "version": version},
        )
        assert r.status_code == 200, r.text
        r = await c.post(
            f"/api/v1/worksites/{ws_id}/job-items",
            headers=admin,
            json={**item, "sub_item_code": "B"},
        )
        assert r.status_code == 422 and r.json()["code"] == "LOOKUP_VALUE_INACTIVE"

        # Employee create validates both lists.
        emp = {
            "tally_id": f"T{uuid4().hex[:7]}",
            "name": "Lookup Worker",
            "role": "WORKER",
            "grade_code": "G1A",
            "staff_grade_description": "Not A Listed Type",
            "country": "AE",
        }
        r = await c.post("/api/v1/employees", headers=admin, json=emp)
        assert r.status_code == 422 and r.json()["code"] == "INVALID_STAFF_GRADE_DESCRIPTION"
        r = await c.post(
            "/api/v1/employees",
            headers=admin,
            json={**emp, "staff_grade_description": "gardener helper"},
        )
        assert r.status_code in (200, 201), r.text
    async with async_session_factory() as session:
        saved = (
            await session.execute(select(Employee).where(Employee.tally_id == emp["tally_id"]))
        ).scalar_one()
        assert saved.staff_grade_description == "Gardener Helper"
        assert (await session.get(JobItem, item_id)) is not None


# --- Imports ----------------------------------------------------------------------------------


def _workbook(sheets: dict[str, list[dict[str, str]]]) -> bytes:
    """The template with the example rows dropped and ``sheets`` filled in."""
    wb = openpyxl.load_workbook(io.BytesIO(generate_import_template_bytes()))
    for name, rows in sheets.items():
        ws = wb[name]
        headers = {ws.cell(4, c).value: c for c in range(2, ws.max_column + 1)}
        for r in range(5, ws.max_row + 1):
            ws.cell(r, 1, value="#")  # drop example rows
        for i, values in enumerate(rows):
            row = 5 + i
            for col in range(1, ws.max_column + 1):
                ws.cell(row, col).value = None  # cell(value=None) leaves a cell as it is
            for key, val in values.items():
                ws.cell(row, headers[key], value=val)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _employees_workbook(rows: list[dict[str, str]]) -> bytes:
    return _workbook({"Employees": rows})


@db_required
@pytest.mark.asyncio
async def test_import_reads_the_lists() -> None:
    new_type = _unique("Lake")
    async with async_session_factory() as session:
        admin_user, _ = await get_admin_user_and_token(session)
        await LookupService.add_value(
            session, STAFF_GRADE_DESCRIPTION, new_type, False, admin_user.id, "ADMIN"
        )
        await session.commit()
    new_grade = await _unused_grade()
    base = {"name": "Imp Worker", "role": "WORKER", "country": "AE", "grade_code": "G1A"}
    tallies = [f"T{uuid4().hex[:7].upper()}" for _ in range(3)]
    content = _employees_workbook(
        [
            {**base, "tally_id": tallies[0], "staff_grade_description": new_type},
            {**base, "tally_id": tallies[1], "staff_grade_description": "Gardner Helper"},
            {
                **base,
                "tally_id": tallies[2],
                "staff_grade_description": "Team Leader",
                "grade_code": f"{new_grade}-2026",
            },
        ]
    )
    async with async_session_factory() as session:
        prev = await ImportService.parse_and_preview(
            session, content, "e.xlsx", admin_user.id, selected_sheets=["Employees"]
        )
        await session.commit()
        rows = (
            (await session.execute(select(ImportRow).where(ImportRow.batch_id == prev.batch_id)))
            .scalars()
            .all()
        )
        by_tally = {r.normalized.get("tally_id"): r for r in rows}
        # A value added on screen is accepted; an alias resolves (also on Employees now).
        assert by_tally[tallies[0]].status != "ERROR", by_tally[tallies[0]].messages
        assert by_tally[tallies[0]].normalized["staff_grade_description"] == new_type
        assert "SGD_ALIAS_APPLIED" in by_tally[tallies[1]].codes
        assert by_tally[tallies[1]].normalized["staff_grade_description"] == "Gardener Helper"
        # A grade with no line in an active revision is an ERROR, never added to a list.
        assert by_tally[tallies[2]].status == "ERROR"
        assert "UNKNOWN_GRADE_CODE" in by_tally[tallies[2]].codes
        msg = next(
            m["message"] for m in by_tally[tallies[2]].messages if m["field"] == "grade_code"
        )
        assert "Salary_Revision_Lines" in msg

    # The same grade with its revision line in the same file is accepted, and joins the list
    # on commit through the revision.
    rev_code = f"T51C-{uuid4().hex[:6]}"
    line = {
        "revision_code": rev_code,
        "grade_code": new_grade,
        "grade_group_title": "Test",
        "basic_salary": "1000",
        "visa_provision": "0",
        "air_ticket_provision": "0",
        "uniform_provision": "0",
        "medical_provision": "0",
        "accommodation_provision": "0",
    }
    revision = {
        "revision_code": rev_code,
        "revision_name": "Import grade test",
        "country": "AE",
        "effective_from": "2099-01-01",
        "status": "ACTIVE",
    }
    worker = {**base, "tally_id": tallies[2], "staff_grade_description": "Team Leader"}
    content = _workbook(
        {
            "Employees": [{**worker, "grade_code": f"{new_grade}-2026"}],
            "Salary_Revisions": [revision],
            "Salary_Revision_Lines": [line],
        }
    )
    sheets = ["Employees", "Salary_Revisions", "Salary_Revision_Lines"]
    async with async_session_factory() as session:
        prev = await ImportService.parse_and_preview(
            session, content, "e.xlsx", admin_user.id, selected_sheets=sheets
        )
        await session.commit()
        rows = (
            (await session.execute(select(ImportRow).where(ImportRow.batch_id == prev.batch_id)))
            .scalars()
            .all()
        )
        assert all(r.status != "ERROR" for r in rows), [r.messages for r in rows]
        await ImportService.commit_batch(session, prev.batch_id, admin_user.id, "ADMIN")
        await session.commit()
        listed = (
            await session.execute(
                select(LookupValue).where(
                    LookupValue.list_key == GRADE_CODE, LookupValue.value == new_grade
                )
            )
        ).scalar_one()
        assert listed.source == "REVISION" and listed.is_active
    await _archive_revision(rev_code)  # leave the AE revisions as they were

    # An unknown staff type is an ERROR with a hint; values are added on screen, not by import.
    content = _employees_workbook(
        [{**base, "tally_id": f"T{uuid4().hex[:7]}", "staff_grade_description": "Gardener Helpr"}]
    )
    async with async_session_factory() as session:
        prev = await ImportService.parse_and_preview(
            session, content, "e.xlsx", admin_user.id, selected_sheets=["Employees"]
        )
        await session.commit()
        row = (
            await session.execute(select(ImportRow).where(ImportRow.batch_id == prev.batch_id))
        ).scalar_one()
        assert row.status == "ERROR" and "SGD_UNKNOWN" in row.codes
        msg = next(m["message"] for m in row.messages if m["code"] == "SGD_UNKNOWN")
        assert "Did you mean Gardener Helper?" in msg
