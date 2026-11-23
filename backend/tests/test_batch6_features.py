"""Tests for Batch 6 operational updates:
- Worksite supervisor assignment and operational scoping
- Supervisor worker directory scoping
- Employee profile details update and immutable attribute change history
- Future-dated salary revision update and deletion with DEC-06 guardrails
- Salary structure DEC-39 cost breakdown and Admin-only RBAC
- Import & Export RBAC (Admin & Engineer only) and two-sheet Worksite Excel export
"""

import io
import socket
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.clock import site_today
from fw.core.db import async_session_factory
from fw.main import create_app
from fw.modules.identity import User
from fw.modules.identity.service import AuthService, hash_password
from fw.modules.jobs.models import JobItem, Worksite, WorksiteSupervisor
from fw.modules.org.models import Employee, Group, Zone
from fw.modules.payroll.models import EmployeeSalary
from fw.modules.scheduling.models import ScheduledWork


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


async def get_admin_user_and_token(session) -> tuple[User, str]:
    admin_user = (
        await session.execute(select(User).where(User.role == "ADMIN"))
    ).scalar_one_or_none()
    if not admin_user:
        admin_user = User(
            username=f"admin_{uuid4().hex[:6]}",
            credential_hash=hash_password("Password123!"),
            role="ADMIN",
            is_active=True,
            employee_id=None,
        )
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)
    token = AuthService.create_access_token(admin_user)
    return admin_user, token


