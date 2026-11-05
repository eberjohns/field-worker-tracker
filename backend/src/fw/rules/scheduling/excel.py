"""Pure Excel roster generator matching the client's weekly schedule sheet layout."""

import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


@dataclass(frozen=True)
class ExcelRosterDayCell:
    """Cell representation for a worker on one day of the week."""

    work_date: date
    display_text: str  # e.g. "12A14301 A (9.0h)" or "WEEKLY-OFF" or "SKIPPED"
    hours: Decimal
    is_marker: bool


@dataclass(frozen=True)
class ExcelRosterWorkerRow:
    """Row representation for one worker in the weekly roster."""

    employee_name: str
    tally_id: str
    grade_code: str
    staff_grade_description: str
    standard_hours: Decimal
    daily_cells: list[ExcelRosterDayCell]  # 7 days Mon-Sun
    total_allocated_hours: Decimal
    total_standard_hours: Decimal
    remarks: str = ""


def build_roster_excel_bytes(
    week_start: date,
    worker_rows: list[ExcelRosterWorkerRow],
    week_title: str | None = None,
) -> bytes:
    """Build an openpyxl Excel workbook in the client's weekly schedule layout and return bytes."""
    wb = openpyxl.Workbook()
    active_sheet = wb.active
    assert active_sheet is not None
    ws: Worksheet = active_sheet
    ws.title = "Weekly Roster"

    # Header fonts and fills
    title_font = Font(name="Calibri", size=14, bold=True)
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    regular_font = Font(name="Calibri", size=10)
    bold_font = Font(name="Calibri", size=10, bold=True)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center")

    # Title block
    title_text = week_title or f"Weekly Roster - Week starting {week_start.isoformat()}"
    ws.merge_cells("A1:M1")
    ws["A1"] = title_text
    ws["A1"].font = title_font
    ws["A1"].alignment = left_align
    ws.row_dimensions[1].height = 28

    # Table column headers
    headers = [
        "Worker Name",
        "Tally ID",
        "Grade",
        "Staff Type",
        "Std H",
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun",
        "Hours",
        "Remarks",
    ]

    # Row 3 for headers
    ws.row_dimensions[3].height = 24
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=3, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Add worker rows
    current_row = 4
    for worker in worker_rows:
        ws.row_dimensions[current_row].height = 22

        # Fixed columns
        ws.cell(row=current_row, column=1, value=worker.employee_name).font = bold_font
        ws.cell(row=current_row, column=2, value=worker.tally_id).alignment = center_align
        ws.cell(row=current_row, column=3, value=worker.grade_code or "").alignment = center_align
        ws.cell(row=current_row, column=4, value=worker.staff_grade_description or "")
        ws.cell(row=current_row, column=5, value=float(worker.standard_hours)).alignment = (
            center_align
        )

        # 7 Day columns (Mon=6 .. Sun=12)
        for day_idx in range(7):
            col_num = 6 + day_idx
            if day_idx < len(worker.daily_cells):
                d_cell = worker.daily_cells[day_idx]
                cell_val = d_cell.display_text
            else:
                cell_val = "FREE"

            c = ws.cell(row=current_row, column=col_num, value=cell_val)
            c.font = regular_font
            c.alignment = center_align

        # Total hours column
        hours_str = f"{worker.total_allocated_hours:.1f} / {worker.total_standard_hours:.1f}"
        h_cell = ws.cell(row=current_row, column=13, value=hours_str)
        h_cell.font = bold_font
        h_cell.alignment = center_align

        # Remarks column
        ws.cell(row=current_row, column=14, value=worker.remarks).font = regular_font

        current_row += 1

    # Adjust column widths
    column_widths: dict[int, int] = {
        1: 22,  # Name
        2: 12,  # Tally ID
        3: 10,  # Grade
        4: 20,  # Staff Type
        5: 8,  # Std H
        6: 18,  # Mon
        7: 18,  # Tue
        8: 18,  # Wed
        9: 18,  # Thu
        10: 18,  # Fri
        11: 18,  # Sat
        12: 18,  # Sun
        13: 14,  # Hours
        14: 20,  # Remarks
    }
    for col_idx, width in column_widths.items():
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
