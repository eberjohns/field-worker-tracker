"""PDF report generator producing standard PDF 1.4 documents without external C-libraries."""

import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fw.modules.reports.schemas import ReportColumn


def escape_pdf_text(text: str) -> str:
    """Escape parentheses and backslashes for PDF string literals."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def generate_pdf_report(
    columns: list[ReportColumn],
    rows: list[dict[str, Any]],
    title: str = "Report",
    filters: dict[str, Any] | None = None,
) -> bytes:
    """Generate a clean printable PDF (PDF 1.4) in landscape/portrait table layout."""
    # We will use landscape: 792 x 612 pt (US Letter landscape)
    page_width = 792
    page_height = 612
    margin_left = 36
    margin_top = 40
    line_height = 14
    rows_per_page = 30

    # Pick up to 8 primary columns if table is too wide
    display_cols = columns[:8] if len(columns) > 8 else columns
    col_width = (page_width - 2 * margin_left) / max(len(display_cols), 1)

    # Chunk rows into pages
    chunked_rows = [rows[i : i + rows_per_page] for i in range(0, max(len(rows), 1), rows_per_page)]
    if not chunked_rows:
        chunked_rows = [[]]

    total_pages = len(chunked_rows)
    page_contents: list[str] = []

    for page_idx, page_rows in enumerate(chunked_rows, start=1):
        commands: list[str] = []
        # Title and header banner
        commands.append("BT")
        commands.append("/F1 14 Tf")
        commands.append(f"1 0 0 1 {margin_left} {page_height - margin_top} Tm")
        commands.append(f"({escape_pdf_text(title)}) Tj")
        commands.append("ET")

        # Subtitle / Page info
        commands.append("BT")
        commands.append("/F1 8 Tf")
        commands.append(f"1 0 0 1 {page_width - margin_left - 100} {page_height - margin_top} Tm")
        commands.append(f"(Page {page_idx} of {total_pages}) Tj")
        commands.append("ET")

        # Filter info on page 1
        curr_y = page_height - margin_top - 20
        if page_idx == 1 and filters:
            filter_str = ", ".join(f"{k}={v}" for k, v in filters.items() if v is not None)[:120]
            if filter_str:
                commands.append("BT")
                commands.append("/F1 8 Tf")
                commands.append(f"1 0 0 1 {margin_left} {curr_y} Tm")
                commands.append(f"(Filters: {escape_pdf_text(filter_str)}) Tj")
                commands.append("ET")
                curr_y -= 14

        # Table Header Background Bar
        commands.append("0.12 0.16 0.24 rg")  # Dark blue-gray
        commands.append(f"{margin_left} {curr_y - 4} {page_width - 2 * margin_left} 16 re f")

        # Table Header Text
        commands.append("1 1 1 rg")  # White
        commands.append("BT")
        commands.append("/F1 8 Tf")
        for c_idx, col in enumerate(display_cols):
            x = margin_left + c_idx * col_width + 4
            commands.append(f"1 0 0 1 {x} {curr_y} Tm")
            commands.append(f"({escape_pdf_text(col.label[:18])}) Tj")
        commands.append("ET")
        curr_y -= line_height + 4

        # Table Data Rows
        for r_idx, row in enumerate(page_rows):
            # Alternating row background
            if r_idx % 2 == 1:
                commands.append("0.96 0.97 0.98 rg")  # Light gray
                commands.append(
                    f"{margin_left} {curr_y - 2} {page_width - 2 * margin_left} {line_height} re f"
                )

            commands.append("0.1 0.1 0.1 rg")  # Text color
            commands.append("BT")
            commands.append("/F1 8 Tf")
            for c_idx, col in enumerate(display_cols):
                val = row.get(col.key)
                val_str = ""
                if val is not None:
                    if isinstance(val, (datetime, date)):
                        val_str = val.isoformat()
                    elif isinstance(val, (Decimal, float)):
                        val_str = f"{val:.2f}"
                    else:
                        val_str = str(val)
                x = margin_left + c_idx * col_width + 4
                commands.append(f"1 0 0 1 {x} {curr_y} Tm")
                commands.append(f"({escape_pdf_text(val_str[:22])}) Tj")
            commands.append("ET")
            curr_y -= line_height

        page_contents.append("\n".join(commands))

    # Assemble PDF Objects
    # 1: Catalog, 2: Pages, 3.. (Page & Content)
    objects: list[bytes] = []

    # Obj 1: Catalog
    catalog_obj = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    objects.append(catalog_obj)

    # We need object numbers:
    # Obj 2: Pages (kids: 3, 5, 7, ...; contents: 4, 6, 8, ...)
    page_obj_ids = [3 + i * 2 for i in range(total_pages)]
    kids_refs = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    pages_obj = (
        f"2 0 obj\n<< /Type /Pages /Kids [{kids_refs}] /Count {total_pages} >>\nendobj\n".encode(
            "latin1"
        )
    )
    objects.append(pages_obj)

    # For each page, add Page object and Content stream object
    for i in range(total_pages):
        page_id = 3 + i * 2
        content_id = page_id + 1
        stream_bytes = page_contents[i].encode("latin1")
        stream_len = len(stream_bytes)

        page_dict = (
            f"{page_id} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
        ).encode("latin1")
        objects.append(page_dict)

        content_dict = (
            f"{content_id} 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("latin1")
            + stream_bytes
            + b"\nendstream\nendobj\n"
        )
        objects.append(content_dict)

    # Build xref table
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]  # Object 0 is free
    for obj in objects:
        offsets.append(out.tell())
        out.write(obj)

    xref_offset = out.tell()
    num_objects = len(objects) + 1
    out.write(f"xref\n0 {num_objects}\n".encode("latin1"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("latin1"))

    out.write(
        f"trailer\n<< /Size {num_objects} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "latin1"
        )
    )
    return out.getvalue()
