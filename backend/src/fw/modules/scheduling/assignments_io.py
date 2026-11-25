"""Operational Planner: export and import of job item assignments (19 Nov meeting item 6).

One row per worker, job item and day, in a plain sheet that round-trips: what the export
writes, the import reads. The import only **adds** assignments (DIRECT shifts, as when a
planner adds a worker to a cell). It never changes or removes existing rows; those stay
planner edits. Every row goes through the same validation as the planner
(`validate_scheduled_work_request`); errors skip the row, warnings are reported and accepted.
A check-only pass (`dry_run`) reports what would happen without writing anything.

Scope (DEC-57): Admin sees and imports everywhere; other roles only on worksites in scope.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

import openpyxl
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.errors import AppError
from fw.modules.identity import User
from fw.modules.jobs import JobItem, Worksite
from fw.modules.org import Employee
from fw.modules.scheduling.models import ScheduledWork
from fw.modules.scheduling.schemas import OperationalShiftCreate, ScheduledWorkValidateRequest
from fw.modules.scheduling.scope import AccessScope

SHEET = "Assignments"
COLUMNS = (
    "Job Number",
    "Job Name",
    "Sub Item Code",
    "Work Date",
    "Tally ID",
    "Worker Name",
    "Assigned Hours",
    "Source",
)
REQUIRED = ("Job Number", "Sub Item Code", "Work Date", "Tally ID")
MAX_RANGE_DAYS = 92
MAX_ROWS = 5000


@dataclass
class ImportRowResult:
    row: int
    status: str  # CREATED | WOULD_CREATE | EXISTS | ERROR
    message: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    dry_run: bool
    rows: list[ImportRowResult] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(1 for r in self.rows if r.status == status)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "created": self.count("CREATED"),
            "would_create": self.count("WOULD_CREATE"),
            "existing": self.count("EXISTS"),
            "errors": self.count("ERROR"),
            "rows": [
                {"row": r.row, "status": r.status, "message": r.message, "warnings": r.warnings}
                for r in self.rows
            ],
        }


def _check_range(from_date: date, to_date: date) -> None:
    if to_date < from_date or (to_date - from_date).days + 1 > MAX_RANGE_DAYS:
        raise AppError(
            code="VALIDATION_ERROR",
            message=f"Choose a range of 1 to {MAX_RANGE_DAYS} days.",
            status_code=400,
        )


async def export_assignments_xlsx(
    session: AsyncSession, user: User, from_date: date, to_date: date
) -> bytes:
    """Active assignments in the range, on the worksites the user can see."""
    _check_range(from_date, to_date)
    scope = await AccessScope.resolve(session, user)
    stmt = (
        select(ScheduledWork, JobItem, Worksite, Employee)
        .join(JobItem, ScheduledWork.job_item_id == JobItem.id)
        .join(Worksite, ScheduledWork.worksite_id == Worksite.id)
        .join(Employee, ScheduledWork.employee_id == Employee.id)
        .where(
            ScheduledWork.status == "ACTIVE",
            ScheduledWork.work_date >= from_date,
            ScheduledWork.work_date <= to_date,
        )
        .order_by(
            ScheduledWork.work_date,
            Worksite.job_number,
            JobItem.sub_item_code,
            Employee.tally_id,
        )
    )
    ws_filter = scope.worksite_filter
    if ws_filter is not None:
        stmt = stmt.where(ScheduledWork.worksite_id.in_(ws_filter))
    rows = (await session.execute(stmt)).all()

    wb = openpyxl.Workbook()
    sheet = wb.active
    assert sheet is not None
    sheet.title = SHEET
    sheet.append(list(COLUMNS))
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="334155")
    for sw, item, ws, emp in rows:
        sheet.append(
            [
                ws.job_number,
                ws.job_name,
                item.sub_item_code,
                sw.work_date,
                emp.tally_id,
                emp.name,
                float(sw.assigned_hours),
                sw.source,
            ]
        )
    for col, width in zip("ABCDEFGH", (14, 30, 14, 12, 12, 28, 14, 12), strict=True):
        sheet.column_dimensions[col].width = width
    for (cell,) in sheet.iter_rows(min_row=2, min_col=4, max_col=4):
        cell.number_format = "yyyy-mm-dd"
    sheet.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


async def import_assignments_xlsx(
    session: AsyncSession, user: User, content: bytes, dry_run: bool
) -> ImportResult:
    """Add the sheet's assignments that don't exist yet (see the module docstring)."""
    from fw.modules.scheduling.service import SchedulingService  # avoids an import cycle

    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - any unreadable upload is the same user error
        raise AppError(
            code="VALIDATION_ERROR", message="The file is not a readable .xlsx.", status_code=400
        ) from exc
    sheet = wb[SHEET] if SHEET in wb.sheetnames else wb.worksheets[0]
    raw_rows = list(sheet.iter_rows(values_only=True))
    if not raw_rows:
        raise AppError(code="VALIDATION_ERROR", message="The sheet is empty.", status_code=400)
    header = [_text(h) for h in raw_rows[0]]
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise AppError(
            code="VALIDATION_ERROR",
            message=f"Missing columns: {', '.join(missing)}. Start from an export.",
            status_code=400,
        )
    col = {name: header.index(name) for name in header if name}
    data_rows = [
        (i + 2, r) for i, r in enumerate(raw_rows[1:]) if any(v not in (None, "") for v in r)
    ]
    if len(data_rows) > MAX_ROWS:
        raise AppError(
            code="VALIDATION_ERROR",
            message=f"At most {MAX_ROWS} rows per file.",
            status_code=400,
        )

    scope = await AccessScope.resolve(session, user)
    service = SchedulingService(session)
    result = ImportResult(dry_run=dry_run)
    seen: set[tuple[UUID, UUID, date]] = set()
    item_cache: dict[tuple[str, str], JobItem | None] = {}
    emp_cache: dict[str, Employee | None] = {}

    def cell(row: tuple[Any, ...], name: str) -> Any:
        idx = col.get(name)
        return row[idx] if idx is not None and idx < len(row) else None

    for row_no, row in data_rows:
        job_number = _text(cell(row, "Job Number"))
        sub_code = _text(cell(row, "Sub Item Code"))
        tally_id = _text(cell(row, "Tally ID"))
        work_date = _parse_date(cell(row, "Work Date"))
        if not (job_number and sub_code and tally_id and work_date):
            result.rows.append(
                ImportRowResult(
                    row_no, "ERROR", "Job Number, Sub Item Code, Work Date and Tally ID are needed."
                )
            )
            continue

        key_item = (job_number, sub_code)
        if key_item not in item_cache:
            item_cache[key_item] = (
                await session.execute(
                    select(JobItem)
                    .join(Worksite, JobItem.worksite_id == Worksite.id)
                    .where(Worksite.job_number == job_number, JobItem.sub_item_code == sub_code)
                )
            ).scalar_one_or_none()
        item = item_cache[key_item]
        if item is None:
            result.rows.append(
                ImportRowResult(row_no, "ERROR", f"No job item {sub_code} on job {job_number}.")
            )
            continue
        if not scope.can_view_worksite(item.worksite_id):
            result.rows.append(
                ImportRowResult(row_no, "ERROR", f"Job {job_number} is outside your worksites.")
            )
            continue

        if tally_id not in emp_cache:
            emp_cache[tally_id] = (
                await session.execute(select(Employee).where(Employee.tally_id == tally_id))
            ).scalar_one_or_none()
        emp = emp_cache[tally_id]
        if emp is None:
            result.rows.append(ImportRowResult(row_no, "ERROR", f"No employee {tally_id}."))
            continue

        hours_raw = cell(row, "Assigned Hours")
        try:
            hours = (
                Decimal(str(hours_raw))
                if hours_raw not in (None, "")
                else Decimal(str(item.hours_per_occurrence_per_staff))
            )
        except InvalidOperation:
            result.rows.append(ImportRowResult(row_no, "ERROR", "Assigned Hours is not a number."))
            continue
        if not (Decimal("0") < hours <= Decimal("24")):
            result.rows.append(
                ImportRowResult(row_no, "ERROR", "Assigned Hours must be above 0 and at most 24.")
            )
            continue

        key = (emp.id, item.id, work_date)
        if key in seen:
            result.rows.append(ImportRowResult(row_no, "ERROR", "Repeated in this file."))
            continue
        seen.add(key)
        exists = (
            await session.execute(
                select(ScheduledWork.id).where(
                    ScheduledWork.employee_id == emp.id,
                    ScheduledWork.job_item_id == item.id,
                    ScheduledWork.work_date == work_date,
                    ScheduledWork.status == "ACTIVE",
                )
            )
        ).first()
        if exists:
            result.rows.append(ImportRowResult(row_no, "EXISTS", "Already assigned; left as is."))
            continue

        try:
            report = await service.validate_scheduled_work_request(
                ScheduledWorkValidateRequest(
                    employee_id=emp.id,
                    job_item_id=item.id,
                    work_date=work_date,
                    assigned_hours=hours,
                ),
                is_admin=user.role == "ADMIN",
            )
        except AppError as exc:
            result.rows.append(ImportRowResult(row_no, "ERROR", str(exc.detail)))
            continue
        warnings = [w.message for w in report.warnings]
        if not report.is_valid:
            result.rows.append(
                ImportRowResult(
                    row_no, "ERROR", "; ".join(e.message for e in report.errors), warnings
                )
            )
            continue
        if dry_run:
            result.rows.append(ImportRowResult(row_no, "WOULD_CREATE", "", warnings))
            continue
        await service.create_operational_shift(
            OperationalShiftCreate(
                job_item_id=item.id,
                work_date=work_date,
                employee_id=emp.id,
                assigned_hours=hours,
                override_reason="Imported",
                source="DIRECT",
                acknowledge_warnings=True,
            ),
            current_user_id=user.id,
        )
        result.rows.append(ImportRowResult(row_no, "CREATED", "", warnings))
    return result
