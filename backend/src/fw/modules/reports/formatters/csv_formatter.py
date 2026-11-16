"""CSV report formatter."""

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fw.modules.reports.schemas import ReportColumn


def generate_csv_report(
    columns: list[ReportColumn],
    rows: list[dict[str, Any]],
) -> bytes:
    """Generate RFC 4180 compliant CSV bytes."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header
    writer.writerow([col.label for col in columns])

    # Rows
    for row in rows:
        row_vals = []
        for col in columns:
            val = row.get(col.key)
            if val is None:
                row_vals.append("")
            elif isinstance(val, (datetime, date)):
                row_vals.append(val.isoformat())
            elif isinstance(val, (Decimal, float)):
                row_vals.append(f"{val:.2f}")
            else:
                row_vals.append(str(val))
        writer.writerow(row_vals)

    return output.getvalue().encode("utf-8")
