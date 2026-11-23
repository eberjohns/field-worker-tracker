"""Managed lists (DEC-60): staff types (``staff_grade_description``) and grade codes.

Values are added on screen by Admin or Engineer, deactivated by Admin, never deleted. This module
holds the pure parts: how a value is cleaned, when two values are the same, near-match hints and
the seed list. Pure: no I/O.
"""

import difflib
import re
from collections.abc import Iterable

from fw.rules.grades import base_grade_code, grade_sort_key
from fw.rules.imports.normalizer import SGD_ALIASES, normalize_text

STAFF_GRADE_DESCRIPTION = "staff_grade_description"
GRADE_CODE = "grade_code"
LIST_KEYS: tuple[str, ...] = (STAFF_GRADE_DESCRIPTION, GRADE_CODE)

LOOKUP_DUPLICATE = "LOOKUP_DUPLICATE"
LOOKUP_NEAR_MATCH = "LOOKUP_NEAR_MATCH"
LOOKUP_VALUE_INACTIVE = "LOOKUP_VALUE_INACTIVE"
INVALID_STAFF_GRADE_DESCRIPTION = "INVALID_STAFF_GRADE_DESCRIPTION"
UNKNOWN_GRADE_CODE = "UNKNOWN_GRADE_CODE"
NO_REVISION_LINE = "NO_REVISION_LINE"
GRADE_ADDED_TO_LIST = "GRADE_ADDED_TO_LIST"

NEAR_MATCH_CUTOFF = 0.85

# Seed for the staff type list (migration 0024 and "Reset database"). Not a validation list:
# what is allowed is whatever is active in ``lookup_values``.
SEED_STAFF_TYPES: frozenset[str] = frozenset(
    {
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
)


def is_list_key(list_key: str) -> bool:
    return list_key in LIST_KEYS


def clean_value(list_key: str, raw: str | None) -> str | None:
    """Stored form of a value: staff types trimmed with single spaces; grades as base codes.

    Blank -> None. A grade code that cannot be parsed raises ``InvalidGradeCodeError`` (DEC-58).
    """
    cleaned = normalize_text(raw)
    if not cleaned:
        return None
    if list_key == GRADE_CODE:
        return base_grade_code(cleaned)
    return cleaned


def value_key(value: str) -> str:
    """Comparison key: case- and space-insensitive ("Gardener  helper" == "GardenerHelper")."""
    return re.sub(r"\s+", "", (value or "").replace(" ", " ")).lower()


def find_existing(value: str, existing: Iterable[str]) -> str | None:
    """The existing value equal to ``value`` ignoring case and spaces, if any."""
    key = value_key(value)
    for candidate in existing:
        if value_key(candidate) == key:
            return candidate
    return None


def near_matches(list_key: str, value: str, existing: Iterable[str]) -> list[str]:
    """Values the user probably meant: a known alias first, then close spellings.

    Only for staff types: grade codes have a strict format, and close codes (G3B, G3C) are
    different grades.
    """
    if list_key != STAFF_GRADE_DESCRIPTION:
        return []
    pool = list(existing)
    hints: list[str] = []
    alias_target = SGD_ALIASES.get(normalize_text(value.lower()) or "")
    if alias_target:
        hit = find_existing(alias_target, pool)
        if hit:
            hints.append(hit)
    by_key = {value_key(v): v for v in pool}
    for key in difflib.get_close_matches(
        value_key(value), list(by_key), n=3, cutoff=NEAR_MATCH_CUTOFF
    ):
        if by_key[key] not in hints and key != value_key(value):
            hints.append(by_key[key])
    return hints


def sort_values(list_key: str, values: Iterable[str]) -> list[str]:
    """Grades in natural order (G1A < G2A < G10A); staff types alphabetically."""
    if list_key == GRADE_CODE:
        return sorted(values, key=grade_sort_key)
    return sorted(values, key=str.lower)


def did_you_mean(hints: list[str]) -> str:
    return f" Did you mean {hints[0]}?" if hints else ""
