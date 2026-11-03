"""Pure validation rules for bulk imports.

Per docs/11-import-pipeline.md:
- Stable validation codes with clear severity levels.
"""

from collections import defaultdict
from datetime import date
from typing import Any


def check_date_range(start: date | None, end: date | None) -> str | None:
    """Validate that start date is on or before end date."""
    if start and end and end < start:
        return "END_BEFORE_START"
    return None


def detect_file_key_clashes(
    rows: list[dict[str, Any]], key_fields: list[str]
) -> dict[int, list[str]]:
    """Detect rows in the file sharing the same primary key.

    Returns mapping of row_index -> list of error codes.
    If the exact same row content is repeated: DUPLICATE_KEY_IN_FILE.
    If the key matches but non-key content differs: KEY_CLASH.
    """
    row_errors: dict[int, list[str]] = defaultdict(list)
    key_to_rows: dict[tuple[Any, ...], list[tuple[int, dict[str, Any]]]] = defaultdict(list)

    for idx, row in enumerate(rows):
        key = tuple(row.get(k) for k in key_fields)
        if all(v is not None for v in key):
            key_to_rows[key].append((idx, row))

    for _key, entries in key_to_rows.items():
        if len(entries) > 1:
            first_idx, first_row = entries[0]
            # Check if all duplicate rows have identical payload
            for other_idx, other_row in entries[1:]:
                # compare values ignoring None/empty
                is_identical = True
                for k in set(first_row.keys()).union(other_row.keys()):
                    if first_row.get(k) != other_row.get(k):
                        is_identical = False
                        break
                code = "DUPLICATE_KEY_IN_FILE" if is_identical else "KEY_CLASH"
                row_errors[first_idx].append(code)
                row_errors[other_idx].append(code)

    return row_errors


def detect_reporting_issues(
    reporting_rows: list[dict[str, Any]],
) -> dict[int, list[str]]:
    """Validate reporting rows for self-reference, multiple supervisors, and hierarchy cycles.

    Each row has: employee_tally_id, manager_tally_id, relationship.
    """
    row_errors: dict[int, list[str]] = defaultdict(list)
    supervisor_counts: dict[str, list[int]] = defaultdict(list)
    manager_graph: dict[str, list[str]] = defaultdict(list)

    for idx, r in enumerate(reporting_rows):
        emp = str(r.get("employee_tally_id", "") or "").strip()
        mgr = str(r.get("manager_tally_id", "") or "").strip()
        rel = str(r.get("relationship", "") or "").strip().upper()

        if emp and mgr:
            # 1. Self reference check
            if emp == mgr:
                row_errors[idx].append("SELF_REFERENCE")

            # 2. Multiple supervisors check
            if rel == "SUPERVISOR":
                supervisor_counts[emp].append(idx)

            manager_graph[emp].append(mgr)

    # Multiple supervisors check
    for _emp, indices in supervisor_counts.items():
        if len(indices) > 1:
            for idx in indices:
                row_errors[idx].append("MULTIPLE_SUPERVISORS")

    # 3. Hierarchy cycle check
    # Find all nodes that can reach themselves
    cycle_nodes: set[str] = set()

    for start_node in manager_graph:
        visited: set[str] = set()
        queue = list(manager_graph.get(start_node, []))
        while queue:
            curr = queue.pop(0)
            if curr == start_node:
                cycle_nodes.add(start_node)
                break
            if curr not in visited:
                visited.add(curr)
                queue.extend(manager_graph.get(curr, []))

    if cycle_nodes:
        for idx, r in enumerate(reporting_rows):
            emp = str(r.get("employee_tally_id", "") or "").strip()
            if emp in cycle_nodes:
                row_errors[idx].append("HIERARCHY_CYCLE")

    return row_errors
