"""Unit tests for import normalization and validation rules."""

from datetime import date
from decimal import Decimal

from fw.rules.imports.normalizer import (
    normalize_grade_code,
    normalize_sgd,
    normalize_text,
    parse_cell_value,
)
from fw.rules.imports.validator import (
    check_date_range,
    detect_file_key_clashes,
    detect_reporting_issues,
)


def test_normalize_text():
    assert normalize_text("  hello   world  ") == "hello world"
    assert normalize_text("non\u00a0breaking\u00a0spaces") == "non breaking spaces"
    assert normalize_text("   ") is None
    assert normalize_text(None) is None


def test_normalize_grade_code():
    assert normalize_grade_code("G5-C") == "G5C"
    assert normalize_grade_code("g5c") == "G5C"
    assert normalize_grade_code("G5C26") == "G5C"
    assert normalize_grade_code("G2B26") == "G2B"
    assert normalize_grade_code("G1A") == "G1A"


def test_normalize_sgd():
    # Exact match in controlled list
    sgd, code = normalize_sgd("Gardener Helper")
    assert sgd == "Gardener Helper"
    assert code is None

    # Case insensitive exact match
    sgd, code = normalize_sgd("gardener helper")
    assert sgd == "Gardener Helper"
    assert code is None

    # Alias match
    sgd, code = normalize_sgd("Gardner Helper")
    assert sgd == "Gardener Helper"
    assert code == "SGD_ALIAS_APPLIED"

    sgd, code = normalize_sgd("Superintent")
    assert sgd == "Superintendent"
    assert code == "SGD_ALIAS_APPLIED"

    # Unknown
    sgd, code = normalize_sgd("Specialized Drone Pilot")
    assert sgd == "Specialized Drone Pilot"
    assert code == "SGD_UNKNOWN"


def test_parse_cell_value_cell_rules():
    # 1. Blank cell -> KEEP
    val, action, err = parse_cell_value(None, "text", is_required=True)
    assert action == "KEEP"
    assert err is None

    val, action, err = parse_cell_value("   ", "text", is_required=False)
    assert action == "KEEP"
    assert err is None

    # 2. Underscore on optional -> CLEAR
    val, action, err = parse_cell_value("_", "text", is_required=False)
    assert action == "CLEAR"
    assert err is None

    # 3. Underscore on required -> CLEAR_ON_REQUIRED
    val, action, err = parse_cell_value("_", "text", is_required=True)
    assert action == "CLEAR"
    assert err == "CLEAR_ON_REQUIRED"


def test_parse_cell_value_types():
    # Boolean
    val, action, err = parse_cell_value("Y", "bool", False)
    assert val is True and action == "SET" and err is None

    val, action, err = parse_cell_value("N", "bool", False)
    assert val is False and action == "SET" and err is None

    val, action, err = parse_cell_value("invalid", "bool", False)
    assert action == "SET" and err == "INVALID_TYPE"

    # Date
    val, action, err = parse_cell_value("2026-11-03", "date", False)
    assert val == date(2026, 11, 3) and action == "SET" and err is None

    val, action, err = parse_cell_value("03/11/2026", "date", False)
    assert action == "SET" and err == "INVALID_DATE"

    # Decimal
    val, action, err = parse_cell_value("1250.75", "decimal", False)
    assert val == Decimal("1250.75") and action == "SET" and err is None

    val, action, err = parse_cell_value("-10.00", "decimal", False)
    assert action == "SET" and err == "NEGATIVE_VALUE"


def test_detect_file_key_clashes():
    rows = [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Bob"},
        {"id": "1", "name": "Alice Changed"},  # Clash with row 0
        {"id": "3", "name": "Charlie"},
        {"id": "3", "name": "Charlie"},  # Exact duplicate with row 3
    ]
    clashes = detect_file_key_clashes(rows, ["id"])
    assert "KEY_CLASH" in clashes[0]
    assert "KEY_CLASH" in clashes[2]
    assert "DUPLICATE_KEY_IN_FILE" in clashes[3]
    assert "DUPLICATE_KEY_IN_FILE" in clashes[4]
    assert 1 not in clashes


def test_detect_reporting_issues():
    # Self reference & Multiple supervisors & Cycle
    reporting = [
        {"employee_tally_id": "1001", "manager_tally_id": "1001", "relationship": "SUPERVISOR"},
        {"employee_tally_id": "1002", "manager_tally_id": "2001", "relationship": "SUPERVISOR"},
        {"employee_tally_id": "1002", "manager_tally_id": "2002", "relationship": "SUPERVISOR"},
        {"employee_tally_id": "3001", "manager_tally_id": "3002", "relationship": "SUPERINTENDENT"},
        {"employee_tally_id": "3002", "manager_tally_id": "3001", "relationship": "SUPERINTENDENT"},
    ]
    issues = detect_reporting_issues(reporting)
    assert "SELF_REFERENCE" in issues[0]
    assert "MULTIPLE_SUPERVISORS" in issues[1]
    assert "MULTIPLE_SUPERVISORS" in issues[2]
    assert "HIERARCHY_CYCLE" in issues[3]
    assert "HIERARCHY_CYCLE" in issues[4]


def test_check_date_range():
    assert check_date_range(date(2026, 1, 1), date(2026, 12, 31)) is None
    assert check_date_range(date(2026, 12, 31), date(2026, 1, 1)) == "END_BEFORE_START"
