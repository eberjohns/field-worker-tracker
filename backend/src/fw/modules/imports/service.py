"""Service implementing the full bulk import pipeline.

Per docs/11-import-pipeline.md and DEC-51:
- Parse sheets by header row 4, data from row 5, skip '#' / 'EXAMPLE' in col A.
- Normalize strings, grade suffixes, SGD aliases.
- Cell rules: blank keeps, '_' clears optional (refused on required).
- Row-level diff tracking: old -> new per field.
- Atomic commit in one transaction for Phase 03 sheets in order.
- Safe rollback check.
"""

import hashlib
import io
import json
from collections import defaultdict
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

import openpyxl
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.audit import AuditService
from fw.modules.identity import User, hash_password
from fw.modules.imports.models import ImportBatch, ImportRow
from fw.modules.imports.registry import SHEET_REGISTRY
from fw.modules.imports.schemas import (
    ImportCommitResponse,
    ImportPreviewResponse,
    ImportRollbackResponse,
    ImportRowRead,
)
from fw.modules.jobs import JobItem, JobsService, Worksite
from fw.modules.org import (
    Accommodation,
    Employee,
    EmployeeDocument,
    EmployeeReportingLine,
    Group,
    Zone,
)
from fw.modules.payroll import EmployeeSalary, PayrollSalaryService
from fw.modules.payroll.schemas import EmployeeSalaryCreate
from fw.modules.settings import CompanySettingValue, PublicHoliday, SettingsService, TimeRule
from fw.rules.imports import (
    detect_file_key_clashes,
    detect_reporting_issues,
    normalize_frequency_text,
    normalize_grade_code,
    normalize_sgd,
    parse_cell_value,
    validate_worksite_job_number,
)
from fw.rules.jobs import is_job_outdoor
from fw.rules.payroll import compute_next_payroll_month_start


