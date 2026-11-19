from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime, date
import uuid
from .user import User
from .employee import Employee

class AttendanceStatus(str, Enum):
    present = "Present"
    absent = "Absent"
    leave = "On Leave"
    wfh = "Work from Home"
    duty = "On Duty"

class Attendance(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID = Field(index=True, foreign_key="employee.id")
    employee: Optional["Employee"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Attendance.employee_id]"})
    attendance_date: date = Field(index=True)
    status: AttendanceStatus = Field(index=True)
    in_time: datetime | None = Field(default=None)
    out_time: datetime | None = Field(default=None)
    working_hours: float | None = Field(default=0)
    leave_application_id: uuid.UUID | None = Field(default=None, foreign_key="leave_application.id")
    leave_application: Optional["LeaveApplication"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Attendance.leave_application_id]"})
    employee_shift_id: uuid.UUID | None = Field(default=None, foreign_key="employee_shift.id")
    employee_shift: Optional["EmployeeShift"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Attendance.employee_shift_id]"})
    attendance_request_id: uuid.UUID | None = Field(default=None, foreign_key="attendance_request.id")
    attendance_request: Optional["AttendanceRequest"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Attendance.attendance_request_id]"})
    events: list["AttendanceEvent"] = Relationship(back_populates="attendance", sa_relationship_kwargs={"foreign_keys": "[AttendanceEvent.attendance_id]"})
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Attendance.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Attendance.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)