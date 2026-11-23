"""Grade codes (DEC-58): one stored form everywhere, the base code (e.g. ``G3C``, ``G16A``, ``G25``).

Only suffixes that can be recognised for certain are removed:

- a revision year, ``-YYYY``            (``G3C-2026`` -> ``G3C``)
- a revision code, ``-R<n>``            (``G3C-R2``   -> ``G3C``)
- a hyphen inside the code              (``G5-C``     -> ``G5C``)

Anything else (for example ``G3C26``, ``G3CR2``, ``3C``) is rejected with ``INVALID_GRADE_CODE``
instead of being guessed at. Pure function: no I/O.
"""

import re

INVALID_GRADE_CODE = "INVALID_GRADE_CODE"

_GRADE_RE = re.compile(r"^(G\d{1,2})-?([A-Z]?)(?:-(?:\d{4}|R\d{1,3}))?$")
_BASE_RE = re.compile(r"^G\d{1,2}[A-Z]?$")


class InvalidGradeCodeError(ValueError):
    """Raised when a grade code cannot be parsed into a base code."""

    code = INVALID_GRADE_CODE

    def __init__(self, raw: str) -> None:
        self.raw = raw
        super().__init__(
            f"Invalid grade code '{raw}'. Expected a base code like G3C or G16A, "
            "optionally with a '-YYYY' or '-R<n>' revision suffix."
        )


def base_grade_code(raw: str) -> str:
    """Return the base grade code for ``raw`` or raise ``InvalidGradeCodeError``."""
    cleaned = (raw or "").strip().upper()
    match = _GRADE_RE.match(cleaned)
    if not match:
        raise InvalidGradeCodeError(raw)
    return match.group(1) + match.group(2)


def try_base_grade_code(raw: str | None) -> str | None:
    """Like ``base_grade_code`` but returns None for blank or unparseable input."""
    if raw is None or not str(raw).strip():
        return None
    try:
        return base_grade_code(str(raw))
    except InvalidGradeCodeError:
        return None


def is_base_grade_code(value: str) -> bool:
    """True when ``value`` is already in stored (base) form."""
    return bool(_BASE_RE.match(value or ""))


def display_grade_code(base: str, suffix_label: str | None) -> str:
    """Display form for a revision line, e.g. ``G3C`` + ``2026`` -> ``G3C-2026``."""
    return f"{base}-{suffix_label}" if suffix_label else base


def grade_sort_key(code: str) -> tuple[int, str]:
    """Natural order: G1A < G2A < G10A < G25."""
    m = re.match(r"^G(\d+)([A-Z]?)$", code or "")
    if not m:
        return (10_000, code or "")
    return (int(m.group(1)), m.group(2))
