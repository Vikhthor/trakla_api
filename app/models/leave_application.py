from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime, date
import uuid
from .user import User

class LeaveApplicationStatus(str, Enum):
    open = "Open"
    approved = "Approved"
    rejected = "Rejected"
    cancelled = "Cancelled"

class LeaveApplication(SQLModel, table=True):
    __tablename__ = "leave_application"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID = Field(index=True, foreign_key="employee.id")
    employee: Optional["Employee"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[LeaveApplication.employee_id]"})
    leave_type_id: uuid.UUID = Field(index=True, foreign_key="leave_type.id")
    leave_type: Optional["LeaveType"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[LeaveApplication.leave_type_id]"})
    from_date: date
    to_date: date
    is_half_day: bool | None = Field(default=False)
    half_day_date: date | None = Field(default=None)
    description: str | None = Field(default=None)
    leave_balance: float
    status: LeaveApplicationStatus | None = Field(default="Open")
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[LeaveApplication.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[LeaveApplication.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)