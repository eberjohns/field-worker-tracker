"""Batch 5.3b: base grade codes, budget warnings, future salary rows, Admin-only salary data,
/grades, profile-details validation, payroll settings without fallbacks."""

import io
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.clock import site_today
from fw.core.db import async_session_factory
from fw.core.errors import AppError
from fw.main import create_app
from fw.modules.budget import BudgetService
from fw.modules.imports import ImportRow, generate_import_template_bytes
from fw.modules.jobs.models import JobItem
from fw.modules.org.models import EmployeeAttributeHistory
from fw.modules.payroll.models import EmployeeSalary, SalaryRevision, SalaryRevisionLine
from fw.modules.payroll.service import _required_decimal_setting
from fw.rules.grades import (
    InvalidGradeCodeError,
    base_grade_code,
    display_grade_code,
    grade_sort_key,
)
from tests.test_batch6_features import db_required, get_admin_user_and_token
from tests.test_dec57_scope import _person, _site

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# --- Pure rules -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "base"),
    [
        ("G3C", "G3C"),
        ("g3c", "G3C"),
        ("G3C-2026", "G3C"),
        ("G3C-R2", "G3C"),
        ("G5-C", "G5C"),
        ("G5-C-2027", "G5C"),
        ("G16A", "G16A"),
        ("G25", "G25"),
        (" G25-R12 ", "G25"),
    ],
)
def test_base_grade_code_strips_only_known_suffixes(raw: str, base: str) -> None:
    assert base_grade_code(raw) == base


@pytest.mark.parametrize("raw", ["G3C26", "G3CR2", "3C", "GE", "", "G3C-26", "G3C-2026-X", "S1"])
def test_base_grade_code_rejects_unparseable(raw: str) -> None:
    with pytest.raises(InvalidGradeCodeError) as exc:
        base_grade_code(raw)
    assert exc.value.code == "INVALID_GRADE_CODE"


def test_display_and_sort() -> None:
    assert display_grade_code("G3C", "2026") == "G3C-2026"
    assert display_grade_code("G3C", None) == "G3C"
    assert sorted(["G10A", "G2A", "G1C", "G25", "G1A"], key=grade_sort_key) == [
        "G1A",
        "G1C",
        "G2A",
        "G10A",
        "G25",
    ]


async def _admin_headers() -> dict[str, str]:
    async with async_session_factory() as session:
        _, token = await get_admin_user_and_token(session)
    return {"Authorization": f"Bearer {token}"}


# --- Revisions: base codes stored, display suffix ---------------------------------------------