async def create_user_with_token(session, role: str, name: str | None = None) -> tuple[User, str]:
    if role == "ADMIN":
        return await get_admin_user_and_token(session)

    name = name or f"Test {role} {uuid4().hex[:6]}"
    emp = Employee(
        tally_id=f"EMP_{uuid4().hex[:6]}",
        name=name,
        role=role,
        is_active=True,
        country="AE",
    )
    session.add(emp)
    await session.flush()

    username = f"user_{uuid4().hex[:8]}"
    user = User(
        username=username,
        credential_hash=hash_password("Password123!"),
        role=role,
        is_active=True,
        employee_id=emp.id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = AuthService.create_access_token(user)
    return user, token


async def create_test_worksite(session, name: str, budget: Decimal | None = None) -> Worksite:
    grp = Group(name=f"Grp_{uuid4().hex[:6]}", code=f"GRP_{uuid4().hex[:6]}")
    zn = Zone(name=f"Zn_{uuid4().hex[:6]}", code=f"ZN_{uuid4().hex[:6]}")
    session.add_all([grp, zn])
    await session.flush()

    ws = Worksite(
        job_number=f"JN_{uuid4().hex[:6]}",
        job_name=name,
        group_id=grp.id,
        zone_id=zn.id,
        country="AE",
        is_active=True,
        budget_amount=budget,
    )
    session.add(ws)
    await session.commit()
    await session.refresh(ws)
    return ws


@db_required
@pytest.mark.asyncio
async def test_worksite_supervisor_assignment_and_scoping():
    """Verify assigning a supervisor scopes their worksite listing and masks budget for non-admins."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with async_session_factory() as session:
            admin_user, admin_token = await create_user_with_token(session, "ADMIN")
            sup_user, sup_token = await create_user_with_token(session, "SUPERVISOR")

            # Create 2 worksites
            w1 = await create_test_worksite(session, "Assigned Worksite Alpha", Decimal("50000.00"))
            w2 = await create_test_worksite(
                session, "Unassigned Worksite Beta", Decimal("75000.00")
            )

        # 1. Admin assigns supervisor to w1
        resp = await client.post(
            f"/api/v1/worksites/{w1.id}/supervisors",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"supervisor_id": str(sup_user.employee_id)},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["supervisor_id"] == str(sup_user.employee_id)
        assert data["worksite_id"] == str(w1.id)

        # 2. List supervisors of w1
        resp = await client.get(
            f"/api/v1/worksites/{w1.id}/supervisors",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        sups = resp.json()
        assert len(sups) == 1
        assert sups[0]["supervisor_id"] == str(sup_user.employee_id)

        # 3. Supervisor lists worksites -> only w1 is returned, budget_amount is masked (None)
        resp = await client.get(
            "/api/v1/worksites",
            headers={"Authorization": f"Bearer {sup_token}"},
        )
        assert resp.status_code == 200
        ws_list = resp.json()
        ws_ids = [w["id"] for w in ws_list]
        assert str(w1.id) in ws_ids
        assert str(w2.id) not in ws_ids
        target_ws = next(w for w in ws_list if w["id"] == str(w1.id))
        assert target_ws["budget_amount"] is None

        # 4. Admin lists worksites -> both w1 and w2 returned, budget_amount visible
        resp = await client.get(
            "/api/v1/worksites",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        admin_ws_list = resp.json()
        admin_ws_ids = [w["id"] for w in admin_ws_list]
        assert str(w1.id) in admin_ws_ids
        assert str(w2.id) in admin_ws_ids
        target_ws = next(w for w in admin_ws_list if w["id"] == str(w1.id))
        assert float(target_ws["budget_amount"]) == 50000.0

        # 5. Admin unassigns supervisor from w1
        resp = await client.delete(
            f"/api/v1/worksites/{w1.id}/supervisors/{sup_user.employee_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 204

        # Verify supervisor list is now empty
        resp = await client.get(
            f"/api/v1/worksites/{w1.id}/supervisors",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0


@db_required
@pytest.mark.asyncio
async def test_supervisor_worker_directory_scoping():
    """Verify supervisor can only see workers assigned to their worksite's job items."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with async_session_factory() as session:
            admin_user, admin_token = await create_user_with_token(session, "ADMIN")
            sup_user, sup_token = await create_user_with_token(session, "SUPERVISOR")

            w1 = await create_test_worksite(session, "Scoping Site 1")
            _w2 = await create_test_worksite(session, "Scoping Site 2")

            # Assign supervisor to w1
            sup_link = WorksiteSupervisor(worksite_id=w1.id, supervisor_id=sup_user.employee_id)
            session.add(sup_link)

            # Create 2 workers
            worker_in = Employee(
                tally_id=f"WK_{uuid4().hex[:6]}",
                name="Worker Inside W1",
                role="WORKER",
                is_active=True,
                country="AE",
            )
            worker_out = Employee(
                tally_id=f"WK_{uuid4().hex[:6]}",
                name="Worker Outside W2",
                role="WORKER",
                is_active=True,
                country="AE",
            )
            session.add_all([worker_in, worker_out])
            await session.flush()

            # Create job item for w1 and schedule worker_in to it
            ji = JobItem(
                worksite_id=w1.id,
                sub_item_code="01",
                staff_grade_description="Helper",
                planned_grade_code="G1A",
                frequency_unit="WEEK",
                occurrences_per_period=Decimal("6.0"),
                period_interval=1,
                required_staff_count=1,
                hours_per_occurrence_per_staff=Decimal("8.0"),
                start_date=date(2026, 1, 1),
                deployment_type="PERMANENT",
                is_active=True,
            )
            session.add(ji)
            await session.flush()

            sw = ScheduledWork(
                work_date=site_today("AE"),
                employee_id=worker_in.id,
                job_item_id=ji.id,
                worksite_id=w1.id,
                assigned_hours=Decimal("8.00"),
                status="ACTIVE",
            )
            session.add(sw)
            await session.commit()

        # Supervisor requests employees list
        resp = await client.get(
            "/api/v1/employees",
            headers={"Authorization": f"Bearer {sup_token}"},
        )
        assert resp.status_code == 200
        employees = resp.json()
        emp_ids = [e["id"] for e in employees]

        # Supervisor must see themselves and worker_in, but NOT worker_out
        assert str(worker_in.id) in emp_ids
        assert str(worker_out.id) not in emp_ids


@db_required
@pytest.mark.asyncio
async def test_employee_profile_details_and_attribute_history():
    """Verify PATCH /employees/{id}/profile-details logs changes into employee_attribute_history."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with async_session_factory() as session:
            admin_user, admin_token = await create_user_with_token(session, "ADMIN")

            emp = Employee(
                tally_id=f"EMP_{uuid4().hex[:6]}",
                name="History Test Worker",
                role="WORKER",
                staff_grade_description="Helper",
                grade_code="G1A",
                is_driver=False,
                is_active=True,
                country="AE",
            )
            session.add(emp)
            await session.commit()
            await session.refresh(emp)

        # Update profile details
        resp = await client.patch(
            f"/api/v1/employees/{emp.id}/profile-details",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "staff_grade_description": "Gardener Expert",
                "grade_code": "G2B",
                "is_driver": True,
                "reason": "Annual promotion & license acquired",
            },
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["staff_grade_description"] == "Gardener Expert"
        assert updated["grade_code"] == "G2B"
        assert updated["is_driver"] is True

        # Fetch attribute history
        resp = await client.get(
            f"/api/v1/employees/{emp.id}/attribute-history",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) == 3

        history_map = {h["attribute_name"]: h for h in history}
        assert "STAFF_GRADE_DESCRIPTION" in history_map
        assert history_map["STAFF_GRADE_DESCRIPTION"]["old_value"] == "Helper"
        assert history_map["STAFF_GRADE_DESCRIPTION"]["new_value"] == "Gardener Expert"
        assert (
            history_map["STAFF_GRADE_DESCRIPTION"]["reason"]
            == "Annual promotion & license acquired"
        )

        assert "GRADE_CODE" in history_map
        assert history_map["GRADE_CODE"]["old_value"] == "G1A"
        assert history_map["GRADE_CODE"]["new_value"] == "G2B"

        assert "IS_DRIVER" in history_map
        assert history_map["IS_DRIVER"]["old_value"] == "False"
        assert history_map["IS_DRIVER"]["new_value"] == "True"


@db_required
@pytest.mark.asyncio
async def test_future_salary_revision_update_and_delete_with_guardrails():
    """Verify editing/deleting future salary revisions and rejecting past revisions (DEC-06)."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        today = site_today("AE")
        past_date = today - timedelta(days=30)
        future_date = today + timedelta(days=30)

        async with async_session_factory() as session:
            admin_user, admin_token = await create_user_with_token(session, "ADMIN")

            emp = Employee(
                tally_id=f"SAL_{uuid4().hex[:6]}",
                name="Salary Revision Test Worker",
                role="WORKER",
                is_active=True,
                country="AE",
            )
            session.add(emp)
            await session.flush()

            past_sal = EmployeeSalary(
                employee_id=emp.id,
                basic_salary=Decimal("1200.00"),
                special_allowance=Decimal("100.00"),
                effective_from=past_date,
            )
            future_sal = EmployeeSalary(
                employee_id=emp.id,
                basic_salary=Decimal("1500.00"),
                special_allowance=Decimal("150.00"),
                effective_from=future_date,
            )
            session.add_all([past_sal, future_sal])
            await session.commit()
            await session.refresh(past_sal)
            await session.refresh(future_sal)

        # 1. Update past salary -> rejected with 422
        resp = await client.patch(
            f"/api/v1/employees/{emp.id}/salary/{past_sal.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"basic_salary": 1300.0},
        )
        assert resp.status_code == 422
        assert "CANNOT_MODIFY_HISTORICAL_SALARY" in resp.text

        # 2. Delete past salary -> rejected with 422
        resp = await client.delete(
            f"/api/v1/employees/{emp.id}/salary/{past_sal.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "CANNOT_MODIFY_HISTORICAL_SALARY" in resp.text

        # 3. Update future salary -> succeeds
        resp = await client.patch(
            f"/api/v1/employees/{emp.id}/salary/{future_sal.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"basic_salary": 1800.0, "special_allowance": 200.0},
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert float(updated["basic_salary"]) == 1800.0
        assert float(updated["special_allowance"]) == 200.0

        # 4. Delete future salary -> succeeds
        resp = await client.delete(
            f"/api/v1/employees/{emp.id}/salary/{future_sal.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 204


@db_required
@pytest.mark.asyncio
async def test_salary_structure_cost_breakdown_and_rbac():
    """Verify DEC-39 cost calculations and Admin-only RBAC on /salary-structures."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with async_session_factory() as session:
            admin_user, admin_token = await create_user_with_token(session, "ADMIN")
            sup_user, sup_token = await create_user_with_token(session, "SUPERVISOR")

            emp = Employee(
                tally_id=f"COST_{uuid4().hex[:6]}",
                name="Cost Breakdown Worker",
                role="WORKER",
                is_active=True,
                country="AE",
            )
            session.add(emp)
            await session.flush()

            sal = EmployeeSalary(
                employee_id=emp.id,
                basic_salary=Decimal("1200.00"),
                special_allowance=Decimal("200.00"),
                fixed_ot_amount=Decimal("100.00"),
                effective_from=date(2026, 1, 1),
            )
            session.add(sal)
            await session.commit()

        # 1. Supervisor access denied (DEC-47)
        resp = await client.get(
            "/api/v1/salary-structures",
            headers={"Authorization": f"Bearer {sup_token}"},
        )
        assert resp.status_code == 403

        # 2. Admin access allowed with full cost breakdown
        resp = await client.get(
            "/api/v1/salary-structures",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        structures = resp.json()
        target = next(s for s in structures if s["employee_id"] == str(emp.id))

        assert float(target["basic_salary"]) == 1200.0
        assert float(target["salary_portion"]) == 1500.0  # 1200 + 200 + 100
        # Gratuity: (1200 / 365) * 30 = 98.63
        assert float(target["gratuity"]) == 98.63
        # Leave salary: 1200 / 12 = 100.00
        assert float(target["leave_salary"]) == 100.00
        # Provisions from settings (132+65+30+550+65 = 842) + 98.63 + 100.00 = 1040.63
        assert float(target["per_month_provision"]) == 1040.63
        # Staff cost: 1500 + 1040.63 = 2540.63
        assert float(target["total_staff_cost"]) == 2540.63
        # HR OH: 2540.63 * 0.05 = 127.03
        assert float(target["hr_oh"]) == 127.03
        # Final cost: 2540.63 + 127.03 = 2667.66
        assert float(target["final_cost"]) == 2667.66


@db_required
@pytest.mark.asyncio
async def test_import_and_export_rbac_and_two_sheet_worksite_export():
    """Verify import/export restricted to Admin & Engineer and worksite export has 2 sheets."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with async_session_factory() as session:
            admin_user, admin_token = await create_user_with_token(session, "ADMIN")
            eng_user, eng_token = await create_user_with_token(session, "ENGINEER")
            sup_user, sup_token = await create_user_with_token(session, "SUPERVISOR")

            # Create worksite with job item
            ws = await create_test_worksite(session, "Export Test Worksite", Decimal("120000.00"))

            ji = JobItem(
                worksite_id=ws.id,
                sub_item_code="JI_EXP_01",
                staff_grade_description="Gardener",
                planned_grade_code="G3C",
                frequency_unit="WEEK",
                occurrences_per_period=Decimal("6.0"),
                period_interval=1,
                required_staff_count=2,
                hours_per_occurrence_per_staff=Decimal("8.0"),
                start_date=date(2026, 1, 1),
                deployment_type="PERMANENT",
                is_active=True,
            )
            session.add(ji)
            await session.commit()

        # 1. Supervisor denied export & import
        resp = await client.get(
            "/api/v1/worksites/export",
            headers={"Authorization": f"Bearer {sup_token}"},
        )
        assert resp.status_code == 403

        resp = await client.get(
            "/api/v1/employees/export",
            headers={"Authorization": f"Bearer {sup_token}"},
        )
        assert resp.status_code == 403

        # 2. Engineer allowed export
        resp = await client.get(
            "/api/v1/worksites/export",
            headers={"Authorization": f"Bearer {eng_token}"},
        )
        assert resp.status_code == 200

        # 3. Admin export contains two sheets: Worksites and Job_Items
        resp = await client.get(
            "/api/v1/worksites/export",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(resp.content), data_only=True)
        sheet_names = wb.sheetnames
        assert "Worksites" in sheet_names
        assert "Job_Items" in sheet_names

        # Check Job_Items sheet contents
        ji_sheet = wb["Job_Items"]
        assert ji_sheet.cell(row=1, column=1).value == "Job Number"
        assert ji_sheet.cell(row=1, column=2).value == "Worksite Name"
        assert ji_sheet.cell(row=1, column=3).value == "Sub Item Code"
        assert ji_sheet.cell(row=1, column=4).value == "Staff Grade Description"
        assert ji_sheet.cell(row=1, column=5).value == "Planned Grade Code"

        # Verify our created job item row is present
        found = False
        for r in range(2, ji_sheet.max_row + 1):
            if ji_sheet.cell(row=r, column=3).value == "JI_EXP_01":
                found = True
                assert ji_sheet.cell(row=r, column=4).value == "Gardener"
                assert ji_sheet.cell(row=r, column=5).value == "G3C"
                break
        assert found, "Created job item not found in Job_Items sheet"
