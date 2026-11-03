"""Pure hierarchy business rules (BR-EM-05, BR-EM-06, DEC-10).

This module contains pure Python logic with no database, framework, or module dependencies.
"""

from collections import defaultdict, deque
from typing import Literal

ReportingRelationship = Literal["SUPERVISOR", "SUPERINTENDENT", "ENGINEER"]


class HierarchyRuleViolation(Exception):
    """Raised when a hierarchy business rule is violated."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_reporting_link(
    existing_links: list[tuple[str, str, str]],  # (employee_id, manager_id, relationship)
    employee_id: str,
    manager_id: str,
    relationship: str,
) -> None:
    """Validate that adding (employee_id -> manager_id) does not violate hierarchy rules.

    Rules:
    - No self-link (employee_id != manager_id)
    - At most one SUPERVISOR relationship per employee
    - No directed cycle across any reporting relationship (BR-EM-06)
    """
    if employee_id == manager_id:
        raise HierarchyRuleViolation(
            code="SELF_REPORTING_NOT_ALLOWED",
            message="An employee cannot report to themselves.",
        )

    # Check for duplicate supervisor
    if relationship == "SUPERVISOR":
        for emp, mgr, rel in existing_links:
            if emp == employee_id and rel == "SUPERVISOR" and mgr != manager_id:
                raise HierarchyRuleViolation(
                    code="MULTIPLE_SUPERVISORS_NOT_ALLOWED",
                    message="An employee may have at most one supervisor.",
                )

    # Check for directed cycle.
    # An edge (u, v) means u reports to v (u is subordinate, v is manager).
    # Adding (employee_id -> manager_id) creates a cycle if there is already a path
    # from manager_id to employee_id (i.e. manager_id already reports directly or
    # indirectly to employee_id).
    adjacency: dict[str, set[str]] = defaultdict(set)
    for emp, mgr, _ in existing_links:
        adjacency[emp].add(mgr)

    # Check if employee_id is reachable from manager_id
    visited: set[str] = set()
    queue: deque[str] = deque([manager_id])
    while queue:
        current = queue.popleft()
        if current == employee_id:
            raise HierarchyRuleViolation(
                code="HIERARCHY_CYCLE",
                message="Cannot create reporting line: cycle detected in hierarchy.",
            )
        if current not in visited:
            visited.add(current)
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)


def compute_transitive_scope(
    user_employee_id: str,
    links: list[tuple[str, str]],  # (employee_id, manager_id)
) -> set[str]:
    """Compute all employee IDs within the reporting scope of user_employee_id.

    Scope includes:
    1. The user themselves (self).
    2. All direct and indirect subordinates (descendants in the management hierarchy).
    """
    # Build downward adjacency: manager -> set of direct subordinates
    subordinates_map: dict[str, set[str]] = defaultdict(set)
    for emp_id, mgr_id in links:
        subordinates_map[mgr_id].add(emp_id)

    scope: set[str] = {user_employee_id}
    queue: deque[str] = deque([user_employee_id])
    visited: set[str] = {user_employee_id}

    while queue:
        current_mgr = queue.popleft()
        for subordinate in subordinates_map.get(current_mgr, set()):
            if subordinate not in visited:
                visited.add(subordinate)
                scope.add(subordinate)
                queue.append(subordinate)

    return scope

