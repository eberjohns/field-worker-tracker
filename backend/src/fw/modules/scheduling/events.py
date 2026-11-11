"""Domain events for scheduling module."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from fw.core.events import DomainEvent


@dataclass(kw_only=True)
class LeaveApprovedEvent(DomainEvent):
    leave_id: UUID
    employee_id: UUID
    date_from: date
    date_to: date
    worker_name: str
    approved_by_user_id: UUID


@dataclass(kw_only=True)
class LeaveCancelledEvent(DomainEvent):
    leave_id: UUID
    cancelled_by_user_id: UUID


@dataclass(kw_only=True)
class ReassignmentApprovedEvent(DomainEvent):
    reassignment_id: UUID | None = None
    leave_request_id: UUID | None = None
    original_employee_id: UUID | None = None
    approved_by_user_id: UUID | None = None
