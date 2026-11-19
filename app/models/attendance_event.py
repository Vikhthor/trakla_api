from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .user import User

class AttendanceEventType(str, Enum):
    checkin = "In"
    checkout = "Out"

class AttendanceEvent(SQLModel, table=True):
    __tablename__ = "attendance_event"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID = Field(index=True, foreign_key="employee.id")
    employee: Optional["Employee"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[AttendanceEvent.employee_id]"})
    event_type: AttendanceEventType
    event_time: datetime
    attendance_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="attendance.id")
    attendance: "Attendance" = Relationship(back_populates="events", sa_relationship_kwargs={"foreign_keys": "[AttendanceEvent.attendance_id]"})
    employee_shift_id: uuid.UUID | None = Field(default=None, foreign_key="employee_shift.id")
    employee_shift: Optional["EmployeeShift"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[AttendanceEvent.employee_shift_id]"})
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[AttendanceEvent.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[AttendanceEvent.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)