"""Public interface for managed lists (DEC-60, ADR-030): staff types and grade codes.

Owns ``lookup_values``. The HTTP routes are in ``fw.api.lookups`` because the list endpoint also
shows values in use from higher modules (employees, job items, revision lines).
"""

from fw.modules.lookups.models import LookupValue
from fw.modules.lookups.schemas import (
    LookupValueCreate,
    LookupValueCreated,
    LookupValueRead,
    LookupValueUpdate,
    LookupWarning,
)
from fw.modules.lookups.service import LookupService

__all__ = [
    "LookupService",
    "LookupValue",
    "LookupValueCreate",
    "LookupValueCreated",
    "LookupValueRead",
    "LookupValueUpdate",
    "LookupWarning",
]
