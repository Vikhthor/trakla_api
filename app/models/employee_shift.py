from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime, time
import uuid
from .user import User
from .shift_assignment import ShiftAssignment

class EmployeeShift(SQLModel, table=True):
    __tablename__ = "employee_shift"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shift_name: str = Field(index=True)
    start_time: time
    end_time: time
    color: str | None = Field(default=None)
    interval: int
    interval_unit: str
    repeat_days: str | None = Field(default=None)
    disabled: bool | None = Field(default=False)
    employees: list["Employee"] = Relationship(
        back_populates="shifts", 
        link_model=ShiftAssignment,
        sa_relationship_kwargs={
            "primaryjoin": "EmployeeShift.id == ShiftAssignment.shift_id",
            "secondaryjoin": "Employee.id == ShiftAssignment.employee_id",
        }
    )
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[EmployeeShift.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[EmployeeShift.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)