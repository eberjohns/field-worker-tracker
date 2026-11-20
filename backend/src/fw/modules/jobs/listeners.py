"""Jobs module domain-event listeners."""

from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.events import EmployeeProfileChanged, event_bus
from fw.modules.jobs.service import JobsService


async def handle_employee_profile_changed(
    event: EmployeeProfileChanged, session: AsyncSession
) -> None:
    """A supervisor who is deactivated or loses the SUPERVISOR role leaves their worksites (DEC-57)."""
    if session is None:
        return
    await JobsService.end_assignments_for_ineligible_supervisors(
        session, employee_id=event.employee_id, actor_role="SYSTEM"
    )


_registered = False


def register_jobs_listeners() -> None:
    global _registered
    if not _registered:
        event_bus.subscribe_sync(EmployeeProfileChanged, handle_employee_profile_changed)
        _registered = True
