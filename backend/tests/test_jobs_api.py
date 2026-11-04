"""Integration tests for Worksites, Job Items, Boundaries, and Boundary Queue."""

import socket
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from fw.core.db import async_session_factory, engine
from fw.main import app
from fw.modules.identity import AuthService, User
from fw.modules.org import Accommodation, Employee, Group, Zone


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
    if not is_db_available():
        pytest.skip("PostgreSQL not available on localhost:5432")

    created_temp = False
    async with async_session_factory() as session:
        # Check if bootstrap ADMIN001 already exists
        user = (await session.execute(
            select(User).where(User.username == "ADMIN001")
        )).scalar_one_or_none()

        if user:
            admin_id = user.id
            emp_id = user.employee_id
        else:
            admin_id = uuid4()
            emp_id = uuid4()
            emp = Employee(
                id=emp_id,
                tally_id=f"ADM{str(uuid4())[:6]}",
                name="Jobs Admin",
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
            created_temp = True

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
        if created_temp:
            async with async_session_factory() as session:
                await session.execute(delete(User).where(User.id == admin_id))
                await session.execute(delete(Employee).where(Employee.id == emp_id))
                await session.commit()
        await engine.dispose()


@pytest.fixture
async def test_org_setup():
    async with async_session_factory() as session:
        # Ensure test group
        g = (
            await session.execute(select(Group).where(Group.code == "GRP_TEST_04"))
        ).scalar_one_or_none()
        if not g:
            g = Group(code="GRP_TEST_04", name="Phase 04 Test Group")
            session.add(g)

        # Ensure test zone
        z = (
            await session.execute(select(Zone).where(Zone.code == "ZONE_TEST_04"))
        ).scalar_one_or_none()
        if not z:
            z = Zone(code="ZONE_TEST_04", name="Phase 04 Test Zone")
            session.add(z)

        # Ensure test accommodation
        acc = (
            await session.execute(
                select(Accommodation).where(Accommodation.accommodation_code == "ACC_TEST_04")
            )
        ).scalar_one_or_none()
        if not acc:
            acc = Accommodation(
                accommodation_code="ACC_TEST_04",
                name="Phase 04 Test Camp",
            )
            session.add(acc)

        await session.commit()
        await session.refresh(g)
        await session.refresh(z)
        await session.refresh(acc)
        return {"group_id": str(g.id), "zone_id": str(z.id), "acc_id": str(acc.id)}


@db_required
@pytest.mark.asyncio
async def test_worksite_crud_and_boundary_flow(admin_client, test_org_setup):
    client = admin_client

    # 1. Create worksite 12A14301 (A -> is_outdoor = True)
    ws1_payload = {
        "job_number": f"12A{str(uuid4().int)[:5]}",
        "job_name": "Dubai Marina Landscape",
        "group_id": test_org_setup["group_id"],
        "zone_id": test_org_setup["zone_id"],
        "country": "AE",
        "budget_amount": "50000.00",
    }
    res1 = await client.post("/api/v1/worksites", json=ws1_payload)
    assert res1.status_code == 201, res1.text
    ws1 = res1.json()
    assert ws1["is_outdoor"] is True
    assert ws1["has_boundary"] is False
    ws1_id = ws1["id"]

    # 2. Create worksite with B -> is_outdoor = False
    ws2_payload = {
        "job_number": f"12B{str(uuid4().int)[:5]}",
        "job_name": "Dubai Marina Indoor",
        "group_id": test_org_setup["group_id"],
        "zone_id": test_org_setup["zone_id"],
        "country": "AE",
    }
    res2 = await client.post("/api/v1/worksites", json=ws2_payload)
    assert res2.status_code == 201, res2.text
    ws2 = res2.json()
    assert ws2["is_outdoor"] is False
    assert ws2["has_boundary"] is False
    ws2_id = ws2["id"]

    # 3. Check Boundary Queue: both worksites and accommodation without boundary should be listed
    queue_res = await client.get("/api/v1/boundary-queue")
    assert queue_res.status_code == 200, queue_res.text
    queue_data = queue_res.json()
    assert queue_data["total_count"] >= 2
    assert queue_data["unset_count"] >= 2
    item_codes = [it["code"] for it in queue_data["items"]]
    assert ws1["job_number"] in item_codes
    assert ws2["job_number"] in item_codes

    # 4. Refuse invalid polygon on worksite 1 (self-intersecting bowtie)
    bowtie_polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [55.14, 25.08],
                [55.15, 25.09],
                [55.14, 25.09],
                [55.15, 25.08],
                [55.14, 25.08],
            ]
        ],
    }
    inv_res = await client.put(
        f"/api/v1/worksites/{ws1_id}/boundary",
        json={"boundary": bowtie_polygon},
    )
    assert inv_res.status_code == 422, inv_res.text
    assert inv_res.json()["code"] == "INVALID_POLYGON"

    # 5. Set valid boundary polygon on worksite 1
    valid_polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [55.1400, 25.0800],
                [55.1450, 25.0800],
                [55.1450, 25.0850],
                [55.1400, 25.0850],
                [55.1400, 25.0800],
            ]
        ],
    }
    val_res = await client.put(
        f"/api/v1/worksites/{ws1_id}/boundary",
        json={"boundary": valid_polygon},
    )
    assert val_res.status_code == 200, val_res.text
    updated_ws1 = val_res.json()
    assert updated_ws1["has_boundary"] is True
    assert updated_ws1["rep_latitude"] is not None
    assert updated_ws1["rep_longitude"] is not None

    # 6. Copy boundary from worksite 1 to worksite 2
    copy_res = await client.post(
        f"/api/v1/worksites/{ws2_id}/copy-boundary",
        json={"source_worksite_id": ws1_id},
    )
    assert copy_res.status_code == 200, copy_res.text
    updated_ws2 = copy_res.json()
    assert updated_ws2["has_boundary"] is True
    assert float(updated_ws2["rep_latitude"]) == float(updated_ws1["rep_latitude"])
    assert float(updated_ws2["rep_longitude"]) == float(updated_ws1["rep_longitude"])

    # 7. Add job item to worksite 1 (structured frequency: 6 per week, 3 staff, 9 hours)
    item_payload = {
        "sub_item_code": "A",
        "staff_grade_description": "Gardener - Hand Watering",
        "planned_grade_code": "G1C",
        "frequency_unit": "WEEK",
        "occurrences_per_period": "6.0",
        "period_interval": 1,
        "required_staff_count": 3,
        "hours_per_occurrence_per_staff": "9.0",
        "start_date": "2026-01-01",
        "deployment_type": "PERMANENT",
    }
    item_res = await client.post(
        f"/api/v1/worksites/{ws1_id}/job-items",
        json=item_payload,
    )
    assert item_res.status_code == 201, item_res.text
    job_item = item_res.json()
    assert job_item["expected_activities_per_year"] == "312.000"
    assert job_item["expected_annual_hours"] == "8424.000"
    job_item_id = job_item["id"]

    # 8. Check validation panel endpoint
    v_res = await client.get(f"/api/v1/job-items/{job_item_id}/validation")
    assert v_res.status_code == 200, v_res.text
    val_data = v_res.json()
    assert val_data["calculated_activities_per_year"] == "312.000"
    assert val_data["calculated_annual_hours"] == "8424.000"
    assert val_data["days_per_occurrence"] == 1

    # 9. Check occurrences generated automatically
    occ_res = await client.get(f"/api/v1/occurrences?job_item_id={job_item_id}")
    assert occ_res.status_code == 200, occ_res.text
    occurrences = occ_res.json()
    assert len(occurrences) > 0
    assert occurrences[0]["required_staff_count"] == 3
    assert occurrences[0]["required_hours_per_staff"] == "9.000"


