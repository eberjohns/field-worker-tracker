"""Public interface for managed lists (DEC-60, ADR-030): staff types and grade codes.

Owns ``lookup_values``. Staff types are kept by Admin in Settings; the grade list is kept by payroll
from active salary revisions (``LookupService.sync_grades``). The HTTP routes are in
``fw.api.lookups`` because Settings also shows values in use from higher modules.
"""

from fw.modules.lookups.models import LookupValue
from fw.modules.lookups.schemas import (
    LookupValueCreate,
    LookupValueRead,
    LookupValueUpdate,
)
from fw.modules.lookups.service import LookupService

__all__ = [
    "LookupService",
    "LookupValue",
    "LookupValueCreate",
    "LookupValueRead",
    "LookupValueUpdate",
]
