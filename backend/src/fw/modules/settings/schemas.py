from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CompanySettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    setting_key: str
    country: str | None
    value: Any
    unit: str | None
    effective_from: date
    effective_to: date | None
    created_at: datetime


class CompanySettingUpdate(BaseModel):
    value: Any
    country: str | None = None
    effective_from: date | None = None
    unit: str | None = None


class TimeRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    country: str | None
    scope_type: str
    scope_employee_id: UUID | None
    applies_to: str
    start_date: date
    end_date: date | None
    accommodation_start: time | None
    first_site_start: time | None
    break_minutes: int | None
    last_site_end: time | None
    accommodation_end: time | None
    standard_hours_change_minutes: int | None
    notes: str | None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class TimeRuleCreate(BaseModel):
    name: str
    country: str | None = None
    scope_type: str
    scope_employee_id: UUID | None = None
    applies_to: str = "ALL"
    start_date: date
    end_date: date | None = None
    accommodation_start: time | None = None
    first_site_start: time | None = None
    break_minutes: int | None = None
    last_site_end: time | None = None
    accommodation_end: time | None = None
    standard_hours_change_minutes: int | None = None
    notes: str | None = None


class TimeRuleUpdate(BaseModel):
    version: int
    name: str | None = None
    country: str | None = None
    scope_type: str | None = None
    scope_employee_id: UUID | None = None
    applies_to: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    accommodation_start: time | None = None
    first_site_start: time | None = None
    break_minutes: int | None = None
    last_site_end: time | None = None
    accommodation_end: time | None = None
    standard_hours_change_minutes: int | None = None
    notes: str | None = None
    is_active: bool | None = None


class WinningFieldSourceRead(BaseModel):
    rule_id: UUID | str
    rule_name: str
    scope_type: str
    field_name: str
    value: Any


class MatchedRuleExplanationRead(BaseModel):
    rule_id: UUID | str
    rule_name: str
    scope_type: str
    applies_to: str
    priority_score: float
    is_match: bool
    status: str
    reasons: list[str] = Field(default_factory=list)


class TimeRuleResolveResponse(BaseModel):
    employee_id: UUID
    date: date
    is_outdoor: bool | None
    accommodation_start: time | None
    first_site_start: time | None
    break_minutes: int
    last_site_end: time | None
    accommodation_end: time | None
    planned_total_minutes: int
    planned_worked_minutes: int
    standard_hours_change_minutes: int
    has_accommodation: bool
    winning_rule_id: UUID | str | None
    winning_rule_name: str | None
    winning_sources: dict[str, WinningFieldSourceRead]
    matched_rules: list[MatchedRuleExplanationRead]


class PublicHolidayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    holiday_date: date
    name: str
    country: str
    created_at: datetime


class PublicHolidayCreate(BaseModel):
    holiday_date: date
    name: str
    country: str


class ConsentPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    language: str
    title: str
    body: str
    published_at: datetime
    created_at: datetime


class ConsentPolicyCreate(BaseModel):
    version: int
    language: str
    title: str
    body: str
