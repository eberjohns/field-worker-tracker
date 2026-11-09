from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.audit import AuditLog, AuditLogRead, AuditService
from fw.modules.identity import User, require_role
from fw.modules.jobs import JobItem, Worksite
from fw.modules.org import Accommodation, Employee

router = APIRouter(prefix="/audit-logs", tags=["audit"])


async def enrich_audit_logs(
    logs: list[AuditLog], session: AsyncSession
) -> list[AuditLogRead]:
    """Enrich audit log records with human-readable names for UUID entities and diff fields."""
    emp_ids: set[UUID] = set()
    ws_ids: set[UUID] = set()
    ji_ids: set[UUID] = set()
    user_ids: set[UUID] = set()
    acc_ids: set[UUID] = set()

    for log in logs:
        if log.actor_user_id:
            user_ids.add(log.actor_user_id)

        try:
            eid = UUID(str(log.entity_id))
            etype = (log.entity_type or "").lower()
            if "employee" in etype:
                emp_ids.add(eid)
            elif "worksite" in etype or etype == "job":
                ws_ids.add(eid)
            elif "job_item" in etype:
                ji_ids.add(eid)
            elif "user" in etype:
                user_ids.add(eid)
            elif "accommodation" in etype:
                acc_ids.add(eid)
        except (ValueError, TypeError):
            pass

        if isinstance(log.diff, dict):
            for k, v in log.diff.items():
                try:
                    vid = UUID(str(v))
                    k_lower = k.lower()
                    if "employee" in k_lower or k_lower in ("manager_id", "supervisor_id"):
                        emp_ids.add(vid)
                    elif "job_item" in k_lower:
                        ji_ids.add(vid)
                    elif "worksite" in k_lower or "job_id" in k_lower:
                        ws_ids.add(vid)
                    elif "accommodation" in k_lower:
                        acc_ids.add(vid)
                    elif "user" in k_lower:
                        user_ids.add(vid)
                except (ValueError, TypeError):
                    pass

    emp_map: dict[str, str] = {}
    if emp_ids:
        q_emp = select(Employee.id, Employee.name, Employee.tally_id).where(
            Employee.id.in_(emp_ids)
        )
        for r in (await session.execute(q_emp)).all():
            emp_map[str(r.id)] = f"{r.name} ({r.tally_id})"

    ws_map: dict[str, str] = {}
    if ws_ids:
        q_ws = select(Worksite.id, Worksite.job_name, Worksite.job_number).where(
            Worksite.id.in_(ws_ids)
        )
        for r in (await session.execute(q_ws)).all():
            ws_map[str(r.id)] = f"{r.job_name} ({r.job_number})"

    ji_map: dict[str, str] = {}
    if ji_ids:
        q_ji = (
            select(
                JobItem.id,
                JobItem.sub_item_code,
                JobItem.staff_grade_description,
                Worksite.job_name,
                Worksite.job_number,
            )
            .join(Worksite, Worksite.id == JobItem.worksite_id)
            .where(JobItem.id.in_(ji_ids))
        )
        for r in (await session.execute(q_ji)).all():
            desc = r.staff_grade_description or r.sub_item_code or "Shift"
            ji_map[str(r.id)] = f"{r.job_name} ({r.job_number}) - {desc}"

    acc_map: dict[str, str] = {}
    if acc_ids:
        q_acc = select(Accommodation.id, Accommodation.name, Accommodation.code).where(
            Accommodation.id.in_(acc_ids)
        )
        for r in (await session.execute(q_acc)).all():
            acc_map[str(r.id)] = f"{r.name} ({r.code})"

    user_map: dict[str, str] = {}
    if user_ids:
        q_usr = select(User.id, User.username, User.role).where(
            User.id.in_(user_ids)
        )
        for r in (await session.execute(q_usr)).all():
            user_map[str(r.id)] = f"{r.username} ({r.role})"

    enriched: list[AuditLogRead] = []
    for log in logs:
        entity_label: str | None = None
        str_eid = str(log.entity_id)
        if str_eid in emp_map:
            entity_label = emp_map[str_eid]
        elif str_eid in ws_map:
            entity_label = ws_map[str_eid]
        elif str_eid in ji_map:
            entity_label = ji_map[str_eid]
        elif str_eid in acc_map:
            entity_label = acc_map[str_eid]
        elif str_eid in user_map:
            entity_label = user_map[str_eid]

        diff_labels: dict[str, str] = {}
        if isinstance(log.diff, dict):
            for k, v in log.diff.items():
                str_v = str(v)
                if str_v in emp_map:
                    diff_labels[k] = emp_map[str_v]
                elif str_v in ji_map:
                    diff_labels[k] = ji_map[str_v]
                elif str_v in ws_map:
                    diff_labels[k] = ws_map[str_v]
                elif str_v in acc_map:
                    diff_labels[k] = acc_map[str_v]
                elif str_v in user_map:
                    diff_labels[k] = user_map[str_v]

        if not entity_label and isinstance(log.diff, dict):
            e_label = diff_labels.get("employee_id")
            j_label = diff_labels.get("job_item_id") or diff_labels.get("worksite_id")
            if e_label and j_label:
                entity_label = f"{e_label} @ {j_label}"
            elif e_label:
                entity_label = e_label

        actor_name: str | None = None
        if log.actor_user_id and str(log.actor_user_id) in user_map:
            actor_name = user_map[str(log.actor_user_id)]

        item = AuditLogRead.model_validate(log).model_copy(
            update={
                "entity_label": entity_label,
                "diff_labels": diff_labels,
                "actor_name": actor_name,
            }
        )
        enriched.append(item)

    return enriched


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs(
    actor_user_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> list[AuditLogRead]:
    logs = await AuditService.list_logs(
        session=session,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        offset=offset,
    )
    return await enrich_audit_logs(logs, session)