@db_required
@pytest.mark.asyncio
async def test_budget_only_staff_type_produces_no_occurrences(admin_client, test_org_setup):
    client = admin_client

    # Create worksite
    j_num = f"99A{str(uuid4().int)[:5]}"
    ws_res = await client.post(
        "/api/v1/worksites",
        json={
            "job_number": j_num,
            "job_name": "Budget Only Test Job",
            "group_id": test_org_setup["group_id"],
            "zone_id": test_org_setup["zone_id"],
            "country": "AE",
        },
    )
    assert ws_res.status_code == 201, ws_res.text
    ws_id = ws_res.json()["id"]

    # Create job item with HSE Engineer (which is in default budget_only_staff_types)
    item_res = await client.post(
        f"/api/v1/worksites/{ws_id}/job-items",
        json={
            "sub_item_code": "HSE",
            "staff_grade_description": "HSE Engineer",
            "planned_grade_code": "G5A",
            "frequency_unit": "MONTH",
            "occurrences_per_period": "1.0",
            "period_interval": 1,
            "required_staff_count": 1,
            "hours_per_occurrence_per_staff": "9.0",
            "start_date": "2026-01-01",
            "deployment_type": "REMOTE",
        },
    )
    assert item_res.status_code == 201, item_res.text
    item_id = item_res.json()["id"]

    # Verify 0 occurrences generated
    occ_res = await client.get(f"/api/v1/occurrences?job_item_id={item_id}")
    assert occ_res.status_code == 200, occ_res.text
    assert len(occ_res.json()) == 0


@db_required
@pytest.mark.asyncio
async def test_import_worksites_hyphen_rejection_and_commit(admin_client, test_org_setup):
    import io

    import openpyxl

    from fw.modules.imports import generate_import_template_bytes

    client = admin_client
    wb = openpyxl.load_workbook(io.BytesIO(generate_import_template_bytes()))

    # Setup Worksites sheet with an invalid hyphenated job number and a valid job number
    ws_w = wb["Worksites"]
    # Row 5: hyphenated/combined job number -> MUST be rejected with INVALID_JOB_NUMBER
    ws_w.cell(row=5, column=1, value="")
    ws_w.cell(row=5, column=2, value="12A14301-02")
    ws_w.cell(row=5, column=3, value="Hyphenated Job")
    ws_w.cell(row=5, column=5, value="GRP_TEST_04")
    ws_w.cell(row=5, column=6, value="ZONE_TEST_04")
    ws_w.cell(row=5, column=8, value="AE")
    ws_w.cell(row=5, column=9, value="Y")

    # Row 6: valid job number
    valid_jnum = f"33A{str(uuid4().int)[:5]}"
    ws_w.cell(row=6, column=1, value="")
    ws_w.cell(row=6, column=2, value=valid_jnum)
    ws_w.cell(row=6, column=3, value="Valid Imported Worksite")
    ws_w.cell(row=6, column=5, value="GRP_TEST_04")
    ws_w.cell(row=6, column=6, value="ZONE_TEST_04")
    ws_w.cell(row=6, column=8, value="AE")
    ws_w.cell(row=6, column=9, value="Y")

    # Save and upload
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    upload_res = await client.post(
        "/api/v1/imports",
        files={
            "file": (
                "test_worksites.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload_res.status_code == 201, upload_res.text
    preview = upload_res.json()
    assert preview["can_commit"] is False, "Batch with invalid job number should not be committable"

    # Find the row with the hyphenated job number
    invalid_row = next(
        r
        for r in preview["rows"]
        if r["sheet"] == "Worksites" and r["natural_key"] == "12A14301-02"
    )
    assert invalid_row["status"] == "ERROR"
    assert "INVALID_JOB_NUMBER" in invalid_row["codes"]
