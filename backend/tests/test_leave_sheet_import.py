"""The master import reads the Leave sheet (owner decision 25 Nov 2026): pending or approved leave,
validated like the Admin leave import; approved leave takes the worker off the materialised roster."""

import io
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import openpyxl
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import site_today
from fw.main import app
from fw.modules.identity import AuthService, UserService
from fw.modules.imports import generate_import_template_bytes
from fw.modules.scheduling import LeaveRequest, ScheduledWork
from tests.test_roster_materialise import _employee, _item, _off_name, _save

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _workbook(rows: list[list[str | None]]) -> bytes:
    """The template with only these Leave rows (tally, type, from, to, reason, status)."""
    wb = openpyxl.load_workbook(io.BytesIO(generate_import_template_bytes()))
    ws = wb["Leave"]
    for i, row in enumerate(rows):
        ws.cell(row=5 + i, column=1, value=None)
        for j, value in enumerate(row, start=2):
            ws.cell(row=5 + i, column=j, value=value)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _upload(c: AsyncClient, content: bytes) -> dict:
    r = await c.post("/api/v1/imports", files={"file": ("leave.xlsx", content, XLSX)})
    assert r.status_code == 201, r.text
    return r.json()


async def _leave_rows(c: AsyncClient, batch_id: str) -> list[dict]:
    r = await c.get(f"/api/v1/imports/{batch_id}/preview?sheet=Leave")
    assert r.status_code == 200, r.text
    return r.json()["rows"]


async def test_leave_sheet_imports_pending_and_approved(db_session: AsyncSession) -> None:
    today = site_today("AE")
    item = await _item(db_session)
    emp = await _employee(db_session, weekly_off=_off_name(today + timedelta(days=6)))
    await _save(db_session, item, [(emp.id, Decimal("8"))])
    leave_from, leave_to = today + timedelta(days=2), today + timedelta(days=3)
    later_from, later_to = today + timedelta(days=60), today + timedelta(days=61)

    admin = await UserService.get_or_create_system_admin(db_session)
    await db_session.commit()
    headers = {"Authorization": f"Bearer {AuthService.create_access_token(admin)}"}
    content = _workbook(
        [
            [emp.tally_id, "ANNUAL", leave_from.isoformat(), leave_to.isoformat(), "Trip", None],
            [emp.tally_id, "SICK", later_from.isoformat(), later_to.isoformat(), None, "PENDING"],
        ]
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t", headers=headers
    ) as c:
        batch = await _upload(c, content)
        assert batch["can_commit"] is True, batch
        rows = await _leave_rows(c, batch["batch_id"])
        assert [r["action"] for r in rows] == ["NEW", "NEW"]
        r = await c.post(f"/api/v1/imports/{batch['batch_id']}/commit")
        assert r.status_code == 200, r.text

        leaves = {
            lv.leave_type: lv
            for lv in (
                await db_session.execute(
                    select(LeaveRequest).where(LeaveRequest.employee_id == emp.id)
                )
            )
            .scalars()
            .all()
        }
        assert leaves["ANNUAL"].status == "APPROVED"
        assert leaves["ANNUAL"].approved_by_user_id == admin.id
        assert leaves["SICK"].status == "REQUESTED"
        days = set(
            (
                await db_session.execute(
                    select(ScheduledWork.work_date).where(
                        ScheduledWork.employee_id == emp.id,
                        ScheduledWork.job_item_id == item.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert days and leave_from not in days and leave_to not in days

        # The same file again changes nothing.
        again = await _upload(c, content)
        assert [r["action"] for r in await _leave_rows(c, again["batch_id"])] == [
            "UNCHANGED",
            "UNCHANGED",
        ]


async def test_leave_sheet_validation_errors(db_session: AsyncSession) -> None:
    today = site_today("AE")
    emp = await _employee(db_session)
    admin = await UserService.get_or_create_system_admin(db_session)
    db_session.add(
        LeaveRequest(
            employee_id=emp.id,
            leave_type="ANNUAL",
            from_date=today + timedelta(days=10),
            to_date=today + timedelta(days=12),
            reason="Existing",
            status="APPROVED",
            recorded_by_user_id=admin.id,
        )
    )
    await db_session.commit()
    headers = {"Authorization": f"Bearer {AuthService.create_access_token(admin)}"}
    d = lambda n: (today + timedelta(days=n)).isoformat()  # noqa: E731
    content = _workbook(
        [
            [f"NOPE{uuid4().hex[:6]}", "ANNUAL", d(20), d(21), None, None],  # unknown worker
            [emp.tally_id, "HOLIDAY", d(30), d(31), None, None],  # not a leave type
            [emp.tally_id, "SICK", d(41), d(40), None, None],  # to before from
            [emp.tally_id, "SICK", d(11), d(14), None, None],  # overlaps existing leave
            [emp.tally_id, "UNPAID", d(50), d(52), None, "MAYBE"],  # unknown status
            [emp.tally_id, "UNPAID", d(70), d(72), None, None],  # overlaps the next row
            [emp.tally_id, "OTHER", d(72), d(73), None, None],
        ]
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t", headers=headers
    ) as c:
        batch = await _upload(c, content)
        assert batch["can_commit"] is False
        rows = await _leave_rows(c, batch["batch_id"])
    codes = [set(r["codes"]) for r in sorted(rows, key=lambda r: r["row_number"])]
    assert "REFERENCE_NOT_FOUND" in codes[0]
    assert codes[1] and all(r["status"] == "ERROR" for r in rows[:5])
    assert "INVALID_DATE_RANGE" in codes[2]
    assert "LEAVE_OVERLAP" in codes[3]
    assert codes[4]
    assert "LEAVE_OVERLAP" in codes[6]
