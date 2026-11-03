from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="Worker/Employee ID (tally_id)")
    password: str = Field(...)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    username: str
    role: str
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None = None
    version: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool
    user: UserRead


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    version: int


class ResetPasswordResponse(BaseModel):
    message: str
    must_change_password: bool = True
