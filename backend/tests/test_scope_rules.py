"""Unit tests for worksite-based access scope rules (DEC-57, DEC-10)."""

import pytest

from fw.rules.scope import AccessLevel, ScopePurpose, employee_access, scope_supervisor_ids

DIR, REQ, OPS = ScopePurpose.DIRECTORY, ScopePurpose.REQUESTS, ScopePurpose.OPERATIONS
FULL, RO = AccessLevel.FULL, AccessLevel.READ_ONLY


@pytest.mark.parametrize("purpose", [DIR, REQ, OPS])
def test_admin_sees_everything(purpose: ScopePurpose) -> None:
    assert employee_access("ADMIN", purpose, in_crew=False, on_my_sites=False) == FULL


@pytest.mark.parametrize("purpose", [DIR, REQ, OPS])
def test_worker_sees_only_self(purpose: ScopePurpose) -> None:
    assert employee_access("WORKER", purpose, in_crew=True, on_my_sites=False) == FULL
    assert employee_access("WORKER", purpose, in_crew=False, on_my_sites=True) is None


@pytest.mark.parametrize(
    ("purpose", "in_crew", "on_site", "expected"),
    [
        # Employees: own crew + workers on my worksites (read-only)
        (DIR, True, False, FULL),
        (DIR, False, True, RO),
        (DIR, False, False, None),
        # Leave / own requests: own crew only
        (REQ, True, False, FULL),
        (REQ, False, True, None),
        # Attendance, live map, reports: only days on my worksites
        (OPS, True, True, FULL),
        (OPS, False, True, RO),
        (OPS, True, False, None),  # my crew member on another supervisor's site
        (OPS, False, False, None),
    ],
)
def test_supervisor_rules(
    purpose: ScopePurpose, in_crew: bool, on_site: bool, expected: AccessLevel | None
) -> None:
    assert employee_access("SUPERVISOR", purpose, in_crew, on_site) == expected


@pytest.mark.parametrize("role", ["SUPERINTENDENT", "ENGINEER"])
@pytest.mark.parametrize("purpose", [DIR, REQ, OPS])
def test_superintendent_and_engineer_rules(role: str, purpose: ScopePurpose) -> None:
    assert employee_access(role, purpose, in_crew=True, on_my_sites=False) == FULL
    assert employee_access(role, purpose, in_crew=False, on_my_sites=True) == RO
    assert employee_access(role, purpose, in_crew=False, on_my_sites=False) is None


def test_scope_supervisor_ids() -> None:
    roles = {"E1": "ENGINEER", "S1": "SUPERVISOR", "S2": "SUPERVISOR", "W1": "WORKER"}
    crew = {"E1", "S1", "S2", "W1"}
    assert scope_supervisor_ids("S1", "SUPERVISOR", {"S1", "W1"}, roles) == {"S1"}
    assert scope_supervisor_ids("E1", "ENGINEER", crew, roles) == {"S1", "S2"}
    assert scope_supervisor_ids("E1", "SUPERINTENDENT", crew, roles) == {"S1", "S2"}
    assert scope_supervisor_ids("W1", "WORKER", {"W1"}, roles) == set()