@db_required
@pytest.mark.asyncio
async def test_revision_stores_base_codes_and_shows_year_suffix() -> None:
    headers = await _admin_headers()
    code = f"RB{uuid4().hex[:6].upper()}"
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        resp = await c.post(
            "/api/v1/salary-revisions",
            headers=headers,
            json={
                "code": code,
                "name": "Base code test",
                "effective_from": "2026-01-01",
                "lines": [
                    {"grade_code": "G3C-2026", "basic_salary": "1500.00"},
                    {"grade_code": "g16a", "basic_salary": "9000.00"},
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["suffix_label"] == "2026"
        lines = {ln["grade_code"]: ln for ln in body["lines"]}
        assert set(lines) == {"G3C", "G16A"}
        assert lines["G3C"]["display_grade_code"] == "G3C-2026"

        bad = await c.post(
            "/api/v1/salary-revisions",
            headers=headers,
            json={
                "code": f"{code}X",
                "name": "Bad",
                "effective_from": "2026-01-01",
                "lines": [{"grade_code": "G3C26", "basic_salary": "1.00"}],
            },
        )
        assert bad.status_code == 422
        assert bad.json()["code"] == "INVALID_GRADE_CODE"

        dup = await c.post(
            "/api/v1/salary-revisions",
            headers=headers,
            json={
                "code": f"{code}D",
                "name": "Dup",
                "effective_from": "2026-01-01",
                "lines": [{"grade_code": "G3C"}, {"grade_code": "G3C-R2"}],
            },
        )
        assert dup.status_code == 422
        assert dup.json()["code"] == "DUPLICATE_GRADE_LINE"

        grades = await c.get("/api/v1/grades", headers=headers)
        assert grades.status_code == 200
        assert "G3C" in grades.json() and "G16A" in grades.json()
        assert all("-" not in g for g in grades.json())


# --- Budget: no 10.00 fallback ----------------------------------------------------------------


@db_required
@pytest.mark.asyncio
async def test_budget_reports_missing_grade_and_leaves_it_out() -> None:
    async with async_session_factory() as session:
        rev = SalaryRevision(
            code=f"BW{uuid4().hex[:6].upper()}",
            name="Budget warn",
            country="AE",
            effective_from=site_today("AE") - timedelta(days=400),
            status="ACTIVE",
            suffix_label="2025",
        )
        rev.lines.append(SalaryRevisionLine(grade_code="G1A", basic_salary=Decimal("1200.00")))
        session.add(rev)
        ws, item_a = await _site(session, "Budget warn site")
        ws.salary_revision_code = rev.code
        ws.budget_amount = None
        item_b = JobItem(
            worksite_id=ws.id,
            sub_item_code="B",
            staff_grade_description="Helper",
            planned_grade_code="G9C",
            frequency_unit="WEEK",
            occurrences_per_period=Decimal("1.0"),
            period_interval=1,
            required_staff_count=1,
            hours_per_occurrence_per_staff=Decimal("8.0"),
            start_date=item_a.start_date,
            deployment_type="PERMANENT",
            is_active=True,
        )
        session.add(item_b)
        await session.commit()

        rows = await BudgetService.planned_vs_actual(session, is_admin=True, worksite_ids=[ws.id])
    row = next(r for r in rows if r.worksite_id == ws.id)
    missing = [w for w in row.warnings if w.code == "MISSING_GRADE_RATE"]
    assert len(missing) == 1 and missing[0].grade_code == "G9C"
    # Item B (1 x 52 x 8 h a year) is left out; item A (6 x 52 x 8) counts. Both run over the
    # same days of the contract year (DEC-59 pro-rates by day), so B's hours are 1/6 of A's.
    assert row.missing_rate_hours > 0
    assert abs(row.missing_rate_hours * 6 - row.annual_planned_man_hours) < Decimal("0.01")
    assert row.annual_labor_budget is not None and row.annual_labor_budget > Decimal("0.00")


# --- Future salary rows and CREW_BREAK rows ---------------------------------------------------


def _salary(emp_id, eff, basic: str, source: str = "MANUAL", brk: int | None = 60):
    return EmployeeSalary(
        employee_id=emp_id,
        effective_from=eff,
        standard_hours=Decimal("8.00"),
        basic_salary=Decimal(basic),
        special_allowance=Decimal("100.00"),
        fixed_ot_amount=Decimal("0.00"),
        bonus=Decimal("0.00"),
        telephone_allowance=Decimal("0.00"),
        housing_transport_allowance=Decimal("0.00"),
        break_minutes=brk,
        change_source=source,
    )


@db_required
@pytest.mark.asyncio
async def test_future_salary_edit_and_delete_resync_crew_break_rows() -> None:
    headers = await _admin_headers()
    today = site_today("AE")
    async with async_session_factory() as session:
        worker, _ = await _person(session, "WORKER", "Sal")
        current = _salary(worker.id, today - timedelta(days=30), "1000.00")
        raise_row = _salary(worker.id, today + timedelta(days=10), "1200.00")
        crew = _salary(worker.id, today + timedelta(days=20), "1200.00", "CREW_BREAK", 45)
        session.add_all([current, raise_row, crew])
        await session.commit()
        ids = (worker.id, current.id, raise_row.id, crew.id)
    emp_id, current_id, raise_id, crew_id = ids
    base = f"/api/v1/employees/{emp_id}/salary"

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        # CREW_BREAK rows cannot be edited or deleted directly.
        r = await c.delete(f"{base}/{crew_id}", headers=headers)
        assert r.status_code == 422 and r.json()["code"] == "CREW_BREAK_ROW_LOCKED"
        r = await c.patch(f"{base}/{crew_id}", headers=headers, json={"basic_salary": "1.00"})
        assert r.status_code == 422 and r.json()["code"] == "CREW_BREAK_ROW_LOCKED"
        # Current/past rows cannot be deleted.
        r = await c.delete(f"{base}/{current_id}", headers=headers)
        assert r.status_code == 422

        # Edit the future raise: the later crew-break row follows the new amount.
        r = await c.patch(f"{base}/{raise_id}", headers=headers, json={"basic_salary": "1300.00"})
        assert r.status_code == 200, r.text
        async with async_session_factory() as session:
            crew_row = await session.get(EmployeeSalary, crew_id)
            assert crew_row is not None
            assert crew_row.basic_salary == Decimal("1300.00")
            assert crew_row.break_minutes == 45

        # Delete the future raise: the crew-break row falls back to the current row's amount.
        r = await c.delete(f"{base}/{raise_id}", headers=headers)
        assert r.status_code in (200, 204), r.text
        async with async_session_factory() as session:
            crew_row = await session.get(EmployeeSalary, crew_id)
            assert crew_row is not None
            assert crew_row.basic_salary == Decimal("1000.00")
            assert crew_row.break_minutes == 45


# --- Admin-only salary data -------------------------------------------------------------------


def _fill(wb: openpyxl.Workbook, sheet: str, values: dict[str, str], row: int = 5) -> None:
    ws = wb[sheet]
    headers = {ws.cell(4, c).value: c for c in range(2, ws.max_column + 1)}
    if row == 5:
        for r in range(5, ws.max_row + 1):  # drop example rows
            ws.cell(r, 1, value="#")
    ws.cell(row, 1, value="")  # blank column A = data row
    for key, val in values.items():
        ws.cell(row, headers[key], value=val)


def _workbook_with_salary_and_settings() -> bytes:
    wb = openpyxl.load_workbook(io.BytesIO(generate_import_template_bytes()))
    _fill(
        wb,
        "Salary_Revisions",
        {
            "revision_code": f"EX{uuid4().hex[:5].upper()}",
            "revision_name": "X",
            "effective_from": "2026-01-01",
        },
    )
    _fill(
        wb,
        "Company_Settings",
        {"setting_key": "provision_visa", "value": "999", "effective_from": "2026-01-01"},
    )
    _fill(
        wb,
        "Company_Settings",
        {"setting_key": "ot1_multiplier", "value": "9", "effective_from": "2026-01-01"},
        row=6,
    )
    for name in wb.sheetnames:
        if name not in ("README", "Salary_Revisions", "Company_Settings") and name in wb.sheetnames:
            ws = wb[name]
            for r in range(5, ws.max_row + 1):
                ws.cell(r, 1, value="#")
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


@db_required
@pytest.mark.asyncio
async def test_engineer_cannot_see_or_write_salary_and_money_settings() -> None:
    admin_headers = await _admin_headers()
    async with async_session_factory() as session:
        _, eng_token = await _person(session, "ENGINEER", "Eng53b")
        await session.commit()
    eng = {"Authorization": f"Bearer {eng_token}"}
    content = _workbook_with_salary_and_settings()

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        # Revision lines (salary amounts) are Admin only; the code list is not.
        rev = (await c.get("/api/v1/salary-revisions", headers=eng)).json()
        assert (await c.get("/api/v1/salary-revisions", headers=eng)).status_code == 200
        if rev:
            code = rev[0]["code"]
            assert (await c.get(f"/api/v1/salary-revisions/{code}", headers=eng)).status_code == 403
            r = await c.get(f"/api/v1/salary-revisions/{code}/export-template", headers=eng)
            assert r.status_code == 403

        # Engineer template has no salary sheets.
        t = await c.get("/api/v1/imports/template", headers=eng)
        names = openpyxl.load_workbook(io.BytesIO(t.content)).sheetnames
        assert not {"Employee_Salary", "Salary_Revisions", "Salary_Revision_Lines"} & set(names)
        t = await c.get("/api/v1/imports/template", headers=admin_headers)
        assert "Salary_Revision_Lines" in openpyxl.load_workbook(io.BytesIO(t.content)).sheetnames

        # Engineer upload: salary sheet rows and money settings are skipped, values not stored.
        up = await c.post("/api/v1/imports", headers=eng, files={"file": ("e.xlsx", content, XLSX)})
        assert up.status_code == 201, up.text
        batch = up.json()["batch_id"]
        rows = (await c.get(f"/api/v1/imports/{batch}/preview?limit=500", headers=eng)).json()[
            "rows"
        ]
        sal = [r for r in rows if r["sheet"] == "Salary_Revisions"]
        assert sal and all(r["action"] == "SKIPPED" for r in sal)
        assert all(r["codes"] == ["SHEET_ADMIN_ONLY"] and r["normalized"] == {} for r in sal)
        cs = {r["natural_key"]: r for r in rows if r["sheet"] == "Company_Settings"}
        for key in ("provision_visa", "ot1_multiplier"):
            assert cs[key]["codes"] == ["SETTING_ADMIN_ONLY"]
            assert cs[key]["normalized"] == {}
        # Nothing of the values is stored for the Engineer's batch.
        async with async_session_factory() as session:
            stored = (
                (
                    await session.execute(
                        select(ImportRow).where(
                            ImportRow.batch_id == batch,
                            ImportRow.sheet.in_(["Salary_Revisions", "Company_Settings"]),
                            ImportRow.action == "SKIPPED",
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert stored
        for row in stored:
            assert set(row.raw_row) <= {"setting_key"}
            assert "999" not in str(row.raw_row) and "9" != row.raw_row.get("value")

        # Admin uploads the same file: the engineer sees none of its salary rows and cannot commit.
        up = await c.post(
            "/api/v1/imports", headers=admin_headers, files={"file": ("a.xlsx", content, XLSX)}
        )
        batch = up.json()["batch_id"]
        rows = (await c.get(f"/api/v1/imports/{batch}/preview?limit=500", headers=eng)).json()[
            "rows"
        ]
        assert not [r for r in rows if r["sheet"] == "Salary_Revisions"]
        assert not [
            r for r in rows if r["sheet"] == "Company_Settings" and "provision" in r["natural_key"]
        ]
        commit = await c.post(f"/api/v1/imports/{batch}/commit", headers=eng)
        assert commit.status_code == 422


# --- profile-details --------------------------------------------------------------------------


@db_required
@pytest.mark.asyncio
async def test_profile_details_validation_and_actor_role() -> None:
    headers = await _admin_headers()
    today = site_today("AE")
    async with async_session_factory() as session:
        worker, _ = await _person(session, "WORKER", "Prof")
        sup, _ = await _person(session, "SUPERVISOR", "ProfSup")
        await session.commit()
        worker_id, sup_id = worker.id, sup.id

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:

        async def patch(emp_id, body):
            return await c.patch(
                f"/api/v1/employees/{emp_id}/profile-details",
                headers=headers,
                json={"reason": "test", **body},
            )

        r = await patch(
            worker_id, {"grade_code": "G2B", "effective_from": str(today + timedelta(days=1))}
        )
        assert r.status_code == 422 and r.json()["code"] == "FUTURE_PROFILE_CHANGE_NOT_SUPPORTED"
        r = await patch(worker_id, {"grade_code": "G2B26"})
        assert r.status_code == 422 and r.json()["code"] == "INVALID_GRADE_CODE"
        r = await patch(worker_id, {"staff_grade_description": "Mason"})
        assert r.status_code == 422 and r.json()["code"] == "INVALID_STAFF_GRADE_DESCRIPTION"
        # The meeting-locked field is staff_grade_description, for Supervisor/Superintendent/Engineer.
        r = await patch(sup_id, {"staff_grade_description": "Gardener Expert"})
        assert r.status_code == 422 and r.json()["code"] == "STAFF_GRADE_DESCRIPTION_LOCKED"
        # Grade changes on staff roles are still allowed.
        r = await patch(sup_id, {"grade_code": "G4A-2026"})
        assert r.status_code == 200, r.text
        assert r.json()["grade_code"] == "G4A"

        r = await patch(
            worker_id, {"grade_code": "g2b", "effective_from": str(today - timedelta(days=3))}
        )
        assert r.status_code == 200, r.text

    async with async_session_factory() as session:
        hist = (
            (
                await session.execute(
                    select(EmployeeAttributeHistory).where(
                        EmployeeAttributeHistory.employee_id == worker_id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(hist) == 1
    assert hist[0].new_value == "G2B"
    assert hist[0].actor_role == "ADMIN"
    assert hist[0].effective_from == today - timedelta(days=3)


# --- Settings without fallbacks ---------------------------------------------------------------


@db_required
@pytest.mark.asyncio
async def test_missing_money_setting_stops_with_setting_missing() -> None:
    async with async_session_factory() as session:
        assert await _required_decimal_setting(
            session, "provision_visa", "AE", site_today("AE")
        ) == Decimal("132")
        with pytest.raises(AppError) as exc:
            await _required_decimal_setting(
                session, "provision_does_not_exist", "AE", site_today("AE")
            )
    assert exc.value.code == "SETTING_MISSING"


# --- default_password is Admin only in Company_Settings (owner, 23 Nov) ------------------------


def test_default_password_is_admin_only_setting() -> None:
    from fw.rules.imports import is_admin_only_row, is_admin_only_setting

    assert is_admin_only_setting("default_password")
    assert is_admin_only_row("Company_Settings", "default_password")
    assert not is_admin_only_setting("grace_period_minutes")


@db_required
@pytest.mark.asyncio
async def test_engineer_import_skips_default_password() -> None:
    async with async_session_factory() as session:
        _, eng_token = await _person(session, "ENGINEER", "EngPwd53b")
        await session.commit()
    eng = {"Authorization": f"Bearer {eng_token}"}

    wb = openpyxl.load_workbook(io.BytesIO(generate_import_template_bytes()))
    _fill(
        wb,
        "Company_Settings",
        {"setting_key": "default_password", "value": "Leak@12345", "effective_from": "2026-01-01"},
    )
    _fill(
        wb,
        "Company_Settings",
        {"setting_key": "grace_period_minutes", "value": "12", "effective_from": "2026-01-01"},
        row=6,
    )
    for name in wb.sheetnames:
        if name not in ("README", "Company_Settings"):
            ws = wb[name]
            for r in range(5, ws.max_row + 1):
                ws.cell(r, 1, value="#")
    out = io.BytesIO()
    wb.save(out)

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        t = await c.get("/api/v1/imports/template", headers=eng)
        # Exact key only: default_password_max_days is not a credential and stays.
        assert b"'default_password'" not in _sheet_text(t.content, "Company_Settings")
        assert b"'default_password_max_days'" in _sheet_text(t.content, "Company_Settings")

        up = await c.post(
            "/api/v1/imports", headers=eng, files={"file": ("p.xlsx", out.getvalue(), XLSX)}
        )
        assert up.status_code == 201, up.text
        batch = up.json()["batch_id"]
        rows = (await c.get(f"/api/v1/imports/{batch}/preview?limit=500", headers=eng)).json()[
            "rows"
        ]
    cs = {r["natural_key"].split(":")[0]: r for r in rows if r["sheet"] == "Company_Settings"}
    # Same as the money settings: shown as skipped, with no value.
    assert cs["default_password"]["action"] == "SKIPPED"
    assert cs["default_password"]["codes"] == ["SETTING_ADMIN_ONLY"]
    assert cs["default_password"]["normalized"] == {}
    assert cs["grace_period_minutes"]["action"] != "SKIPPED"

    async with async_session_factory() as session:
        stored = (
            (
                await session.execute(
                    select(ImportRow).where(
                        ImportRow.batch_id == batch, ImportRow.sheet == "Company_Settings"
                    )
                )
            )
            .scalars()
            .all()
        )
    pwd = [r for r in stored if str(r.natural_key).startswith("default_password")]
    assert pwd and all(r.action == "SKIPPED" for r in pwd)
    assert all(r.raw_row == {"setting_key": "default_password"} for r in pwd)
    assert "Leak@12345" not in str([r.raw_row for r in stored])


def _sheet_text(xlsx: bytes, sheet: str) -> bytes:
    wb = openpyxl.load_workbook(io.BytesIO(xlsx))
    if sheet not in wb.sheetnames:
        return b""
    return str([[c.value for c in row] for row in wb[sheet].iter_rows()]).encode()


# --- Reset database re-seeds default settings (owner, 23 Nov) ----------------------------------


@db_required
@pytest.mark.asyncio
async def test_reset_database_reseeds_default_settings() -> None:
    from fw.modules.identity import User, hash_password
    from fw.modules.settings import CompanySettingValue
    from fw.modules.settings.defaults import DEFAULT_COMPANY_SETTINGS

    async with async_session_factory() as session:
        _, token = await get_admin_user_and_token(session)
        admin = (await session.execute(select(User).where(User.role == "ADMIN"))).scalars().first()
        assert admin is not None
        admin.credential_hash = hash_password("Admin@1234")
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        res = await c.post(
            "/api/v1/settings/reset-database",
            headers={"Authorization": f"Bearer {token}"},
            json={"confirmation_text": "RESET", "admin_password": "Admin@1234"},
        )
    assert res.status_code == 200, res.text

    async with async_session_factory() as session:
        rows = (await session.execute(select(CompanySettingValue))).scalars().all()
        keys = {(r.setting_key, r.country) for r in rows}
        assert {(k, c) for k, c, _, _ in DEFAULT_COMPANY_SETTINGS} <= keys
        assert ("default_password", None) in keys
        # Every payroll money setting resolves again, without reimporting Company_Settings.
        today = site_today("AE")
        provisions = Decimal("0")
        for key in (
            "provision_visa",
            "provision_air_ticket",
            "provision_uniform",
            "provision_accommodation",
            "provision_medical",
        ):
            provisions += await _required_decimal_setting(session, key, "AE", today)
        assert provisions == Decimal("842")
        for key in (
            "standard_ot_divisor_hours",
            "ot1_multiplier",
            "ot2_multiplier",
            "hr_overhead_rate",
        ):
            assert await _required_decimal_setting(session, key, "AE", today) > 0
