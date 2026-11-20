"""Pure access-scope rules for worksite-based visibility (DEC-57, DEC-10).

Who may see an employee depends on why they are looking (the purpose) and on two facts:
- ``in_crew``: the employee is in the viewer's reporting subtree (DEC-10 crew chain).
- ``on_my_sites``: the employee works on one of the viewer's worksites. For the
  OPERATIONS purpose this means "scheduled there on that work date" (site-day).

Approvals and edits always follow the crew chain (DEC-10). Visibility through a worksite
is read-only (view and comment). No database or framework imports here.
"""

from enum import StrEnum


class ScopePurpose(StrEnum):
    """Why a list or record is being viewed."""

    DIRECTORY = "DIRECTORY"  # Employees list and profile
    REQUESTS = "REQUESTS"  # Leave and reassignment requests
    OPERATIONS = "OPERATIONS"  # Attendance, live map, pending visits, reports, dashboard


class AccessLevel(StrEnum):
    """FULL: the viewer's role permissions apply. READ_ONLY: view and comment only."""

    FULL = "FULL"
    READ_ONLY = "READ_ONLY"


SITE_SCOPED_ROLES = frozenset({"SUPERVISOR", "SUPERINTENDENT", "ENGINEER"})


def employee_access(
    role: str,
    purpose: ScopePurpose,
    in_crew: bool,
    on_my_sites: bool,
) -> AccessLevel | None:
    """Return the viewer's access to one employee (or one employee-day), or None if hidden.

    - ADMIN sees everything with full access.
    - WORKER sees only themselves (their own crew set is just themselves).
    - SUPERVISOR: own crew on Employees and Requests; on operational views only the
      employee-days scheduled on their worksites (their crew working elsewhere belongs
      to that site's supervisor).
    - SUPERINTENDENT / ENGINEER: their crew everywhere, plus read-only access to
      non-crew workers on their worksites.
    """
    norm_role = role.strip().upper()
    if norm_role == "ADMIN":
        return AccessLevel.FULL
    if norm_role not in SITE_SCOPED_ROLES:
        return AccessLevel.FULL if in_crew else None

    if norm_role == "SUPERVISOR":
        if purpose == ScopePurpose.OPERATIONS:
            if not on_my_sites:
                return None
            return AccessLevel.FULL if in_crew else AccessLevel.READ_ONLY
        if in_crew:
            return AccessLevel.FULL
        if purpose == ScopePurpose.DIRECTORY and on_my_sites:
            return AccessLevel.READ_ONLY
        return None

    # SUPERINTENDENT / ENGINEER
    if in_crew:
        return AccessLevel.FULL
    if on_my_sites:
        return AccessLevel.READ_ONLY
    return None


def scope_supervisor_ids(
    viewer_employee_id: str,
    role: str,
    crew_ids: set[str],
    roles_by_employee: dict[str, str],
) -> set[str]:
    """Supervisors whose assigned worksites the viewer sees.

    A supervisor sees their own assigned worksites. A superintendent or engineer sees the
    worksites assigned to any supervisor in their reporting scope. Other roles: none.
    """
    norm_role = role.strip().upper()
    if norm_role == "SUPERVISOR":
        return {viewer_employee_id}
    if norm_role in ("SUPERINTENDENT", "ENGINEER"):
        return {
            emp_id
            for emp_id in crew_ids
            if emp_id != viewer_employee_id
            and roles_by_employee.get(emp_id, "").strip().upper() == "SUPERVISOR"
        }
    return set()
