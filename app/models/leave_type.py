from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime, date
import uuid
from .user import User

class LeaveType(SQLModel, table=True):
    __tablename__ = "leave_type"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    description: str | None = Field(default=None)
    include_holiday: bool | None = Field(default=False)
    allow_carry_forward: bool | None = Field(default=False)
    max_leave_days: int | None = Field(default=None)
    max_consecutive_days: int | None = Field(default=None)
    interval: int
    interval_unit: str
    next_allocation_date: date | None = Field(default=None, index=True)
    disabled: bool | None = Field(default=False)
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[LeaveType.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[LeaveType.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)