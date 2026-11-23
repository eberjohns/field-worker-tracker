"""Groups and zones added on screen (DEC-60 amendment, owner decision 23 Nov 2026).

A new group gets a 3-digit code (the client's codes: 102, 104, 151...). On screen only the name is
entered and the code is generated; an import or API call that gives a code for a new group must
use 3 digits. Zones keep a free-text code. Names are checked like the managed lists: duplicates
ignoring case and spaces are refused, near spellings ask "Did you mean ...?". Pure: no I/O.
"""

import re
from collections.abc import Iterable

INVALID_GROUP_CODE = "INVALID_GROUP_CODE"
DUPLICATE_NAME = "DUPLICATE_NAME"
DUPLICATE_CODE = "DUPLICATE_CODE"
NEAR_MATCH = "NEAR_MATCH"
NO_FREE_GROUP_CODE = "NO_FREE_GROUP_CODE"

_GROUP_CODE_RE = re.compile(r"^\d{3}$")
_FIRST_GENERATED = 100


def is_group_code(code: str | None) -> bool:
    """A group code is exactly 3 digits."""
    return bool(code) and _GROUP_CODE_RE.match(str(code).strip()) is not None


def next_group_code(existing: Iterable[str]) -> str | None:
    """The next free 3-digit code after the highest one in use (151 -> 152).

    Past 999, the lowest free code from 100. None when every code from 100 to 999 is taken.
    Codes that are not 3 digits (older data) are ignored.
    """
    used = {int(c.strip()) for c in existing if is_group_code(c)}
    highest = max(used, default=_FIRST_GENERATED - 1)
    if highest < 999:
        return f"{max(highest + 1, _FIRST_GENERATED):03d}"
    for n in range(_FIRST_GENERATED, 1000):
        if n not in used:
            return f"{n:03d}"
    return None
