from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .user import User
from .shift_assignment import ShiftAssignment

class EmployeeGender(str, Enum):
    male = "Male"
    female = "Female"

class EmployeeStatus(str, Enum):
    active = "Active"
    inactive = "Inactive"

class Employee(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    first_name: str
    last_name: str | None = Field(default=None)
    full_name: str = Field(index=True)
    email: str | None = Field(default=None, unique=True)
    phone: str | None = Field(default=None, unique=True)
    gender: EmployeeGender | None  = Field(default=None)
    address: str | None = Field(default=None)
    image: "File" = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": (
                "and_(Employee.id == foreign(File.record_id), "
                "File.record_type == 'Employee', "
                "File.record_field == 'image')"
            ),
            "viewonly": True
        }
    )
    designation: str | None = Field(default=None)
    department_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="department.id")
    department: Optional["Department"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Employee.department_id]"})
    is_department_head: bool | None = Field(default=False)
    supervisor_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="employee.id")
    supervisor: Optional["Employee"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Employee.supervisor_id]"})
    shifts: list["EmployeeShift"] = Relationship(
        back_populates="employees", 
        link_model=ShiftAssignment,
        sa_relationship_kwargs={
            "primaryjoin": "Employee.id == ShiftAssignment.employee_id",
            "secondaryjoin": "EmployeeShift.id == ShiftAssignment.shift_id",
        }
    )
    status: EmployeeStatus | None = "Active"
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Employee.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Employee.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)