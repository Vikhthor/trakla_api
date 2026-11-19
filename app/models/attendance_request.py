from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime, date
import uuid
from .user import User
from .employee import Employee

class AttendanceRequestStatus(str, Enum):
    open = "Open"
    approved = "Approved"
    rejected = "Rejected"
    cancelled = "Cancelled"

class AttendanceRequest(SQLModel, table=True):
    __tablename__ = "attendance_request"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID = Field(index=True, foreign_key="employee.id")
    employee: Optional["Employee"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[AttendanceRequest.employee_id]"})
    from_date: date
    to_date: date
    status: AttendanceRequestStatus | None = Field(default="Open")
    employee_shift_id: uuid.UUID | None = Field(default=None, foreign_key="employee_shift.id")
    employee_shift: Optional["EmployeeShift"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[AttendanceRequest.employee_shift_id]"})
    reason: str | None = Field(default=None)
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[AttendanceRequest.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[AttendanceRequest.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)