from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from fw.core.db import ModelBase


class LookupValue(ModelBase):
    """A value of a managed list (DEC-60): staff types and grade codes.

    Added on screen (Admin, Engineer), deactivated by Admin, never deleted. ``value_key`` is the
    case- and space-insensitive form used for uniqueness.
    """

    __tablename__ = "lookup_values"
    __table_args__ = (
        UniqueConstraint("list_key", "value_key", name="uq_lookup_values_list_key_value_key"),
        CheckConstraint(
            "list_key IN ('staff_grade_description', 'grade_code')",
            name="ck_lookup_values_list_key",
        ),
        CheckConstraint(
            "source IN ('SEED', 'SCREEN', 'IMPORT', 'REVISION')", name="ck_lookup_values_source"
        ),
        Index("ix_lookup_values_list_key_active", "list_key", "is_active"),
    )

    list_key: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    value_key: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="SCREEN")
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
