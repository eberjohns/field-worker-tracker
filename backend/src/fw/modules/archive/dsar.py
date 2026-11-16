"""Employee Subject Access Request (DSAR) multi-sheet Excel generator.

Implements data-subject rights per UAE PDPL, Saudi PDPL, and docs/14-nonfunctional.md.
Generates a complete, structured, multi-sheet Excel workbook of an employee's personal data.
"""

import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import xlsxwriter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.attendance import AttendanceRecord
from fw.modules.org import Employee, EmployeeDocument
from fw.modules.payroll import PayrollRecord, PayrollRun
from fw.modules.sync import ConsentRecord


def _write_sheet(
    workbook: xlsxwriter.Workbook,
    sheet_name: str,
    headers: list[str],
    rows: list[list[Any]],
) -> None:
    """Helper to format and write a structured data sheet."""
    sheet = workbook.add_worksheet(sheet_name[:31])
    hdr_format = workbook.add_format(
        {"bold": True, "bg_color": "#1E293B", "font_color": "#FFFFFF", "border": 1}
    )
    cell_format = workbook.add_format({"border": 1})
    date_format = workbook.add_format({"num_format": "yyyy-mm-dd", "border": 1})
    dt_format = workbook.add_format({"num_format": "yyyy-mm-dd hh:mm:ss", "border": 1})
    num_format = workbook.add_format({"num_format": "#,##0.00", "border": 1})

    for col_idx, h in enumerate(headers):
        sheet.write(0, col_idx, h, hdr_format)
        sheet.set_column(col_idx, col_idx, max(len(h) + 4, 15))

    for row_idx, r in enumerate(rows, start=1):
        for col_idx, val in enumerate(r):
            if isinstance(val, datetime):
                sheet.write_datetime(row_idx, col_idx, val.replace(tzinfo=None), dt_format)
            elif isinstance(val, date):
                sheet.write_datetime(
                    row_idx, col_idx, datetime(val.year, val.month, val.day), date_format
                )
            elif isinstance(val, (int, float, Decimal)):
                sheet.write_number(row_idx, col_idx, float(val), num_format)
            else:
                sheet.write_string(row_idx, col_idx, str(val) if val is not None else "", cell_format)


async def generate_employee_dsar_excel(session: AsyncSession, employee_id: UUID) -> bytes:
    """Generate multi-sheet Excel DSAR file for an employee."""
    emp = await session.get(Employee, employee_id)
    if not emp:
        raise ValueError(f"Employee {employee_id} not found.")

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})

    # 1. Profile Sheet
    profile_headers = ["Field", "Value"]
    profile_rows = [
        ["Worker ID (Tally ID)", emp.tally_id],
        ["Full Name", emp.name],
        ["Role", emp.role],
        ["Country", emp.country],
        ["Phone Number", emp.phone or "None"],
        ["Email Address", emp.email or "None"],
        ["Staff Grade Description", emp.staff_grade_description or "None"],
        ["Grade Code", emp.grade_code or "None"],
        ["Weekly Off Day", emp.weekly_off_day or "Company Default"],
        ["Join Date", emp.join_date or "None"],
        ["Employment End Date", emp.employment_end_date or "Active"],
        ["Consent Status", emp.consent_status],
        ["Consent Withdrawn At", emp.consent_withdrawn_at or "N/A"],
        ["Account Active", "Yes" if emp.is_active else "No"],
        ["Anonymised At", emp.anonymised_at or "N/A"],
    ]
    _write_sheet(workbook, "Worker Profile", profile_headers, profile_rows)

    # 2. Consent History Sheet
    c_stmt = (
        select(ConsentRecord)
        .where(ConsentRecord.employee_id == employee_id)
        .order_by(ConsentRecord.recorded_at.asc())
    )
    c_records = (await session.execute(c_stmt)).scalars().all()
    consent_headers = ["Policy Version", "Consented At", "Status", "Withdrawn At", "Reason", "Recorded At"]
    consent_rows = [
        [
            c.policy_version,
            c.consented_at,
            c.status,
            c.withdrawn_at or "N/A",
            c.withdrawal_reason or "N/A",
            c.recorded_at,
        ]
        for c in c_records
    ]
    _write_sheet(workbook, "Consent History", consent_headers, consent_rows)

    # 3. Documents Sheet
    d_stmt = select(EmployeeDocument).where(EmployeeDocument.employee_id == employee_id)
    doc_records = (await session.execute(d_stmt)).scalars().all()
    doc_headers = ["Document Type", "Start Date", "Expiry Date", "Active"]
    doc_rows = [
        [d.document_type, d.start_date or "N/A", d.expiry_date, "Yes" if d.is_active else "No"]
        for d in doc_records
    ]
    _write_sheet(workbook, "Document Records", doc_headers, doc_rows)

    # 4. Attendance History Sheet
    att_stmt = (
        select(AttendanceRecord)
        .where(AttendanceRecord.employee_id == employee_id)
        .order_by(AttendanceRecord.work_date.desc())
    )
    att_records = (await session.execute(att_stmt)).scalars().all()
    att_headers = [
        "Work Date",
        "Status",
        "Standard Hours",
        "Actual Work (min)",
        "Break (min)",
        "OT1 (min)",
        "OT2 (min)",
        "Variation (min)",
    ]
    att_rows = [
        [
            a.work_date,
            a.status,
            float(a.standard_hours) if a.standard_hours else 0.0,
            a.actual_work_minutes,
            a.break_minutes,
            a.ot1_minutes,
            a.ot2_minutes,
            a.variation_minutes,
        ]
        for a in att_records
    ]
    _write_sheet(workbook, "Attendance Summary", att_headers, att_rows)

    # 5. Payroll History Sheet
    pay_stmt = (
        select(PayrollRecord, PayrollRun)
        .join(PayrollRun, PayrollRecord.payroll_run_id == PayrollRun.id)
        .where(PayrollRecord.employee_id == employee_id)
        .order_by(PayrollRun.period_start.desc())
    )
    pay_results = (await session.execute(pay_stmt)).all()
    pay_headers = [
        "Period Start",
        "Period End",
        "Standard Hours",
        "Worked Hours",
        "Gross Pay",
        "OT1 Pay",
        "OT2 Pay",
        "Deductions",
        "Net Pay",
    ]
    pay_rows = [
        [
            r.period_start,
            r.period_end,
            float(p.standard_hours) if p.standard_hours else 0.0,
            float(p.worked_hours) if p.worked_hours else 0.0,
            float(p.gross_pay) if p.gross_pay else 0.0,
            float(p.ot1_amount) if p.ot1_amount else 0.0,
            float(p.ot2_amount) if p.ot2_amount else 0.0,
            float(p.missed_hours_deduction) if p.missed_hours_deduction else 0.0,
            float(p.net_pay) if p.net_pay else 0.0,
        ]
        for p, r in pay_results
    ]
    _write_sheet(workbook, "Payroll Slips", pay_headers, pay_rows)

    workbook.close()
    return output.getvalue()
