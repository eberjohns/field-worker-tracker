"""Integration tests for Worksites, Job Items, Boundaries, and Boundary Queue."""

import socket
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.db import async_session_factory, engine
from fw.main import app
from fw.modules.identity import AuthService, User, hash_password
from fw.modules.org import Accommodation, Group, Zone


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

    async with async_session_factory() as session:
        from fw.modules.identity import UserService

        user = await UserService.get_or_create_system_admin(session)
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


@db_required
async def test_update_job_item_with_occurrence_regeneration(admin_client, test_org_setup):
    """Verify editing job item regenerates occurrences idempotently without duplicate key errors."""
    client = admin_client
    jnum = f"22B{str(uuid4().int)[:5]}"

    # Create worksite
    ws_res = await client.post(
        "/api/v1/worksites",
        json={
            "job_number": jnum,
            "job_name": f"Test Site {jnum}",
            "group_id": test_org_setup["group_id"],
            "zone_id": test_org_setup["zone_id"],
            "country": "AE",
            "is_active": True,
        },
    )
    assert ws_res.status_code == 201, ws_res.text
    ws_id = ws_res.json()["id"]

    # Create job item with weekday pattern
    create_res = await client.post(
        f"/api/v1/worksites/{ws_id}/job-items",
        json={
            "sub_item_code": "01",
            "staff_grade_description": "Gardener Expert",
            "planned_grade_code": "G1",
            "frequency_unit": "WEEK",
            "occurrences_per_period": 3,
            "period_interval": 1,
            "weekday_pattern": ["MON", "WED", "FRI"],
            "required_staff_count": 2,
            "hours_per_occurrence_per_staff": 9.0,
            "deployment_type": "PERMANENT",
            "start_date": "2026-01-01",
        },
    )
    assert create_res.status_code == 201, create_res.text
    item = create_res.json()
    item_id = item["id"]
    version = item["version"]

    # Patch job item with updated weekday pattern and hours
    patch_res = await client.patch(
        f"/api/v1/job-items/{item_id}",
        json={
            "hours_per_occurrence_per_staff": 8.0,
            "weekday_pattern": ["MON", "TUE", "THU"],
            "version": version,
        },
    )
    assert patch_res.status_code == 200, patch_res.text
    updated = patch_res.json()
    assert updated["version"] == version + 1
    assert float(updated["hours_per_occurrence_per_staff"]) == 8.0
    assert updated["weekday_pattern"] == ["MON", "TUE", "THU"]