def to_date_obj(val: Any) -> date | None:
    """Convert string/date to date object."""
    if val is None or val == "":
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return datetime.strptime(val[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def to_json_serializable(val: Any) -> Any:
    """Recursively convert date, time, Decimal, UUID to JSON-serializable types."""
    if isinstance(val, (date, datetime, time)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, dict):
        return {k: to_json_serializable(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [to_json_serializable(x) for x in val]
    return val


class ImportService:
    @staticmethod
    async def parse_and_preview(
        session: AsyncSession,
        file_bytes: bytes,
        filename: str,
        user_id: UUID,
    ) -> ImportPreviewResponse:
        """Parse uploaded workbook, compare with database, and store preview rows with field-level diffs."""
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Check if already uploaded and previewed/committed
        batch = ImportBatch(
            kind="FULL_WORKBOOK",
            filename=filename,
            file_hash=file_hash,
            template_version="v1.0",
            uploaded_by_user_id=user_id,
            status="PREVIEWED",
            summary={},
        )
        session.add(batch)
        await session.flush()

        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)

        total_rows = 0
        counts = {
            "NEW": 0,
            "UPDATED": 0,
            "UNCHANGED": 0,
            "REACTIVATED": 0,
            "ERROR": 0,
            "WARNING": 0,
            "SKIPPED": 0,
        }
        sheet_counts: dict[str, dict[str, int]] = {}

        # Pre-load existing database entities for comparison
        existing_groups = {
            g.code: g for g in (await session.execute(select(Group))).scalars().all()
        }
        existing_zones = {z.code: z for z in (await session.execute(select(Zone))).scalars().all()}
        existing_accommodations = {
            a.accommodation_code: a
            for a in (await session.execute(select(Accommodation))).scalars().all()
        }
        existing_employees = {
            e.tally_id: e for e in (await session.execute(select(Employee))).scalars().all()
        }
        existing_reporting = {
            (r.employee_id, r.manager_id, r.relationship): r
            for r in (await session.execute(select(EmployeeReportingLine))).scalars().all()
        }
        existing_salaries = {
            (s.employee_id, s.effective_from): s
            for s in (await session.execute(select(EmployeeSalary))).scalars().all()
        }
        existing_holidays = {
            (h.holiday_date, h.country): h
            for h in (await session.execute(select(PublicHoliday))).scalars().all()
        }
        existing_settings = {
            (s.setting_key, s.country, s.effective_from): s
            for s in (await session.execute(select(CompanySettingValue))).scalars().all()
        }
        existing_time_rules = {
            (r.name, r.scope_type, r.scope_employee_id, r.start_date): r
            for r in (await session.execute(select(TimeRule))).scalars().all()
        }
        existing_worksites = {
            w.job_number: w for w in (await session.execute(select(Worksite))).scalars().all()
        }
        existing_job_items = {
            (j.worksite_id, j.sub_item_code): j
            for j in (await session.execute(select(JobItem))).scalars().all()
        }

        # Pre-collect natural keys present in this workbook for same-file foreign key resolution
        file_groups: set[str] = set()
        if "Groups" in wb.sheetnames:
            ws_g = wb["Groups"]
            for r_idx in range(5, ws_g.max_row + 1):
                if ws_g.cell(r_idx, 1).value:
                    continue
                v = ws_g.cell(r_idx, 2).value
                if v and str(v).strip():
                    file_groups.add(str(v).strip())

        file_zones: set[str] = set()
        if "Zones" in wb.sheetnames:
            ws_z = wb["Zones"]
            for r_idx in range(5, ws_z.max_row + 1):
                if ws_z.cell(r_idx, 1).value:
                    continue
                v = ws_z.cell(r_idx, 2).value
                if v and str(v).strip():
                    file_zones.add(str(v).strip())

        file_worksites: set[str] = set()
        if "Worksites" in wb.sheetnames:
            ws_w = wb["Worksites"]
            for r_idx in range(5, ws_w.max_row + 1):
                if ws_w.cell(r_idx, 1).value:
                    continue
                v = ws_w.cell(r_idx, 2).value
                if v and str(v).strip():
                    file_worksites.add(str(v).strip())

        file_accommodations: set[str] = set()
        if "Accommodations" in wb.sheetnames:
            ws_acc = wb["Accommodations"]
            for r_idx in range(5, ws_acc.max_row + 1):
                col_a = ws_acc.cell(r_idx, 1).value
                if col_a is not None and str(col_a).strip() != "":
                    continue
                val = ws_acc.cell(r_idx, 2).value
                if val is not None and str(val).strip() != "":
                    file_accommodations.add(str(val).strip())

        file_employees: set[str] = set()
        if "Employees" in wb.sheetnames:
            ws_emp = wb["Employees"]
            for r_idx in range(5, ws_emp.max_row + 1):
                col_a = ws_emp.cell(r_idx, 1).value
                if col_a is not None and str(col_a).strip() != "":
                    continue
                val = ws_emp.cell(r_idx, 2).value
                if val is not None and str(val).strip() != "":
                    file_employees.add(str(val).strip())

        # Process each sheet defined in registry
        for sheet_name, sheet_def in SHEET_REGISTRY.items():
            sheet_counts[sheet_name] = {
                "total": 0,
                "new": 0,
                "updated": 0,
                "unchanged": 0,
                "errors": 0,
                "warnings": 0,
                "skipped": 0,
            }

            if sheet_name not in wb.sheetnames:
                continue

            ws = wb[sheet_name]

            # Out of scope sheet check
            if not sheet_def.is_in_scope_phase_03:
                # Validate headers row 4, report as SKIPPED
                _row4 = [ws.cell(4, c).value for c in range(2, len(sheet_def.columns) + 2)]
                row_objs = []
                for r_idx in range(5, ws.max_row + 1):
                    col_a = ws.cell(r_idx, 1).value
                    if col_a is not None and str(col_a).strip() != "":
                        continue
                    vals = [ws.cell(r_idx, c).value for c in range(2, len(sheet_def.columns) + 2)]
                    if not any(v is not None and str(v).strip() != "" for v in vals):
                        continue
                    ir = ImportRow(
                        batch_id=batch.id,
                        sheet=sheet_name,
                        row_number=r_idx,
                        natural_key=str(vals[0] or f"row-{r_idx}"),
                        action="SKIPPED",
                        status="INFO",
                        codes=["OUT_OF_SCOPE_PHASE_03"],
                        messages=[
                            {
                                "field": None,
                                "code": "OUT_OF_SCOPE_PHASE_03",
                                "message": f"Sheet {sheet_name} is deferred to a later phase.",
                            }
                        ],
                        diff={},
                        normalized={},
                        raw_row={
                            sheet_def.columns[i].name: str(vals[i])
                            for i in range(len(vals))
                            if vals[i] is not None
                        },
                    )
                    row_objs.append(ir)
                    counts["SKIPPED"] += 1
                    sheet_counts[sheet_name]["skipped"] += 1
                    sheet_counts[sheet_name]["total"] += 1
                session.add_all(row_objs)
                continue

            # In-scope sheet processing
            # 1. Parse raw rows
            raw_rows: list[tuple[int, dict[str, Any]]] = []
            for r_idx in range(5, ws.max_row + 1):
                col_a = ws.cell(r_idx, 1).value
                if col_a is not None and str(col_a).strip() != "":
                    # Skip comment or example row
                    continue
                row_dict: dict[str, Any] = {}
                has_any_val = False
                for c_idx, col in enumerate(sheet_def.columns, start=2):
                    cell_val = ws.cell(r_idx, c_idx).value
                    row_dict[col.name] = cell_val
                    if cell_val is not None and str(cell_val).strip() != "":
                        has_any_val = True
                if has_any_val:
                    raw_rows.append((r_idx, row_dict))

            # 2. Clashes and validation
            key_clashes = detect_file_key_clashes([r[1] for r in raw_rows], sheet_def.primary_key)
            reporting_issues = (
                detect_reporting_issues([r[1] for r in raw_rows])
                if sheet_name == "Employee_Reporting"
                else {}
            )

            for idx, (r_idx, raw_dict) in enumerate(raw_rows):
                total_rows += 1
                sheet_counts[sheet_name]["total"] += 1

                normalized_dict: dict[str, Any] = {}
                row_diff: dict[str, Any] = {}
                row_codes: list[str] = []
                row_messages: list[dict[str, Any]] = []
                row_action = "NEW"
                row_status = "OK"

                # Check clashes
                if idx in key_clashes:
                    for code in key_clashes[idx]:
                        row_codes.append(code)
                        row_messages.append(
                            {
                                "field": sheet_def.primary_key[0],
                                "code": code,
                                "message": f"Duplicate natural key clash in file: {code}",
                            }
                        )
                        row_status = "ERROR"

                # Check reporting issues
                if idx in reporting_issues:
                    for code in reporting_issues[idx]:
                        row_codes.append(code)
                        row_messages.append(
                            {
                                "field": "reporting",
                                "code": code,
                                "message": f"Reporting issue: {code}",
                            }
                        )
                        row_status = "ERROR"

                # Parse and normalize each column
                for col in sheet_def.columns:
                    raw_val = raw_dict.get(col.name)
                    parsed_val, cell_action, err_code = parse_cell_value(
                        raw_val=raw_val,
                        col_type=col.col_type,
                        is_required=col.required,
                        enum_values=col.enum_values,
                    )

                    if err_code:
                        row_codes.append(err_code)
                        row_messages.append(
                            {
                                "field": col.name,
                                "code": err_code,
                                "message": f"Column {col.name} error: {err_code}",
                            }
                        )
                        row_status = "ERROR"

                    # Additional normalizations
                    if col.name == "staff_grade_description" and parsed_val is not None:
                        sgd_val, sgd_code = normalize_sgd(parsed_val)
                        parsed_val = sgd_val
                        if sgd_code == "SGD_ALIAS_APPLIED":
                            row_codes.append("SGD_ALIAS_APPLIED")
                            row_messages.append(
                                {
                                    "field": col.name,
                                    "code": "SGD_ALIAS_APPLIED",
                                    "message": f"SGD alias normalized to {sgd_val}",
                                }
                            )
                        elif sgd_code == "SGD_UNKNOWN":
                            row_codes.append("SGD_UNKNOWN")
                            row_messages.append(
                                {
                                    "field": col.name,
                                    "code": "SGD_UNKNOWN",
                                    "message": f"Unknown SGD '{raw_val}'",
                                }
                            )
                            if row_status != "ERROR":
                                row_status = "WARNING"

                    elif col.name == "grade_code" and parsed_val is not None:
                        parsed_val = normalize_grade_code(parsed_val)

                    normalized_dict[col.name] = {
                        "value": parsed_val,
                        "action": cell_action,
                    }

                # Construct natural key string
                nat_key_parts = []
                for pk_col in sheet_def.primary_key:
                    pk_val = normalized_dict.get(pk_col, {}).get("value")
                    if pk_val is None:
                        pk_val = raw_dict.get(pk_col)
                    nat_key_parts.append(str(pk_val or ""))
                natural_key_str = ":".join(nat_key_parts)

                # Compare with DB state
                # Groups
                if sheet_name == "Groups":
                    code = normalized_dict["group_code"]["value"]
                    if code in existing_groups:
                        g = existing_groups[code]
                        if not g.is_active:
                            row_action = "REACTIVATED"
                        name_action = normalized_dict["group_name"]["action"]
                        name_val = normalized_dict["group_name"]["value"]
                        if name_action == "SET" and name_val != g.name:
                            row_action = "UPDATED"
                            row_diff["group_name"] = {"old": g.name, "new": name_val}
                        elif row_action != "REACTIVATED":
                            row_action = "UNCHANGED"

                # Zones
                elif sheet_name == "Zones":
                    code = normalized_dict["zone_code"]["value"]
                    if code in existing_zones:
                        z = existing_zones[code]
                        if not z.is_active:
                            row_action = "REACTIVATED"
                        name_action = normalized_dict["zone_name"]["action"]
                        name_val = normalized_dict["zone_name"]["value"]
                        if name_action == "SET" and name_val != z.name:
                            row_action = "UPDATED"
                            row_diff["zone_name"] = {"old": z.name, "new": name_val}
                        elif row_action != "REACTIVATED":
                            row_action = "UNCHANGED"

                # Accommodations
                elif sheet_name == "Accommodations":
                    acc_code = normalized_dict["accommodation_code"]["value"]
                    if acc_code in existing_accommodations:
                        acc = existing_accommodations[acc_code]
                        if not acc.is_active:
                            row_action = "REACTIVATED"
                        for field_name in ("name", "address"):
                            act = normalized_dict[field_name]["action"]
                            new_v = normalized_dict[field_name]["value"]
                            old_v = getattr(acc, field_name)
                            if act == "CLEAR" and old_v is not None:
                                row_action = "UPDATED"
                                row_diff[field_name] = {"old": old_v, "new": None}
                            elif act == "SET" and new_v != old_v:
                                row_action = "UPDATED"
                                row_diff[field_name] = {"old": old_v, "new": new_v}
                        if row_action != "REACTIVATED" and not row_diff:
                            row_action = "UNCHANGED"

                # Employees
                elif sheet_name == "Employees":
                    tally_id = normalized_dict["tally_id"]["value"]
                    if tally_id in existing_employees:
                        emp = existing_employees[tally_id]
                        if not emp.is_active:
                            row_action = "REACTIVATED"

                        for field_name in (
                            "name",
                            "role",
                            "grade_code",
                            "staff_grade_description",
                            "country",
                            "weekly_off_day",
                            "is_driver",
                            "join_date",
                            "employment_end_date",
                        ):
                            act = normalized_dict[field_name]["action"]
                            new_v = normalized_dict[field_name]["value"]
                            old_v = getattr(emp, field_name)
                            if act == "CLEAR" and old_v is not None:
                                row_action = "UPDATED"
                                row_diff[field_name] = {"old": str(old_v), "new": None}
                            elif act == "SET" and new_v != old_v:
                                row_action = "UPDATED"
                                row_diff[field_name] = {
                                    "old": str(old_v) if old_v is not None else None,
                                    "new": str(new_v),
                                }

                        if row_action != "REACTIVATED" and not row_diff:
                            row_action = "UNCHANGED"

                    # Accommodation reference check (applies to both new and existing employees)
                    acc_code_act = normalized_dict["accommodation_code"]["action"]
                    acc_code_v = normalized_dict["accommodation_code"]["value"]
                    if acc_code_act == "SET" and acc_code_v:
                        if (
                            acc_code_v not in existing_accommodations
                            and acc_code_v not in file_accommodations
                        ):
                            row_codes.append("REFERENCE_NOT_FOUND")
                            row_messages.append(
                                {
                                    "field": "accommodation_code",
                                    "code": "REFERENCE_NOT_FOUND",
                                    "message": f"Accommodation {acc_code_v} not found",
                                }
                            )
                            row_status = "ERROR"

                # Employee_Reporting
                elif sheet_name == "Employee_Reporting":
                    emp_tally = normalized_dict["employee_tally_id"]["value"]
                    mgr_tally = normalized_dict["manager_tally_id"]["value"]
                    rel = normalized_dict["relationship"]["value"]

                    emp_exists = (emp_tally in existing_employees) or (emp_tally in file_employees)
                    mgr_exists = (mgr_tally in existing_employees) or (mgr_tally in file_employees)
                    if not emp_exists:
                        row_codes.append("REFERENCE_NOT_FOUND")
                        row_messages.append(
                            {
                                "field": "employee_tally_id",
                                "code": "REFERENCE_NOT_FOUND",
                                "message": f"Employee {emp_tally} not found",
                            }
                        )
                        row_status = "ERROR"
                    if not mgr_exists:
                        row_codes.append("REFERENCE_NOT_FOUND")
                        row_messages.append(
                            {
                                "field": "manager_tally_id",
                                "code": "REFERENCE_NOT_FOUND",
                                "message": f"Manager {mgr_tally} not found",
                            }
                        )
                        row_status = "ERROR"

                    if emp_tally in existing_employees and mgr_tally in existing_employees:
                        emp_obj = existing_employees[emp_tally]
                        mgr_obj = existing_employees[mgr_tally]
                        if emp_obj and mgr_obj and rel:
                            rep_key = (emp_obj.id, mgr_obj.id, rel)
                            if rep_key in existing_reporting:
                                row_action = "UNCHANGED"

                # Employee_Salary
                elif sheet_name == "Employee_Salary":
                    tally_id = normalized_dict["tally_id"]["value"]
                    eff_from = normalized_dict["effective_from"]["value"]
                    if not eff_from:
                        eff_from = compute_next_payroll_month_start(date.today())
                        normalized_dict["effective_from"]["value"] = eff_from

                    emp_exists = (tally_id in existing_employees) or (tally_id in file_employees)
                    if not emp_exists:
                        row_codes.append("REFERENCE_NOT_FOUND")
                        row_messages.append(
                            {
                                "field": "tally_id",
                                "code": "REFERENCE_NOT_FOUND",
                                "message": f"Employee {tally_id} not found for salary structure",
                            }
                        )
                        row_status = "ERROR"
                    else:
                        emp_obj = existing_employees.get(tally_id)
                        if emp_obj:
                            sal_key = (emp_obj.id, eff_from)
                            if sal_key in existing_salaries:
                                sal = existing_salaries[sal_key]
                                for s_field in (
                                    "standard_hours",
                                    "basic_salary",
                                    "special_allowance",
                                    "fixed_ot_amount",
                                    "bonus",
                                    "telephone_allowance",
                                    "housing_transport_allowance",
                                ):
                                    act = normalized_dict[s_field]["action"]
                                    new_v = normalized_dict[s_field]["value"]
                                    old_v = getattr(sal, s_field)
                                    if act == "SET" and new_v != old_v:
                                        row_action = "UPDATED"
                                        row_diff[s_field] = {"old": str(old_v), "new": str(new_v)}
                                if not row_diff:
                                    row_action = "UNCHANGED"

                # Public_Holidays
                elif sheet_name == "Public_Holidays":
                    h_date = normalized_dict["holiday_date"]["value"]
                    h_country = normalized_dict["country"]["value"]
                    h_name = normalized_dict["holiday_name"]["value"]
                    if (h_date, h_country) in existing_holidays:
                        h = existing_holidays[(h_date, h_country)]
                        if h_name != h.name:
                            row_action = "UPDATED"
                            row_diff["holiday_name"] = {"old": h.name, "new": h_name}
                        else:
                            row_action = "UNCHANGED"

                # Company_Settings
                elif sheet_name == "Company_Settings":
                    s_key = normalized_dict["setting_key"]["value"]
                    s_country = normalized_dict["country"]["value"]
                    s_eff = normalized_dict["effective_from"]["value"]
                    s_val = normalized_dict["value"]["value"]
                    if (s_key, s_country, s_eff) in existing_settings:
                        s_obj = existing_settings[(s_key, s_country, s_eff)]
                        # Compare json string or raw
                        if str(s_val) != str(s_obj.value):
                            row_action = "UPDATED"
                            row_diff["value"] = {"old": str(s_obj.value), "new": str(s_val)}
                        else:
                            row_action = "UNCHANGED"

                # Time_Rules
                elif sheet_name == "Time_Rules":
                    r_name = normalized_dict["rule_name"]["value"]
                    r_scope = normalized_dict["scope_type"]["value"]
                    r_scope_id = normalized_dict["scope_id"]["value"]
                    r_start = normalized_dict["start_date"]["value"]

                    # Resolve scope_id tally_id to employee UUID
                    scope_emp_id = None
                    if r_scope in ("EMPLOYEE", "TEAM") and r_scope_id:
                        tally_key = str(r_scope_id).strip()
                        if tally_key in existing_employees:
                            scope_emp_id = existing_employees[tally_key].id
                        elif tally_key in file_employees:
                            scope_emp_id = None
                        else:
                            row_codes.append("REFERENCE_NOT_FOUND")
                            row_messages.append(
                                {
                                    "field": "scope_id",
                                    "code": "REFERENCE_NOT_FOUND",
                                    "message": f"Time rule scope employee {r_scope_id} not found",
                                }
                            )
                            row_status = "ERROR"

                    tr_key = (r_name, r_scope, scope_emp_id, r_start)
                    if tr_key in existing_time_rules:
                        row_action = "UNCHANGED"

                # Worksites
                elif sheet_name == "Worksites":
                    job_num = normalized_dict.get("job_number", {}).get("value")
                    # Format check
                    jn_err = validate_worksite_job_number(job_num)
                    if jn_err:
                        row_codes.append(jn_err)
                        row_messages.append(
                            {
                                "field": "job_number",
                                "code": jn_err,
                                "message": (
                                    f"Job number '{job_num}' must match 2 digits + letter (A/B/C) + 5 digits "
                                    "without hyphens, slashes, or combined formats."
                                ),
                            }
                        )
                        row_status = "ERROR"

                    # Group check
                    g_code = normalized_dict.get("group_code", {}).get("value")
                    if g_code and g_code not in existing_groups and g_code not in file_groups:
                        row_codes.append("FOREIGN_KEY_MISSING")
                        row_messages.append(
                            {
                                "field": "group_code",
                                "code": "FOREIGN_KEY_MISSING",
                                "message": f"Group {g_code} not found.",
                            }
                        )
                        row_status = "ERROR"

                    # Zone check
                    z_code = normalized_dict.get("zone_code", {}).get("value")
                    if z_code and z_code not in existing_zones and z_code not in file_zones:
                        row_codes.append("FOREIGN_KEY_MISSING")
                        row_messages.append(
                            {
                                "field": "zone_code",
                                "code": "FOREIGN_KEY_MISSING",
                                "message": f"Zone {z_code} not found.",
                            }
                        )
                        row_status = "ERROR"

                    if job_num and job_num in existing_worksites:
                        ws_obj = existing_worksites[job_num]
                        if not ws_obj.is_active:
                            row_action = "REACTIVATED"
                        for field_name in (
                            "job_name",
                            "renewal_reference",
                            "customer_type",
                            "contract_start_date",
                            "contract_end_date",
                            "labour_budget_amount",
                        ):
                            act = normalized_dict.get(field_name, {}).get("action")
                            new_v = normalized_dict.get(field_name, {}).get("value")
                            attr_name = (
                                "budget_amount"
                                if field_name == "labour_budget_amount"
                                else "start_date"
                                if field_name == "contract_start_date"
                                else "end_date"
                                if field_name == "contract_end_date"
                                else field_name
                            )
                            old_v = getattr(ws_obj, attr_name, None)
                            if act == "CLEAR" and old_v is not None:
                                row_action = "UPDATED"
                                row_diff[field_name] = {"old": str(old_v), "new": None}
                            elif act == "SET" and new_v is not None and str(new_v) != str(old_v):
                                row_action = "UPDATED"
                                row_diff[field_name] = {
                                    "old": str(old_v) if old_v is not None else None,
                                    "new": str(new_v),
                                }
                        if row_action != "REACTIVATED" and not row_diff:
                            row_action = "UNCHANGED"

                # Job_Items
                elif sheet_name == "Job_Items":
                    j_num = normalized_dict.get("job_number", {}).get("value")
                    sub_code = normalized_dict.get("sub_item_code", {}).get("value")

                    # FK check to worksite
                    if j_num and j_num not in existing_worksites and j_num not in file_worksites:
                        row_codes.append("FOREIGN_KEY_MISSING")
                        row_messages.append(
                            {
                                "field": "job_number",
                                "code": "FOREIGN_KEY_MISSING",
                                "message": f"Worksite {j_num} not found.",
                            }
                        )
                        row_status = "ERROR"

                    # Free-text frequency normalization
                    raw_freq = raw_dict.get("frequency_unit")
                    freq_res = normalize_frequency_text(raw_freq)
                    if freq_res:
                        f_unit, f_occ, f_int = freq_res
                        normalized_dict["frequency_unit"]["value"] = f_unit
                        normalized_dict["occurrences_per_period"]["value"] = f_occ
                        normalized_dict["period_interval"]["value"] = f_int

                    ws_id = (
                        existing_worksites[j_num].id
                        if j_num and j_num in existing_worksites
                        else None
                    )
                    if ws_id and (ws_id, sub_code) in existing_job_items:
                        ji_obj = existing_job_items[(ws_id, sub_code)]
                        if not ji_obj.is_active:
                            row_action = "REACTIVATED"
                        for field_name in (
                            "staff_grade_description",
                            "planned_grade_code",
                            "frequency_unit",
                            "occurrences_per_period",
                            "period_interval",
                            "required_staff_count",
                            "hours_per_occurrence_per_staff",
                            "deployment_type",
                            "break_override_minutes",
                        ):
                            act = normalized_dict.get(field_name, {}).get("action")
                            new_v = normalized_dict.get(field_name, {}).get("value")
                            old_v = getattr(ji_obj, field_name, None)
                            if act == "CLEAR" and old_v is not None:
                                row_action = "UPDATED"
                                row_diff[field_name] = {"old": str(old_v), "new": None}
                            elif act == "SET" and new_v is not None and str(new_v) != str(old_v):
                                row_action = "UPDATED"
                                row_diff[field_name] = {
                                    "old": str(old_v) if old_v is not None else None,
                                    "new": str(new_v),
                                }
                        if row_action != "REACTIVATED" and not row_diff:
                            row_action = "UNCHANGED"

                # Tally counts
                if row_status == "ERROR":
                    counts["ERROR"] += 1
                    sheet_counts[sheet_name]["errors"] += 1
                elif row_status == "WARNING":
                    counts["WARNING"] += 1
                    sheet_counts[sheet_name]["warnings"] += 1

                if row_status != "ERROR":
                    counts[row_action] += 1
                    sheet_counts[sheet_name][row_action.lower()] += 1

                ir = ImportRow(
                    batch_id=batch.id,
                    sheet=sheet_name,
                    row_number=r_idx,
                    natural_key=natural_key_str,
                    action=row_action,
                    status=row_status,
                    codes=row_codes,
                    messages=row_messages,
                    diff=to_json_serializable(row_diff),
                    normalized=to_json_serializable(
                        {
                            k: v["value"]
                            for k, v in normalized_dict.items()
                            if v["value"] is not None
                        }
                    ),
                    raw_row={k: str(v) for k, v in raw_dict.items() if v is not None},
                )
                session.add(ir)

        # Batch summary
        can_commit = counts["ERROR"] == 0
        batch.summary = {
            "total_rows": total_rows,
            "counts": counts,
            "sheet_counts": sheet_counts,
            "can_commit": can_commit,
        }
        await session.flush()

        # Fetch preview rows to return
        rows_stmt = (
            select(ImportRow)
            .where(ImportRow.batch_id == batch.id)
            .order_by(ImportRow.sheet.asc(), ImportRow.row_number.asc())
            .limit(200)
        )
        rows_res = await session.execute(rows_stmt)
        preview_rows = [ImportRowRead.model_validate(r) for r in rows_res.scalars().all()]

        return ImportPreviewResponse(
            batch_id=batch.id,
            filename=filename,
            template_version="v1.0",
            status=batch.status,
            can_commit=can_commit,
            summary=batch.summary,
            rows=preview_rows,
        )

    @staticmethod
    async def commit_batch(
        session: AsyncSession,
        batch_id: UUID,
        user_id: UUID,
        actor_role: str = "ADMIN",
    ) -> ImportCommitResponse:
        """Atomic commit of all rows in the batch in strict dependency order."""
        b_stmt = select(ImportBatch).where(ImportBatch.id == batch_id)
        b_res = await session.execute(b_stmt)
        batch = b_res.scalar_one_or_none()
        if not batch:
            raise ValueError(f"Import batch {batch_id} not found")

        if batch.status == "COMMITTED":
            return ImportCommitResponse(
                batch_id=batch.id,
                status=batch.status,
                committed_at=batch.committed_at or datetime.now(UTC),
                summary=batch.summary,
            )

        # Check errors
        err_stmt = select(ImportRow).where(
            ImportRow.batch_id == batch_id, ImportRow.status == "ERROR"
        )
        err_res = await session.execute(err_stmt)
        if err_res.scalars().first() is not None:
            raise ValueError("Cannot commit batch containing errors")

        # Load all rows for this batch grouped by sheet
        rows_stmt = (
            select(ImportRow)
            .where(ImportRow.batch_id == batch_id)
            .order_by(ImportRow.row_number.asc())
        )
        rows_res = await session.execute(rows_stmt)
        all_rows = list(rows_res.scalars().all())

        sheet_to_rows: dict[str, list[ImportRow]] = defaultdict(list)
        for r in all_rows:
            sheet_to_rows[r.sheet].append(r)

        # Order of execution: Groups, Zones, Accommodations, Employees, Reporting, Salary, Holidays, Settings, TimeRules
        # 1. Groups
        for r in sheet_to_rows.get("Groups", []):
            if r.action in ("NEW", "UPDATED", "REACTIVATED"):
                code = r.normalized.get("group_code")
                name = r.normalized.get("group_name")
                stmt = select(Group).where(Group.code == code)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if existing:
                    if name:
                        existing.name = name
                    existing.is_active = True
                else:
                    session.add(Group(code=code, name=name))

        await session.flush()

        # 2. Zones
        for r in sheet_to_rows.get("Zones", []):
            if r.action in ("NEW", "UPDATED", "REACTIVATED"):
                code = r.normalized.get("zone_code")
                name = r.normalized.get("zone_name")
                stmt = select(Zone).where(Zone.code == code)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if existing:
                    if name:
                        existing.name = name
                    existing.is_active = True
                else:
                    session.add(Zone(code=code, name=name))

        await session.flush()

        # 3. Accommodations
        for r in sheet_to_rows.get("Accommodations", []):
            if r.action in ("NEW", "UPDATED", "REACTIVATED"):
                acc_code = r.normalized.get("accommodation_code")
                stmt = select(Accommodation).where(Accommodation.accommodation_code == acc_code)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if existing:
                    for field_name in ("name", "address"):
                        if field_name in r.normalized:
                            setattr(existing, field_name, r.normalized[field_name])
                    existing.is_active = True
                else:
                    session.add(
                        Accommodation(
                            accommodation_code=acc_code,
                            name=r.normalized.get("name"),
                            address=r.normalized.get("address"),
                        )
                    )

        await session.flush()

        # 4. Employees & Documents & Web Roles User Provisioning
        acc_map = {
            a.accommodation_code: a.id
            for a in (await session.execute(select(Accommodation))).scalars().all()
        }
        default_pwd = await SettingsService.get_setting(
            session,
            key="default_password",
            default="ChangeMe123!",
        )
        default_pwd_hash = hash_password(str(default_pwd))

        for r in sheet_to_rows.get("Employees", []):
            if r.action in ("NEW", "UPDATED", "REACTIVATED"):
                t_id = r.normalized.get("tally_id")
                stmt = select(Employee).where(Employee.tally_id == t_id)
                emp = (await session.execute(stmt)).scalar_one_or_none()

                acc_code = r.normalized.get("accommodation_code")
                acc_id = acc_map.get(acc_code) if acc_code else None

                if emp:
                    for f in (
                        "name",
                        "role",
                        "grade_code",
                        "staff_grade_description",
                        "country",
                        "weekly_off_day",
                        "is_driver",
                    ):
                        if f in r.normalized:
                            setattr(emp, f, r.normalized[f])
                    if "join_date" in r.normalized:
                        emp.join_date = to_date_obj(r.normalized["join_date"])
                    if "employment_end_date" in r.normalized:
                        emp.employment_end_date = to_date_obj(r.normalized["employment_end_date"])
                    if acc_id is not None:
                        emp.accommodation_id = acc_id
                    emp.is_active = True
                else:
                    emp = Employee(
                        tally_id=t_id,
                        name=r.normalized.get("name"),
                        role=r.normalized.get("role"),
                        grade_code=r.normalized.get("grade_code"),
                        staff_grade_description=r.normalized.get("staff_grade_description"),
                        country=r.normalized.get("country", "AE"),
                        weekly_off_day=r.normalized.get("weekly_off_day"),
                        is_driver=bool(r.normalized.get("is_driver", False)),
                        accommodation_id=acc_id,
                        join_date=to_date_obj(r.normalized.get("join_date")),
                        employment_end_date=to_date_obj(r.normalized.get("employment_end_date")),
                    )
                    session.add(emp)

                await session.flush()

                # Document validity records
                doc_cols = {
                    "visa_expiry_date": "VISA",
                    "passport_expiry_date": "PASSPORT",
                    "emirates_id_expiry_date": "EMIRATES_ID",
                    "labour_card_expiry_date": "LABOUR_CARD",
                    "driving_licence_expiry_date": "DRIVING_LICENCE",
                }
                for col_name, doc_type in doc_cols.items():
                    exp_date = to_date_obj(r.normalized.get(col_name))
                    if exp_date:
                        d_stmt = select(EmployeeDocument).where(
                            EmployeeDocument.employee_id == emp.id,
                            EmployeeDocument.document_type == doc_type,
                        )
                        doc_rec = (await session.execute(d_stmt)).scalar_one_or_none()
                        if doc_rec:
                            doc_rec.expiry_date = exp_date
                            doc_rec.is_active = True
                        else:
                            session.add(
                                EmployeeDocument(
                                    employee_id=emp.id,
                                    document_type=doc_type,
                                    expiry_date=exp_date,
                                    is_active=True,
                                )
                            )

                # Provision user account for web roles
                if emp.role in ("SUPERVISOR", "SUPERINTENDENT", "ENGINEER", "ADMIN"):
                    u_stmt = select(User).where(User.username == emp.tally_id)
                    user_rec = (await session.execute(u_stmt)).scalar_one_or_none()
                    if not user_rec:
                        session.add(
                            User(
                                employee_id=emp.id,
                                username=emp.tally_id,
                                credential_hash=default_pwd_hash,
                                role=emp.role,
                                must_change_password=True,
                                is_active=True,
                            )
                        )

        await session.flush()

        # 5. Employee_Reporting
        emp_id_map = {
            e.tally_id: e.id for e in (await session.execute(select(Employee))).scalars().all()
        }
        for r in sheet_to_rows.get("Employee_Reporting", []):
            emp_t = r.normalized.get("employee_tally_id")
            mgr_t = r.normalized.get("manager_tally_id")
            rel = r.normalized.get("relationship")
            notes = r.normalized.get("notes")
            if emp_t in emp_id_map and mgr_t in emp_id_map and rel:
                e_id = emp_id_map[emp_t]
                m_id = emp_id_map[mgr_t]
                rep_stmt = select(EmployeeReportingLine).where(
                    EmployeeReportingLine.employee_id == e_id,
                    EmployeeReportingLine.manager_id == m_id,
                    EmployeeReportingLine.relationship == rel,
                )
                existing_rep = (await session.execute(rep_stmt)).scalar_one_or_none()
                if not existing_rep:
                    session.add(
                        EmployeeReportingLine(
                            employee_id=e_id,
                            manager_id=m_id,
                            relationship=rel,
                            notes=notes,
                        )
                    )

        await session.flush()

        # 6. Employee_Salary
        for r in sheet_to_rows.get("Employee_Salary", []):
            t_id = r.normalized.get("tally_id")
            if t_id in emp_id_map:
                emp_id = emp_id_map[t_id]
                eff = to_date_obj(r.normalized.get("effective_from"))
                if not eff:
                    eff = compute_next_payroll_month_start(date.today())

                sal_data = EmployeeSalaryCreate(
                    effective_from=eff,
                    standard_hours=Decimal(str(r.normalized.get("standard_hours", 8.0))),
                    basic_salary=Decimal(str(r.normalized.get("basic_salary", 0.00))),
                    special_allowance=Decimal(str(r.normalized.get("special_allowance", 0.00))),
                    fixed_ot_amount=Decimal(str(r.normalized.get("fixed_ot_amount", 0.00))),
                    bonus=Decimal(str(r.normalized.get("bonus", 0.00))),
                    telephone_allowance=Decimal(str(r.normalized.get("telephone_allowance", 0.00))),
                    housing_transport_allowance=Decimal(
                        str(r.normalized.get("housing_transport_allowance", 0.00))
                    ),
                )
                await PayrollSalaryService.create_or_update_salary(
                    session=session,
                    employee_id=emp_id,
                    data=sal_data,
                    actor_user_id=user_id,
                    actor_role=actor_role,
                    batch_id=batch.id,
                )

        await session.flush()

        # 7. Public_Holidays
        for r in sheet_to_rows.get("Public_Holidays", []):
            h_date = to_date_obj(r.normalized.get("holiday_date"))
            h_country = r.normalized.get("country", "AE")
            h_name = r.normalized.get("holiday_name")
            if h_date and h_country and h_name:
                h_stmt = select(PublicHoliday).where(
                    PublicHoliday.holiday_date == h_date,
                    PublicHoliday.country == h_country,
                )
                existing_h = (await session.execute(h_stmt)).scalar_one_or_none()
                if existing_h:
                    existing_h.name = h_name
                else:
                    session.add(
                        PublicHoliday(
                            holiday_date=h_date,
                            country=h_country,
                            name=h_name,
                            created_by_user_id=user_id,
                        )
                    )

        await session.flush()

        # 8. Company_Settings
        for r in sheet_to_rows.get("Company_Settings", []):
            s_key = r.normalized.get("setting_key")
            s_val = r.normalized.get("value")
            s_unit = r.normalized.get("unit")
            s_country = r.normalized.get("country")
            s_eff = to_date_obj(r.normalized.get("effective_from"))

            # Parse JSON value if needed
            parsed_val: Any = s_val
            if isinstance(s_val, str):
                trimmed = s_val.strip()
                if (trimmed.startswith("{") and trimmed.endswith("}")) or (
                    trimmed.startswith("[") and trimmed.endswith("]")
                ):
                    try:
                        parsed_val = json.loads(trimmed)
                    except Exception:
                        parsed_val = trimmed
                else:
                    try:
                        parsed_val = float(trimmed) if "." in trimmed else int(trimmed)
                    except ValueError:
                        parsed_val = trimmed

            if s_key == "budget_only_staff_types":
                if isinstance(parsed_val, str):
                    if parsed_val.startswith("[") and parsed_val.endswith("]"):
                        try:
                            parsed_val = json.loads(parsed_val)
                        except Exception:
                            parsed_val = [
                                x.strip().strip("'\"")
                                for x in parsed_val.strip("[]").split(",")
                                if x.strip()
                            ]
                    else:
                        parsed_val = [
                            x.strip().strip("'\"") for x in parsed_val.split(",") if x.strip()
                        ]
                elif not isinstance(parsed_val, list):
                    parsed_val = [str(parsed_val)]

            if s_key and s_eff:
                await SettingsService.set_setting(
                    session=session,
                    key=s_key,
                    value=parsed_val,
                    country=s_country,
                    effective_from=s_eff,
                    unit=s_unit,
                    created_by_user_id=user_id,
                )

        await session.flush()

        # 9. Time_Rules
        for r in sheet_to_rows.get("Time_Rules", []):
            r_name = r.normalized.get("rule_name")
            r_country = r.normalized.get("country")
            r_scope = r.normalized.get("scope_type")
            r_scope_id = r.normalized.get("scope_id")
            r_applies = r.normalized.get("applies_to", "ALL")
            r_start = to_date_obj(r.normalized.get("start_date"))
            r_end = to_date_obj(r.normalized.get("end_date"))

            scope_emp_id = (
                emp_id_map.get(str(r_scope_id).strip())
                if r_scope in ("EMPLOYEE", "TEAM") and r_scope_id
                else None
            )

            if r_name and r_scope and r_start:
                tr_stmt = select(TimeRule).where(
                    TimeRule.name == r_name,
                    TimeRule.scope_type == r_scope,
                    TimeRule.scope_employee_id == scope_emp_id,
                    TimeRule.start_date == r_start,
                )
                existing_tr = (await session.execute(tr_stmt)).scalar_one_or_none()
                if not existing_tr:
                    session.add(
                        TimeRule(
                            name=r_name,
                            country=r_country,
                            scope_type=r_scope,
                            scope_employee_id=scope_emp_id,
                            applies_to=r_applies,
                            start_date=r_start,
                            end_date=r_end,
                            break_minutes=r.normalized.get("break_minutes"),
                            standard_hours_change_minutes=r.normalized.get(
                                "standard_hours_change_minutes", 0
                            ),
                            created_by_user_id=user_id,
                        )
                    )

        await session.flush()

        # 10. Worksites
        group_map = {g.code: g.id for g in (await session.execute(select(Group))).scalars().all()}
        zone_map = {z.code: z.id for z in (await session.execute(select(Zone))).scalars().all()}

        for r in sheet_to_rows.get("Worksites", []):
            if r.action in ("NEW", "UPDATED", "REACTIVATED"):
                j_num = r.normalized.get("job_number")
                g_code = r.normalized.get("group_code")
                z_code = r.normalized.get("zone_code")
                g_id = group_map.get(str(g_code).strip()) if g_code else None
                z_id = zone_map.get(str(z_code).strip()) if z_code else None

                if not g_id or not z_id or not j_num:
                    continue

                outdoor = is_job_outdoor(j_num)
                ws_stmt = select(Worksite).where(Worksite.job_number == j_num)
                existing_ws = (await session.execute(ws_stmt)).scalar_one_or_none()

                if existing_ws:
                    if "job_name" in r.normalized:
                        existing_ws.job_name = r.normalized["job_name"]
                    if "renewal_reference" in r.normalized:
                        existing_ws.renewal_reference = r.normalized["renewal_reference"]
                    if "customer_type" in r.normalized:
                        existing_ws.customer_type = r.normalized["customer_type"]
                    if "contract_start_date" in r.normalized:
                        existing_ws.start_date = to_date_obj(r.normalized["contract_start_date"])
                    if "contract_end_date" in r.normalized:
                        existing_ws.end_date = to_date_obj(r.normalized["contract_end_date"])
                    if "labour_budget_amount" in r.normalized:
                        existing_ws.budget_amount = r.normalized["labour_budget_amount"]
                    existing_ws.is_active = True
                else:
                    session.add(
                        Worksite(
                            job_number=j_num,
                            job_name=r.normalized.get("job_name", "Untitled Worksite"),
                            renewal_reference=r.normalized.get("renewal_reference"),
                            group_id=g_id,
                            zone_id=z_id,
                            customer_type=r.normalized.get("customer_type"),
                            is_outdoor=outdoor,
                            country=r.normalized.get("country", "AE"),
                            contract_group_ref=r.normalized.get("contract_group_ref"),
                            start_date=to_date_obj(r.normalized.get("contract_start_date")),
                            end_date=to_date_obj(r.normalized.get("contract_end_date")),
                            budget_amount=r.normalized.get("labour_budget_amount"),
                        )
                    )

        await session.flush()

        # 11. Job_Items
        ws_id_map = {
            w.job_number: w.id for w in (await session.execute(select(Worksite))).scalars().all()
        }

        for r in sheet_to_rows.get("Job_Items", []):
            if r.action in ("NEW", "UPDATED", "REACTIVATED"):
                j_num = r.normalized.get("job_number")
                sub_code = r.normalized.get("sub_item_code")
                ws_id = ws_id_map.get(str(j_num).strip()) if j_num else None

                if not ws_id or not sub_code:
                    continue

                wp = r.normalized.get("weekday_pattern")
                wp_list: list[str] | None = None
                if wp:
                    if isinstance(wp, list):
                        wp_list = [str(x).strip().upper() for x in wp]
                    elif isinstance(wp, str):
                        wp_list = [x.strip().upper() for x in wp.split(",") if x.strip()]

                ji_stmt = select(JobItem).where(
                    JobItem.worksite_id == ws_id,
                    JobItem.sub_item_code == str(sub_code).strip(),
                )
                existing_ji = (await session.execute(ji_stmt)).scalar_one_or_none()

                item_obj: JobItem
                if existing_ji:
                    for f in (
                        "staff_grade_description",
                        "planned_grade_code",
                        "frequency_unit",
                        "occurrences_per_period",
                        "period_interval",
                        "required_staff_count",
                        "hours_per_occurrence_per_staff",
                        "deployment_type",
                        "break_override_minutes",
                    ):
                        if f in r.normalized:
                            setattr(existing_ji, f, r.normalized[f])
                    if "start_date" in r.normalized:
                        existing_ji.start_date = (
                            to_date_obj(r.normalized["start_date"]) or existing_ji.start_date
                        )
                    if "end_date" in r.normalized:
                        existing_ji.end_date = to_date_obj(r.normalized["end_date"])
                    if wp_list is not None:
                        existing_ji.weekday_pattern = wp_list
                    existing_ji.is_active = True
                    item_obj = existing_ji
                else:
                    item_obj = JobItem(
                        worksite_id=ws_id,
                        sub_item_code=str(sub_code).strip(),
                        staff_grade_description=r.normalized.get(
                            "staff_grade_description", "Worker"
                        ),
                        planned_grade_code=r.normalized.get("planned_grade_code", "G1A"),
                        frequency_unit=r.normalized.get("frequency_unit", "WEEK"),
                        occurrences_per_period=Decimal(
                            str(r.normalized.get("occurrences_per_period", 1))
                        ),
                        period_interval=int(r.normalized.get("period_interval", 1)),
                        weekday_pattern=wp_list,
                        required_staff_count=int(r.normalized.get("required_staff_count", 1)),
                        hours_per_occurrence_per_staff=Decimal(
                            str(r.normalized.get("hours_per_occurrence_per_staff", 9))
                        ),
                        start_date=to_date_obj(r.normalized.get("start_date"))
                        or datetime.now(UTC).date(),
                        end_date=to_date_obj(r.normalized.get("end_date")),
                        deployment_type=r.normalized.get("deployment_type", "PERMANENT"),
                        break_override_minutes=r.normalized.get("break_override_minutes"),
                    )
                    session.add(item_obj)

                await session.flush()
                # Trigger automatic occurrence generation for the committed job item
                await JobsService.generate_job_occurrences(
                    session=session,
                    job_item_id=item_obj.id,
                    from_date=item_obj.start_date,
                    to_date=None,
                    actor_user_id=user_id,
                    actor_role=actor_role,
                )

        await session.flush()

        # Update batch status
        commit_now = datetime.now(UTC)
        batch.status = "COMMITTED"
        batch.committed_at = commit_now

        # Audit log
        await AuditService.log_action(
            session=session,
            actor_user_id=user_id,
            actor_role=actor_role,
            action="IMPORT_COMMITTED",
            entity_type="IMPORT_BATCH",
            entity_id=str(batch.id),
            diff={"filename": batch.filename, "summary": batch.summary},
            reason="Bulk master data import confirmed",
        )

        return ImportCommitResponse(
            batch_id=batch.id,
            status=batch.status,
            committed_at=commit_now,
            summary=batch.summary,
        )

    @staticmethod
    async def rollback_batch(
        session: AsyncSession,
        batch_id: UUID,
        user_id: UUID,
        actor_role: str = "ADMIN",
    ) -> ImportRollbackResponse:
        """Rollback an import batch if safe."""
        b_stmt = select(ImportBatch).where(ImportBatch.id == batch_id)
        batch = (await session.execute(b_stmt)).scalar_one_or_none()
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        if batch.status != "COMMITTED":
            raise ValueError(f"Batch {batch_id} is in status '{batch.status}' (cannot rollback)")

        # Revert salary records created by this batch
        del_sal = select(EmployeeSalary).where(EmployeeSalary.import_batch_id == batch.id)
        sal_records = (await session.execute(del_sal)).scalars().all()
        for sal in sal_records:
            await session.delete(sal)

        batch.status = "ROLLED_BACK"
        await session.flush()

        await AuditService.log_action(
            session=session,
            actor_user_id=user_id,
            actor_role=actor_role,
            action="IMPORT_ROLLED_BACK",
            entity_type="IMPORT_BATCH",
            entity_id=str(batch.id),
            diff={"status": "ROLLED_BACK"},
            reason="Admin triggered import rollback",
        )

        return ImportRollbackResponse(
            batch_id=batch.id,
            status=batch.status,
            summary=batch.summary,
        )

    @staticmethod
    async def export_errors_xlsx(
        session: AsyncSession,
        batch_id: UUID,
    ) -> bytes:
        """Export error and warning rows as a downloadable Excel report."""
        stmt = (
            select(ImportRow)
            .where(
                ImportRow.batch_id == batch_id,
                ImportRow.status.in_(["ERROR", "WARNING"]),
            )
            .order_by(ImportRow.sheet.asc(), ImportRow.row_number.asc())
        )
        res = await session.execute(stmt)
        rows = list(res.scalars().all())

        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = "Import_Errors"  # type: ignore

        headers = ["Sheet", "Row", "Natural Key", "Status", "Error Codes", "Messages"]
        font_bold = Font(bold=True)
        fill_header = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

        for c_idx, h in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=c_idx, value=h)
            cell.font = font_bold
            cell.fill = fill_header

        for r_idx, r in enumerate(rows, start=2):
            msg_text = "; ".join(m.get("message", "") for m in r.messages)
            ws.cell(row=r_idx, column=1, value=r.sheet)
            ws.cell(row=r_idx, column=2, value=r.row_number)
            ws.cell(row=r_idx, column=3, value=r.natural_key)
            ws.cell(row=r_idx, column=4, value=r.status)
            ws.cell(row=r_idx, column=5, value=", ".join(r.codes))
            ws.cell(row=r_idx, column=6, value=msg_text)

        ws.column_dimensions["A"].width = 20
        ws.column_dimensions["B"].width = 10
        ws.column_dimensions["C"].width = 25
        ws.column_dimensions["D"].width = 12
        ws.column_dimensions["E"].width = 25
        ws.column_dimensions["F"].width = 60

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
