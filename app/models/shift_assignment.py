from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid

class ShiftAssignment(SQLModel, table=True):
    __tablename__ = "shift_assignment"
    employee_id: uuid.UUID | None = Field(default=None, foreign_key="employee.id", primary_key=True)
    shift_id: uuid.UUID | None = Field(default=None, foreign_key="employee_shift.id", primary_key=True)
    # employee: "Employee" = Relationship(back_populates="shifts")
    # shift: "EmployeeShift" = Relationship(back_populates="employees")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[ShiftAssignment.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[ShiftAssignment.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)