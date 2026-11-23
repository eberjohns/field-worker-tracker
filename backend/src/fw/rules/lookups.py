"""Managed lists (DEC-60): staff types (``staff_grade_description``) and grade codes.

Staff types are added and deactivated by Admin in Settings > Managed Lists, never deleted. Grade
codes are the base codes with a line in an ACTIVE salary revision: payroll keeps that list, nobody
adds a grade any other way (owner decision 23 Nov 2026). This module holds the pure parts: how a
value is cleaned, when two values are the same, near-match hints and the seed list. Pure: no I/O.
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
GRADE_FROM_REVISION_ONLY = "GRADE_FROM_REVISION_ONLY"

# lookup_values.source: SEED (migration / reset), SCREEN (Settings), REVISION (grade list kept by
# payroll from active salary revisions), IMPORT (grades added by an import before 23 Nov 2026).
SOURCE_SEED = "SEED"
SOURCE_SCREEN = "SCREEN"
SOURCE_REVISION = "REVISION"

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


def close_names(value: str, existing: Iterable[str], exclude_equal: bool = True) -> list[str]:
    """Up to three existing names spelled almost like ``value`` (ignoring case and spaces)."""
    by_key = {value_key(v): v for v in existing}
    key = value_key(value)
    return [
        by_key[k]
        for k in difflib.get_close_matches(key, list(by_key), n=3, cutoff=NEAR_MATCH_CUTOFF)
        if not (exclude_equal and k == key)
    ]


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
    for hit in close_names(value, pool):
        if hit not in hints:
            hints.append(hit)
    return hints


def sort_values(list_key: str, values: Iterable[str]) -> list[str]:
    """Grades in natural order (G1A < G2A < G10A); staff types alphabetically."""
    if list_key == GRADE_CODE:
        return sorted(values, key=grade_sort_key)
    return sorted(values, key=str.lower)


def did_you_mean(hints: list[str]) -> str:
    return f" Did you mean {hints[0]}?" if hints else ""
