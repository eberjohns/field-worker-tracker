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


def test_multiple_superintendents_allowed() -> None:
    existing = [
        ("emp-1", "sup-1", "SUPERVISOR"),
        ("emp-1", "supt-1", "SUPERINTENDENT"),
    ]
    # Adding second superintendent is valid
    validate_reporting_link(existing, "emp-1", "supt-2", "SUPERINTENDENT")


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

