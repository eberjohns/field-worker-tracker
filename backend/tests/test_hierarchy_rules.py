"""Unit tests for hierarchy rules."""

import pytest

from fw.rules.hierarchy import (
    HierarchyRuleViolation,
    compute_transitive_scope,
    validate_reporting_link,
)


def test_self_reporting_forbidden() -> None:
    with pytest.raises(HierarchyRuleViolation) as exc:
        validate_reporting_link([], "emp-1", "emp-1", "SUPERVISOR")
    assert exc.value.code == "SELF_REPORTING_NOT_ALLOWED"


def test_single_supervisor_enforced() -> None:
    existing = [("emp-1", "sup-1", "SUPERVISOR")]
    with pytest.raises(HierarchyRuleViolation) as exc:
        validate_reporting_link(existing, "emp-1", "sup-2", "SUPERVISOR")
    assert exc.value.code == "MULTIPLE_SUPERVISORS_NOT_ALLOWED"


def test_worker_direct_link_forbidden() -> None:
    """Workers cannot be directly linked to a superintendent or engineer."""
    with pytest.raises(HierarchyRuleViolation) as exc:
        validate_reporting_link(
            [],
            "worker-1",
            "supt-1",
            "SUPERINTENDENT",
            employee_role="WORKER",
            manager_role="SUPERINTENDENT",
        )
    assert exc.value.code == "WORKER_DIRECT_LINK_NOT_ALLOWED"

    with pytest.raises(HierarchyRuleViolation) as exc2:
        validate_reporting_link(
            [],
            "worker-1",
            "eng-1",
            "ENGINEER",
            employee_role="WORKER",
            manager_role="ENGINEER",
        )
    assert exc2.value.code == "WORKER_DIRECT_LINK_NOT_ALLOWED"


def test_supervisor_link_role_mismatch() -> None:
    """Manager in a SUPERVISOR link must have role SUPERVISOR."""
    with pytest.raises(HierarchyRuleViolation) as exc:
        validate_reporting_link(
            [],
            "worker-1",
            "mgr-1",
            "SUPERVISOR",
            employee_role="WORKER",
            manager_role="ENGINEER",
        )
    assert exc.value.code == "SUPERVISOR_LINK_ROLE_MISMATCH"


def test_invalid_link_subject() -> None:
    """Superintendent and engineer links attach ONLY to supervisors."""
    with pytest.raises(HierarchyRuleViolation) as exc:
        validate_reporting_link(
            [],
            "eng-1",
            "supt-1",
            "SUPERINTENDENT",
            employee_role="ENGINEER",
            manager_role="SUPERINTENDENT",
        )
    assert exc.value.code == "INVALID_LINK_SUBJECT"


def test_supervisor_cannot_report_to_supervisor() -> None:
    """SUPERVISOR links whose subject has role SUPERVISOR must be rejected with INVALID_LINK_SUBJECT."""
    with pytest.raises(HierarchyRuleViolation) as exc:
        validate_reporting_link(
            [],
            "sup-1",
            "sup-2",
            "SUPERVISOR",
            employee_role="SUPERVISOR",
            manager_role="SUPERVISOR",
        )
    assert exc.value.code == "INVALID_LINK_SUBJECT"


def test_hierarchy_role_mismatch_for_leadership() -> None:
    """Manager role must match SUPERINTENDENT/ENGINEER relationship."""
    with pytest.raises(HierarchyRuleViolation) as exc:
        validate_reporting_link(
            [],
            "sup-1",
            "mgr-1",
            "SUPERINTENDENT",
            employee_role="SUPERVISOR",
            manager_role="ENGINEER",
        )
    assert exc.value.code == "HIERARCHY_ROLE_MISMATCH"


def test_valid_fixed_crew_hierarchy() -> None:
    """Valid crew setup: Worker -> Supervisor -> Superintendent & Engineer."""
    # Worker -> Supervisor
    validate_reporting_link(
        [],
        "worker-1",
        "sup-1",
        "SUPERVISOR",
        employee_role="WORKER",
        manager_role="SUPERVISOR",
    )
    # Supervisor -> Superintendent
    validate_reporting_link(
        [("worker-1", "sup-1", "SUPERVISOR")],
        "sup-1",
        "supt-1",
        "SUPERINTENDENT",
        employee_role="SUPERVISOR",
        manager_role="SUPERINTENDENT",
    )
    # Supervisor -> Engineer
    validate_reporting_link(
        [("worker-1", "sup-1", "SUPERVISOR"), ("sup-1", "supt-1", "SUPERINTENDENT")],
        "sup-1",
        "eng-1",
        "ENGINEER",
        employee_role="SUPERVISOR",
        manager_role="ENGINEER",
    )


def test_direct_cycle_detected() -> None:
    # A reports to B
    existing = [("A", "B", "SUPERVISOR")]
    # B attempting to report to A forms cycle
    with pytest.raises(HierarchyRuleViolation) as exc:
        validate_reporting_link(existing, "B", "A", "ENGINEER")
    assert exc.value.code == "HIERARCHY_CYCLE"


def test_indirect_cycle_detected() -> None:
    # A -> B -> C -> D
    existing = [
        ("A", "B", "SUPERVISOR"),
        ("B", "C", "SUPERINTENDENT"),
        ("C", "D", "ENGINEER"),
    ]
    # D reports to A forms cycle A -> B -> C -> D -> A
    with pytest.raises(HierarchyRuleViolation) as exc:
        validate_reporting_link(existing, "D", "A", "SUPERVISOR")
    assert exc.value.code == "HIERARCHY_CYCLE"


def test_compute_transitive_scope() -> None:
    # Engineer E manages Superintendent S1 and S2
    # S1 manages Supervisor V1
    # V1 manages Worker W1 and W2
    links = [
        ("S1", "E"),
        ("S2", "E"),
        ("V1", "S1"),
        ("W1", "V1"),
        ("W2", "V1"),
        ("W3", "S2"),
    ]

    # E's scope should include self + all descendants: {E, S1, S2, V1, W1, W2, W3}
    e_scope = compute_transitive_scope("E", links)
    assert e_scope == {"E", "S1", "S2", "V1", "W1", "W2", "W3"}

    # V1's scope should be self + W1 + W2
    v1_scope = compute_transitive_scope("V1", links)
    assert v1_scope == {"V1", "W1", "W2"}

    # Worker W1's scope should be just self
    w1_scope = compute_transitive_scope("W1", links)
    assert w1_scope == {"W1"}