@db_required
async def test_reset_database_endpoint_admin_only(admin_client):
    """Verify reset-database requires admin, confirmation_text, and valid admin password."""
    client = admin_client

    # Ensure the active admin account has a known password before testing reset
    async with async_session_factory() as session:
        admin_user = (
            await session.execute(select(User).where(User.role == "ADMIN").limit(1))
        ).scalar_one_or_none()
        assert admin_user is not None
        admin_user.credential_hash = hash_password("Admin@1234")
        await session.commit()

    # Wrong confirmation text -> 400
    bad_confirm = await client.post(
        "/api/v1/settings/reset-database",
        json={"confirmation_text": "WRONG", "admin_password": "Admin@1234"},
    )
    assert bad_confirm.status_code == 400, bad_confirm.text

    # Wrong admin password -> 403
    bad_pass = await client.post(
        "/api/v1/settings/reset-database",
        json={"confirmation_text": "RESET", "admin_password": "WrongPassword!"},
    )
    assert bad_pass.status_code == 403, bad_pass.text

    # Valid confirmation text and admin password -> 200
    res = await client.post(
        "/api/v1/settings/reset-database",
        json={"confirmation_text": "RESET", "admin_password": "Admin@1234"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "success"
    assert "ADMIN001" in data["message"]


@db_required
async def test_boundaries_export_and_import(admin_client):
    """Test boundary export (CSV/JSON) and bulk boundary import with graceful skip reporting."""
    client = admin_client

    # 1. Export as JSON
    json_res = await client.get("/api/v1/boundaries/export?format=json")
    assert json_res.status_code == 200, json_res.text
    exported_list = json_res.json()
    assert isinstance(exported_list, list)

    # 2. Export as CSV
    csv_res = await client.get("/api/v1/boundaries/export?format=csv")
    assert csv_res.status_code == 200, csv_res.text
    assert "entity_type,code,name,has_boundary,format,polygon" in csv_res.text

    # 3. Import boundaries with valid, invalid, and unknown codes
    valid_wkt = "POLYGON((55.385000 25.120000, 55.390000 25.120000, 55.390000 25.125000, 55.385000 25.125000, 55.385000 25.120000))"
    import_payload = {
        "items": [
            {
                "entity_type": "WORKSITE",
                "code": "12A14301",
                "polygon": valid_wkt,
            },
            {
                "entity_type": "WORKSITE",
                "code": "NON_EXISTENT_999",
                "polygon": valid_wkt,
            },
            {
                "entity_type": "ACCOMMODATION",
                "code": "WARSAN_01",
                "polygon": valid_wkt,
            },
            {
                "entity_type": "ACCOMMODATION",
                "code": "UNKNOWN_CAMP_XYZ",
                "polygon": valid_wkt,
            },
        ]
    }

    import_res = await client.post("/api/v1/boundaries/import", json=import_payload)
    assert import_res.status_code == 200, import_res.text
    result = import_res.json()

    assert result["total_rows"] == 4
    # Both unknown codes should be skipped with detailed errors
    assert result["skipped_count"] >= 2
    reasons = [e["reason"] for e in result["errors"]]
    assert any("NON_EXISTENT_999" in r for r in reasons)
    assert any("UNKNOWN_CAMP_XYZ" in r for r in reasons)


@db_required
@pytest.mark.asyncio
async def test_job_item_create_validations(admin_client, test_org_setup):
    """Test JobItemCreate validations: required start_date, grade code, and controlled SGD."""
    client = admin_client

    # 1. Create worksite
    j_num = f"99B{str(uuid4().int)[:5]}"
    ws_res = await client.post(
        "/api/v1/worksites",
        json={
            "job_number": j_num,
            "job_name": "Job Item Validation Worksite",
            "group_id": test_org_setup["group_id"],
            "zone_id": test_org_setup["zone_id"],
            "country": "AE",
            "start_date": "2026-02-01",
        },
    )
    assert ws_res.status_code == 201, ws_res.text
    ws_id = ws_res.json()["id"]

    # 2. Rejection when staff_grade_description is not in controlled list
    res_bad_sgd = await client.post(
        f"/api/v1/worksites/{ws_id}/job-items",
        json={
            "sub_item_code": "01",
            "staff_grade_description": "GARDENER",
            "planned_grade_code": "G1A",
            "start_date": "2026-02-01",
            "frequency_unit": "WEEK",
            "occurrences_per_period": 6,
            "period_interval": 1,
            "required_staff_count": 1,
            "hours_per_occurrence_per_staff": 8.0,
            "deployment_type": "PERMANENT",
        },
    )
    assert res_bad_sgd.status_code == 422
    err_sgd = res_bad_sgd.json()
    assert "not in the controlled list" in str(err_sgd)

    # 3. Rejection when start_date is missing
    res_no_date = await client.post(
        f"/api/v1/worksites/{ws_id}/job-items",
        json={
            "sub_item_code": "02",
            "staff_grade_description": "Gardener Helper",
            "planned_grade_code": "G1A",
            "frequency_unit": "WEEK",
            "occurrences_per_period": 6,
            "period_interval": 1,
            "required_staff_count": 1,
            "hours_per_occurrence_per_staff": 8.0,
            "deployment_type": "PERMANENT",
        },
    )
    assert res_no_date.status_code == 422
    err_date = res_no_date.json()
    assert "start_date" in str(err_date)

    # 4. Rejection when planned_grade_code is missing
    res_no_grade = await client.post(
        f"/api/v1/worksites/{ws_id}/job-items",
        json={
            "sub_item_code": "03",
            "staff_grade_description": "Gardener Helper",
            "start_date": "2026-02-01",
            "frequency_unit": "WEEK",
            "occurrences_per_period": 6,
            "period_interval": 1,
            "required_staff_count": 1,
            "hours_per_occurrence_per_staff": 8.0,
            "deployment_type": "PERMANENT",
        },
    )
    assert res_no_grade.status_code == 422
    err_grade = res_no_grade.json()
    assert "planned_grade_code" in str(err_grade)

    # 5. Success with start_date, grade code, and controlled SGD
    res_ok = await client.post(
        f"/api/v1/worksites/{ws_id}/job-items",
        json={
            "sub_item_code": "01",
            "staff_grade_description": "Gardener Expert",
            "planned_grade_code": "G1A",
            "start_date": "2026-02-01",
            "end_date": "2026-12-31",
            "frequency_unit": "WEEK",
            "occurrences_per_period": 6,
            "period_interval": 1,
            "required_staff_count": 2,
            "hours_per_occurrence_per_staff": 8.0,
            "deployment_type": "PERMANENT",
        },
    )
    assert res_ok.status_code == 201, res_ok.text
    item_data = res_ok.json()
    assert item_data["sub_item_code"] == "01"
    assert item_data["staff_grade_description"] == "Gardener Expert"
    assert item_data["planned_grade_code"] == "G1A"
    assert item_data["start_date"] == "2026-02-01"
    assert item_data["end_date"] == "2026-12-31"
