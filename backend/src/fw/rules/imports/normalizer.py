"""Pure normalization rules for bulk imports.

Per docs/11-import-pipeline.md:
- Trim whitespace, collapse internal spaces, normalize non-breaking spaces.
- Grade code normalization: G5-C, G5C, G5C26 -> G5C (base code with year suffix stripped).
- SGD normalization: SGD_Aliases lookup, SGD_ALIAS_APPLIED (info), SGD_UNKNOWN (warning).
- Cell rules: blank keeps, `_` clears (CLEAR_ON_REQUIRED on required fields).
"""

import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from fw.rules.payroll.salary import round_money

CONTROLLED_SGDS = {
    "Gardener Helper",
    "Gardener Expert",
    "Gardener - Hand Watering",
    "Team Leader",
    "Supervisor",
    "Superintendent",
    "Irrigation Technician",
    "Palm Tree Technician",
    "Foreman With DL",
    "Foreman Without DL",
    "Admin",
    "Irrigation Engineer",
    "Landscaping Engineer",
    "Commercial - QS",
    "HSE Engineer",
    "Project Manager",
}

SGD_ALIASES: dict[str, str] = {
    "gardner helper": "Gardener Helper",
    "gardner expert": "Gardener Expert",
    "gardeners - hand watering": "Gardener - Hand Watering",
    "irrigation technitian": "Irrigation Technician",
    "palm tree techn": "Palm Tree Technician",
    "forman with dl": "Foreman With DL",
    "forman without dl": "Foreman Without DL",
    "superintent": "Superintendent",
}


def normalize_text(val: Any) -> str | None:
    """Normalize text: strip, collapse whitespace, replace non-breaking spaces."""
    if val is None:
        return None
    s = str(val).replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s if s != "" else None


def normalize_grade_code(raw: str | None) -> str | None:
    """Normalize grade code by removing hyphens and stripping trailing 2-digit year suffix.

    Examples:
    'G5-C' -> 'G5C'
    'G5C26' -> 'G5C'
    'G2B26' -> 'G2B'
    'G1C' -> 'G1C'
    """
    cleaned = normalize_text(raw)
    if not cleaned:
        return None
    s = cleaned.replace("-", "").upper()
    # If ends with 2 digits (e.g. 26 for year 2026), strip the year suffix
    match = re.match(r"^(G\d+[A-Z])(\d{2})$", s)
    if match:
        return match.group(1)
    return s


def normalize_sgd(raw: str | None) -> tuple[str | None, str | None]:
    """Normalize Staff Grade Description.

    Returns:
    - (normalized_value, None) if exact match with controlled list
    - (aliased_value, "SGD_ALIAS_APPLIED") if alias was resolved
    - (original_value, "SGD_UNKNOWN") if unknown value (allowed but flagged with warning)
    - (None, None) if raw is empty
    """
    cleaned = normalize_text(raw)
    if not cleaned:
        return (None, None)

    # Check exact match in controlled list
    for standard in CONTROLLED_SGDS:
        if standard.lower() == cleaned.lower():
            return (standard, None)

    # Check alias
    lower_val = cleaned.lower()
    if lower_val in SGD_ALIASES:
        return (SGD_ALIASES[lower_val], "SGD_ALIAS_APPLIED")

    # Unknown
    return (cleaned, "SGD_UNKNOWN")


def parse_cell_value(
    raw_val: Any,
    col_type: str,
    is_required: bool,
    enum_values: list[str] | set[str] | None = None,
) -> tuple[Any, str, str | None]:
    """Parse raw cell value according to type and cell rules.

    Returns (parsed_value, cell_action, error_code)
    cell_action:
      - 'KEEP': blank cell, keep existing value
      - 'CLEAR': `_` in cell, clear optional value
      - 'SET': new parsed value to write
    error_code:
      - None if valid
      - Stable error code (e.g. 'CLEAR_ON_REQUIRED', 'INVALID_TYPE', 'INVALID_ENUM', etc.)
    """
    # 1. Blank cell check -> KEEP
    if raw_val is None:
        return (None, "KEEP", None)

    if isinstance(raw_val, str):
        trimmed = raw_val.strip()
        if trimmed == "":
            return (None, "KEEP", None)
        # 2. Underscore check -> CLEAR
        if trimmed == "_":
            if is_required:
                return (None, "CLEAR", "CLEAR_ON_REQUIRED")
            return (None, "CLEAR", None)

    # 3. Value needs parsing / setting
    if col_type == "text":
        txt = normalize_text(raw_val)
        if enum_values and txt is not None:
            # Case-insensitive enum check
            enum_map = {e.lower(): e for e in enum_values}
            if txt.lower() in enum_map:
                return (enum_map[txt.lower()], "SET", None)
            return (txt, "SET", "INVALID_ENUM")
        return (txt, "SET", None)

    elif col_type == "bool":
        if isinstance(raw_val, bool):
            return (raw_val, "SET", None)
        txt = normalize_text(raw_val)
        if txt is None:
            return (None, "KEEP", None)
        upper = txt.upper()
        if upper in ("Y", "YES", "TRUE", "1"):
            return (True, "SET", None)
        elif upper in ("N", "NO", "FALSE", "0"):
            return (False, "SET", None)
        return (None, "SET", "INVALID_TYPE")

    elif col_type == "date":
        if isinstance(raw_val, datetime):
            return (raw_val.date(), "SET", None)
        if isinstance(raw_val, date):
            return (raw_val, "SET", None)
        txt = normalize_text(raw_val)
        if txt is None:
            return (None, "KEEP", None)
        try:
            parsed_dt = datetime.strptime(txt, "%Y-%m-%d").date()
            return (parsed_dt, "SET", None)
        except ValueError:
            return (None, "SET", "INVALID_DATE")

    elif col_type == "time":
        if isinstance(raw_val, time):
            return (raw_val, "SET", None)
        if isinstance(raw_val, datetime):
            return (raw_val.time(), "SET", None)
        txt = normalize_text(raw_val)
        if txt is None:
            return (None, "KEEP", None)
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                t = datetime.strptime(txt, fmt).time()
                return (t, "SET", None)
            except ValueError:
                pass
        return (None, "SET", "INVALID_TYPE")

    elif col_type == "decimal":
        try:
            # Handles integers, floats, string numbers
            d = Decimal(str(raw_val).strip())
            rounded = round_money(d)
            if rounded < 0:
                return (rounded, "SET", "NEGATIVE_VALUE")
            return (rounded, "SET", None)
        except (InvalidOperation, ValueError):
            return (None, "SET", "INVALID_TYPE")

    elif col_type == "int":
        try:
            i = int(Decimal(str(raw_val).strip()))
            return (i, "SET", None)
        except (InvalidOperation, ValueError):
            return (None, "SET", "INVALID_TYPE")

    elif col_type == "json":
        # Can be dict, list, number, boolean, or string
        return (raw_val, "SET", None)

    return (raw_val, "SET", None)
