"""Excel report generator satisfying Rule 12 from docs/12-reports.md:

- Every report exports to Excel (XLSX).
- One header row, one row per record, no merged cells.
- ISO dates, numbers as numbers.
- Second sheet 'Filters' recording the parameters used.
"""

import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import xlsxwriter

from fw.modules.reports.schemas import ReportColumn


def generate_excel_report(
    columns: list[ReportColumn],
    rows: list[dict[str, Any]],
    filters: dict[str, Any],
    title: str = "Report",
) -> bytes:
    """Generate Excel XLSX bytes with primary data sheet and secondary Filters sheet."""
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})

    # Formats
    header_format = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#1E293B",
            "font_color": "#FFFFFF",
            "border": 1,
            "text_wrap": False,
        }
    )
    filter_header_format = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#334155",
            "font_color": "#FFFFFF",
            "border": 1,
        }
    )
    border_format = workbook.add_format({"border": 1})
    num_format = workbook.add_format({"num_format": "#,##0.00", "border": 1})
    int_format = workbook.add_format({"num_format": "#,##0", "border": 1})
    date_format = workbook.add_format({"num_format": "yyyy-mm-dd", "border": 1})
    datetime_format = workbook.add_format({"num_format": "yyyy-mm-dd hh:mm:ss", "border": 1})

    # Sheet 1: Data
    sanitized_sheet_name = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_"))[:31]
    data_sheet = workbook.add_worksheet(sanitized_sheet_name or "Data")

    # Header Row
    for col_idx, col in enumerate(columns):
        data_sheet.write(0, col_idx, col.label, header_format)
        # Default column width
        data_sheet.set_column(col_idx, col_idx, max(len(col.label) + 4, 14))

    # Data Rows
    for row_idx, row in enumerate(rows, start=1):
        for col_idx, col in enumerate(columns):
            val = row.get(col.key)
            if val is None:
                data_sheet.write_blank(row_idx, col_idx, None, border_format)
            elif isinstance(val, (int, float, Decimal)):
                if col.type == "money" or isinstance(val, (float, Decimal)):
                    data_sheet.write_number(row_idx, col_idx, float(val), num_format)
                else:
                    data_sheet.write_number(row_idx, col_idx, int(val), int_format)
            elif isinstance(val, datetime):
                # ISO formatted string or native excel date
                data_sheet.write_string(
                    row_idx, col_idx, val.strftime("%Y-%m-%d %H:%M:%S"), datetime_format
                )
            elif isinstance(val, date):
                data_sheet.write_string(row_idx, col_idx, val.strftime("%Y-%m-%d"), date_format)
            elif isinstance(val, bool):
                data_sheet.write_boolean(row_idx, col_idx, val, border_format)
            else:
                data_sheet.write_string(row_idx, col_idx, str(val), border_format)

    # Sheet 2: Filters
    filter_sheet = workbook.add_worksheet("Filters")
    filter_sheet.write(0, 0, "Parameter", filter_header_format)
    filter_sheet.write(0, 1, "Applied Value", filter_header_format)
    filter_sheet.set_column(0, 0, 24)
    filter_sheet.set_column(1, 1, 40)

    f_row = 1
    for param_key, param_val in filters.items():
        if param_val is not None:
            filter_sheet.write(f_row, 0, str(param_key), border_format)
            filter_sheet.write(f_row, 1, str(param_val), border_format)
            f_row += 1

    workbook.close()
    return output.getvalue()
