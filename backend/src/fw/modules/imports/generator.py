"""Template generator driven directly by the import registry.

Generates FieldWorkerTracker_Import_Template_v1.0.xlsx matching docs/import-templates/.
"""

import io

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from fw.modules.imports.registry import (
    ALL_SHEET_NAMES,
    CONTROLLED_SGDS,
    SHEET_REGISTRY,
)


def generate_import_template_bytes() -> bytes:
    """Generate the full XLSX import template as bytes."""
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)  # type: ignore

    # Styles
    font_bold = Font(name="Calibri", size=11, bold=True)
    font_title = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
    font_desc = Font(name="Calibri", size=10, italic=True, color="475569")
    font_meta = Font(name="Calibri", size=9, bold=True, color="334155")
    font_regular = Font(name="Calibri", size=11)
    font_example = Font(name="Calibri", size=10, color="64748B")

    fill_header = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    fill_example = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_meta = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    # 1. README Sheet
    ws_readme = wb.create_sheet(title="README")
    ws_readme.views.sheetView[0].showGridLines = True
    ws_readme["A1"] = "Field Worker Tracker - Master Data Import Template (v1.0)"
    ws_readme["A1"].font = font_title
    ws_readme["A2"] = (
        "Fill this workbook to import master data into the Field Worker Tracker. "
        "Review cell rules and guidelines below before uploading."
    )
    ws_readme["A2"].font = font_desc

    readme_rows = [
        ("Important Cell Rules:", ""),
        (
            "1. Blank cell keeps existing value",
            "A blank cell preserves whatever value is currently in the database.",
        ),
        (
            "2. Underscore '_' clears",
            "A cell containing a single underscore '_' clears an optional field (refused on required).",
        ),
        (
            "3. Never deletes",
            "Imports create or update records. Absent rows are NEVER deleted. Deactivation is done on screen.",
        ),
        (
            "4. Column A (#) is ignored",
            "Any row with '#' or 'EXAMPLE' in column A is ignored by the parser.",
        ),
        (
            "5. Headers on row 4",
            "Row 4 contains exact system column names. Do not rename or delete header columns.",
        ),
        ("", ""),
        ("Sheet Order & Scope:", ""),
        ("Groups", "Customer and company account groups (Phase 03)."),
        ("Zones", "Geographic zones (Phase 03)."),
        ("Accommodations", "Staff housing locations (Phase 03)."),
        ("Employees", "Field workers and operations staff (+ document expiries) (Phase 03)."),
        ("Employee_Reporting", "Reporting links: Supervisor, Superintendent, Engineer (Phase 03)."),
        ("Employee_Salary", "Effective-dated worker fixed salary structures (Phase 03)."),
        ("Worksites", "Parent worksites/jobs (Phase 04)."),
        ("Job_Items", "Recurring job staffing items (Phase 04)."),
        ("Leave", "Approved leave records (Phase 06)."),
        ("Public_Holidays", "Country public holidays qualifying for OT2 (Phase 03)."),
        ("Salary_Revisions", "Job budget grade cost revisions (Phase 11)."),
        ("Salary_Revision_Lines", "Job budget grade lines (Phase 11)."),
        ("Company_Settings", "Effective-dated company settings & provisions (Phase 03)."),
        ("Time_Rules", "Planned shift hours and break rules (Phase 03)."),
    ]
    for r_idx, (col1, col2) in enumerate(readme_rows, start=4):
        ws_readme.cell(row=r_idx, column=1, value=col1).font = (
            font_bold
            if ":" in col1
            or col1.startswith("1")
            or col1.startswith("2")
            or col1.startswith("3")
            or col1.startswith("4")
            or col1.startswith("5")
            else font_regular
        )
        ws_readme.cell(row=r_idx, column=2, value=col2).font = font_regular
    ws_readme.column_dimensions["A"].width = 30
    ws_readme.column_dimensions["B"].width = 80

    # 2. Data Sheets
    for sheet_name in ALL_SHEET_NAMES:
        sheet_def = SHEET_REGISTRY[sheet_name]
        ws = wb.create_sheet(title=sheet_name)
        ws.views.sheetView[0].showGridLines = True

        # Row 1: Title
        ws.cell(row=1, column=1, value=sheet_def.name).font = font_title
        # Row 2: Description
        ws.cell(row=2, column=1, value=sheet_def.title).font = font_desc

        # Row 3: Meta rules
        ws.cell(row=3, column=1, value=None)
        for c_idx, col in enumerate(sheet_def.columns, start=2):
            rule_text = f"{col.need_label.lower()} | {col.col_type}"
            cell = ws.cell(row=3, column=c_idx, value=rule_text)
            cell.font = font_meta
            cell.fill = fill_meta
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border

        # Row 4: Headers
        c_hash = ws.cell(row=4, column=1, value="#")
        c_hash.font = font_bold
        c_hash.fill = fill_header
        c_hash.border = thin_border
        c_hash.alignment = Alignment(horizontal="center")

        for c_idx, col in enumerate(sheet_def.columns, start=2):
            c = ws.cell(row=4, column=c_idx, value=col.name)
            c.font = font_bold
            c.fill = fill_header
            c.border = thin_border
            c.alignment = Alignment(horizontal="center")

        # Row 5+: Examples
        for e_idx, ex in enumerate(sheet_def.examples, start=5):
            c_ex = ws.cell(row=e_idx, column=1, value="EXAMPLE")
            c_ex.font = font_example
            c_ex.fill = fill_example
            c_ex.border = thin_border
            c_ex.alignment = Alignment(horizontal="center")

            for c_idx, col in enumerate(sheet_def.columns, start=2):
                val = ex.get(col.name, col.example)
                cell = ws.cell(row=e_idx, column=c_idx, value=val)
                cell.font = font_example
                cell.fill = fill_example
                cell.border = thin_border

        # Adjust column widths
        ws.column_dimensions["A"].width = 12
        for c_idx, col in enumerate(sheet_def.columns, start=2):
            col_letter = get_column_letter(c_idx)
            max_len = max(len(col.name), len(str(col.example or "")))
            ws.column_dimensions[col_letter].width = max(max_len + 4, 16)

    # 3. Lists Sheet
    ws_lists = wb.create_sheet(title="Lists")
    ws_lists.views.sheetView[0].showGridLines = True
    lists_data: dict[str, list[str]] = {
        "role": ["WORKER", "SUPERVISOR", "SUPERINTENDENT", "ENGINEER", "ADMIN"],
        "weekday": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"],
        "yes_no": ["Y", "N"],
        "relationship": ["SUPERVISOR", "SUPERINTENDENT", "ENGINEER"],
        "applies_to": ["ALL", "OUTDOOR_ONLY", "INDOOR_ONLY"],
        "scope_type": ["COMPANY", "TEAM", "DRIVERS", "EMPLOYEE"],
        "country": ["AE", "SA"],
        "customer_type": ["Direct", "Indirect"],
        "frequency_unit": ["WEEK", "MONTH", "QUARTER", "YEAR"],
        "deployment_type": ["PERMANENT", "REMOTE"],
        "leave_type": ["ANNUAL", "SICK", "UNPAID", "EMERGENCY", "OTHER"],
        "revision_status": ["DRAFT", "ACTIVE", "ARCHIVED"],
        "band": ["A", "B", "C"],
        "setting_status": ["GIVEN_BY_CLIENT", "PROPOSED_DEFAULT"],
        "staff_grade_description": sorted(CONTROLLED_SGDS),
    }

    for col_idx, (header, items) in enumerate(lists_data.items(), start=1):
        col_letter = get_column_letter(col_idx)
        cell = ws_lists.cell(row=1, column=col_idx, value=header)
        cell.font = font_bold
        cell.fill = fill_header
        cell.border = thin_border
        for row_idx, val in enumerate(items, start=2):
            c = ws_lists.cell(row=row_idx, column=col_idx, value=val)
            c.font = font_regular
            c.border = thin_border
        ws_lists.column_dimensions[col_letter].width = max(len(header) + 4, 22)

    # 4. SGD_Aliases Sheet
    ws_aliases = wb.create_sheet(title="SGD_Aliases")
    ws_aliases.views.sheetView[0].showGridLines = True
    alias_headers = ["alias_seen_in_your_files", "standard_value", "seen_in"]
    for c_idx, h in enumerate(alias_headers, start=1):
        cell = ws_aliases.cell(row=1, column=c_idx, value=h)
        cell.font = font_bold
        cell.fill = fill_header
        cell.border = thin_border

    alias_rows = [
        ("Gardner Helper", "Gardener Helper", "Hierarchy, Job model"),
        ("Gardner Expert", "Gardener Expert", "Hierarchy"),
        ("Gardeners - Hand watering", "Gardener - Hand Watering", "Job model 2026"),
        ("Irrigation Technitian", "Irrigation Technician", "Job model"),
        ("Palm Tree Techn", "Palm Tree Technician", "Job model (confirm)"),
        ("Forman With DL", "Foreman With DL", "Job model"),
        ("Forman Without DL", "Foreman Without DL", "Job model"),
        ("Superintent", "Superintendent", "Hierarchy"),
    ]
    for r_idx, (a1, a2, a3) in enumerate(alias_rows, start=2):
        ws_aliases.cell(row=r_idx, column=1, value=a1).border = thin_border
        ws_aliases.cell(row=r_idx, column=2, value=a2).border = thin_border
        ws_aliases.cell(row=r_idx, column=3, value=a3).border = thin_border
    ws_aliases.column_dimensions["A"].width = 28
    ws_aliases.column_dimensions["B"].width = 28
    ws_aliases.column_dimensions["C"].width = 25

    # 5. Field_Dictionary Sheet
    ws_dict = wb.create_sheet(title="Field_Dictionary")
    ws_dict.views.sheetView[0].showGridLines = True
    dict_headers = ["sheet", "column", "need", "type", "allowed_values", "description"]
    for c_idx, h in enumerate(dict_headers, start=1):
        cell = ws_dict.cell(row=1, column=c_idx, value=h)
        cell.font = font_bold
        cell.fill = fill_header
        cell.border = thin_border

    dict_r = 2
    for sheet_name in ALL_SHEET_NAMES:
        sheet_def = SHEET_REGISTRY[sheet_name]
        for col in sheet_def.columns:
            allowed = f"list: {col.enum_values}" if col.enum_values else None
            ws_dict.cell(row=dict_r, column=1, value=sheet_name).border = thin_border
            ws_dict.cell(row=dict_r, column=2, value=col.name).border = thin_border
            ws_dict.cell(row=dict_r, column=3, value=col.need_label).border = thin_border
            ws_dict.cell(row=dict_r, column=4, value=col.col_type).border = thin_border
            ws_dict.cell(row=dict_r, column=5, value=allowed).border = thin_border
            ws_dict.cell(row=dict_r, column=6, value=col.description).border = thin_border
            dict_r += 1

    ws_dict.column_dimensions["A"].width = 22
    ws_dict.column_dimensions["B"].width = 28
    ws_dict.column_dimensions["C"].width = 14
    ws_dict.column_dimensions["D"].width = 12
    ws_dict.column_dimensions["E"].width = 30
    ws_dict.column_dimensions["F"].width = 70

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
