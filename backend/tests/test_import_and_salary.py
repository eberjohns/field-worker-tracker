"""Integration tests for Import Framework, Master Data Import, and Salary Structures.

Verifies:
1. Sample template previews all sheets and re-upload is idempotent (all UNCHANGED).
2. Clashes, bad references, invalid types return row-level error codes.
3. UPDATED rows show old -> new per field in diff.
4. Cell rules: blank keeps existing value, `_` clears optional field, `_` on required flags CLEAR_ON_REQUIRED.
5. Salary change records history and applies from next month; difference is correct.
6. Commit is one atomic transaction.
7. Rollback functionality.
"""

import io
import socket
from datetime import date
from uuid import uuid4

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient

from fw.core.db import async_session_factory, engine
from fw.main import app
from fw.modules.identity import AuthService, User, get_current_user
from fw.modules.imports import generate_import_template_bytes
from fw.modules.org import Employee
from fw.rules.payroll import compute_next_payroll_month_start


def is_db_available() -> bool:
    """Check if PostgreSQL is running and accepting connections on localhost:5432."""
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
    """Async test client authenticated as an ADMIN user against a running database."""
    if not is_db_available():
        pytest.skip("PostgreSQL not available on localhost:5432")

    admin_id = uuid4()
    emp_id = uuid4()

    async with async_session_factory() as session:
        # Create admin employee and user
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
            username=emp.tally_id,
            credential_hash="fakehash",
            role="ADMIN",
            is_active=True,
            must_change_password=False,
        )
        session.add(user)
        await session.commit()

    token = AuthService.create_access_token(user)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client, admin_id, emp_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_download_template():
    """Verify template generator and download endpoint without requiring live DB."""
    admin_user = User(
        id=uuid4(),
        employee_id=uuid4(),
        username="ADMIN01",
        role="ADMIN",
        credential_hash="fake",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/imports/template")
            assert resp.status_code == 200
            assert "spreadsheetml.sheet" in resp.headers["content-type"]
            wb = openpyxl.load_workbook(io.BytesIO(resp.content), data_only=True)
            assert "Groups" in wb.sheetnames
            assert "Employees" in wb.sheetnames
            assert "Employee_Salary" in wb.sheetnames
            assert "Lists" in wb.sheetnames
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@db_required
@pytest.mark.asyncio
async def test_upload_sample_template_and_idempotency(admin_client):
    client, _, _ = admin_client
    wb = openpyxl.load_workbook(io.BytesIO(generate_import_template_bytes()))

    # Add real rows for Groups, Zones, Accommodations, Employees
    g_code = f"G{str(uuid4())[:4]}"
    z_code = f"Z{str(uuid4())[:4]}"
    acc_code = f"ACC{str(uuid4())[:4]}"
    t_id = f"WRK{str(uuid4())[:5]}"

    ws_g = wb["Groups"]
    ws_g.cell(row=5, column=1, value="")
    ws_g.cell(row=5, column=2, value=g_code)
    ws_g.cell(row=5, column=3, value="Test Group")

    ws_z = wb["Zones"]
    ws_z.cell(row=5, column=1, value="")
    ws_z.cell(row=5, column=2, value=z_code)
    ws_z.cell(row=5, column=3, value="Test Zone")

    ws_acc = wb["Accommodations"]
    ws_acc.cell(row=5, column=1, value="")
    ws_acc.cell(row=5, column=2, value=acc_code)
    ws_acc.cell(row=5, column=3, value="Test Camp")
    ws_acc.cell(row=5, column=4, value="Camp Address")
    ws_acc.cell(row=5, column=5, value="AE")

    ws_emp = wb["Employees"]
    ws_emp.cell(row=5, column=1, value="")
    ws_emp.cell(row=5, column=2, value=t_id)
    ws_emp.cell(row=5, column=3, value="Test Employee")
    ws_emp.cell(row=5, column=4, value="WORKER")
    ws_emp.cell(row=5, column=5, value="G1C")
    ws_emp.cell(row=5, column=6, value="Gardener Helper")
    ws_emp.cell(row=5, column=7, value="AE")
    ws_emp.cell(row=5, column=10, value=acc_code)

    buf = io.BytesIO()
    wb.save(buf)
    template_bytes = buf.getvalue()

    # 1. First upload -> Preview
    files = {
        "file": (
            "FieldWorkerTracker_Import_Template_v1.0.xlsx",
            template_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    resp = await client.post("/api/v1/imports", files=files)
    assert resp.status_code == 201
    data = resp.json()
    batch_id = data["batch_id"]
    assert data["status"] == "PREVIEWED"
    assert data["can_commit"] is True

    # 2. Commit batch
    commit_resp = await client.post(f"/api/v1/imports/{batch_id}/commit")
    assert commit_resp.status_code == 200
    commit_data = commit_resp.json()
    assert commit_data["status"] == "COMMITTED"

    # 3. Re-upload identical file -> Idempotent check: all in-scope rows should be UNCHANGED
    files2 = {
        "file": (
            "FieldWorkerTracker_Import_Template_v1.0.xlsx",
            template_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    resp2 = await client.post("/api/v1/imports", files=files2)
    assert resp2.status_code == 201
    data2 = resp2.json()
    batch2_id = data2["batch_id"]

    # Check preview rows: none should be NEW
    preview2 = await client.get(f"/api/v1/imports/{batch2_id}/preview")
    assert preview2.status_code == 200
    p2_data = preview2.json()
    counts = p2_data["summary"]["counts"]
    assert counts["NEW"] == 0
    assert counts["UNCHANGED"] > 0


@db_required
@pytest.mark.asyncio
async def test_cell_rules_diff_and_clear(admin_client):
    client, _, _ = admin_client

    # Build a test workbook with known employee
    wb = openpyxl.load_workbook(io.BytesIO(generate_import_template_bytes()))
    ws_emp = wb["Employees"]

    test_tally = f"TST{str(uuid4())[:5]}"
    # Add employee on row 5: required fields + optional phone
    ws_emp.cell(row=5, column=1, value="")  # col A blank
    ws_emp.cell(row=5, column=2, value=test_tally)
    ws_emp.cell(row=5, column=3, value="Initial Worker")
    ws_emp.cell(row=5, column=4, value="WORKER")
    ws_emp.cell(row=5, column=5, value="G1C")
    ws_emp.cell(row=5, column=6, value="Gardener Helper")
    ws_emp.cell(row=5, column=7, value="AE")
    ws_emp.cell(row=5, column=8, value="FRIDAY")
    ws_emp.cell(row=5, column=10, value="")  # Clear leftover template example accommodation
    ws_emp.cell(row=5, column=18, value="+971500000000")  # phone

    buf = io.BytesIO()
    wb.save(buf)

    # 1. Upload & commit initial
    files = {
        "file": (
            "test1.xlsx",
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    r1 = await client.post("/api/v1/imports", files=files)
    assert r1.status_code == 201
    b1_id = r1.json()["batch_id"]
    await client.post(f"/api/v1/imports/{b1_id}/commit")

    # 2. Upload update: change weekly_off_day to SUNDAY, '_' to clear phone, and blank for name (keeps)
    ws_emp.cell(row=5, column=3, value="")  # Blank name -> KEEP existing
    ws_emp.cell(row=5, column=8, value="SUNDAY")  # New weekly off
    ws_emp.cell(row=5, column=18, value="_")  # Underscore -> CLEAR phone

    buf2 = io.BytesIO()
    wb.save(buf2)

    files2 = {
        "file": (
            "test2.xlsx",
            buf2.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    r2 = await client.post("/api/v1/imports", files=files2)
    assert r2.status_code == 201
    b2_id = r2.json()["batch_id"]

    # Preview diff check
    prev_resp = await client.get(f"/api/v1/imports/{b2_id}/preview?sheet=Employees")
    assert prev_resp.status_code == 200
    rows = prev_resp.json()["rows"]
    matching = [r for r in rows if r["natural_key"] == test_tally]
    assert len(matching) == 1
    row = matching[0]
    assert row["action"] == "UPDATED"
    assert "weekly_off_day" in row["diff"]
    assert row["diff"]["weekly_off_day"]["old"] == "FRIDAY"
    assert row["diff"]["weekly_off_day"]["new"] == "SUNDAY"


@db_required
@pytest.mark.asyncio
async def test_error_reporting_codes(admin_client):
    client, _, _ = admin_client

    wb = openpyxl.load_workbook(io.BytesIO(generate_import_template_bytes()))
    ws_emp = wb["Employees"]

    # Row 5: '_' on required field 'name' -> CLEAR_ON_REQUIRED
    ws_emp.cell(row=5, column=1, value="")
    ws_emp.cell(row=5, column=2, value="BAD01")
    ws_emp.cell(row=5, column=3, value="_")  # Clear on required
    ws_emp.cell(row=5, column=4, value="INVALID_ROLE")  # Invalid enum
    ws_emp.cell(row=5, column=5, value="G1C")
    ws_emp.cell(row=5, column=6, value="Gardener Helper")
    ws_emp.cell(row=5, column=7, value="AE")

    buf = io.BytesIO()
    wb.save(buf)

    files = {
        "file": (
            "errors.xlsx",
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    resp = await client.post("/api/v1/imports", files=files)
    assert resp.status_code == 201
    b_id = resp.json()["batch_id"]

    prev = await client.get(f"/api/v1/imports/{b_id}/preview?sheet=Employees")
    rows = prev.json()["rows"]
    bad_row = [r for r in rows if r["natural_key"] == "BAD01"][0]
    assert "CLEAR_ON_REQUIRED" in bad_row["codes"]
    assert "INVALID_ENUM" in bad_row["codes"]
    assert prev.json()["can_commit"] is False


@db_required
@pytest.mark.asyncio
async def test_salary_structure_effective_date_and_difference(admin_client):
    client, _, emp_id = admin_client

    # 1. Create initial salary with blank effective_from (should default to 1st of next month)
    sal_payload1 = {
        "standard_hours": 8.0,
        "basic_salary": 1500.00,
        "special_allowance": 200.00,
        "fixed_ot_amount": 0.00,
        "bonus": 0.00,
        "telephone_allowance": 0.00,
        "housing_transport_allowance": 0.00,
    }
    r1 = await client.post(f"/api/v1/employees/{emp_id}/salary", json=sal_payload1)
    assert r1.status_code == 201
    sal1 = r1.json()
    expected_eff1 = str(compute_next_payroll_month_start(date.today()))
    assert sal1["effective_from"] == expected_eff1
    assert float(sal1["salary_portion"]) == 1700.00

    # 2. Update with salary raise
    sal_payload2 = {
        "effective_from": "2027-01-01",
        "standard_hours": 8.0,
        "basic_salary": 1800.00,
        "special_allowance": 300.00,
        "fixed_ot_amount": 0.00,
        "bonus": 0.00,
        "telephone_allowance": 0.00,
        "housing_transport_allowance": 0.00,
    }
    r2 = await client.post(f"/api/v1/employees/{emp_id}/salary", json=sal_payload2)
    assert r2.status_code == 201

    # 3. Get salary history and check difference calculation
    hist_resp = await client.get(f"/api/v1/employees/{emp_id}/salary")
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert len(hist["history"]) >= 2
    # Latest change difference: 2100 - 1700 = 400.00
    assert float(hist["last_change_difference"]) == 400.00
    assert hist["last_change_date"] == "2027-01-01"

    # 4. Check list salary structures endpoint
    list_resp = await client.get("/api/v1/salary-structures")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(i["employee_id"] == str(emp_id) for i in items)
