from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .organization import Organization
from .user_roles import UserRoles

class UserType(str, Enum):
    system = "System"
    technician = "Technician"

class User(SQLModel, table=True):
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    first_name: str
    last_name: str
    full_name: str | None = Field(default=None)
    email: str = Field(unique=True, index=True)
    phone: str = Field(unique=True, index=True)
    address: str | None = Field(default=None)
    image: str | None = Field(default=None)
    user_type: UserType
    department_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="department.id")
    department: "Department" = Relationship(back_populates="users", sa_relationship_kwargs={"foreign_keys": "[User.department_id]"})
    roles: list["UserRole"] = Relationship(
        back_populates="users", 
        link_model=UserRoles,
        sa_relationship_kwargs={
            "primaryjoin": "User.id == UserRoles.user_id",
            "secondaryjoin": "UserRole.id == UserRoles.role_id",
        }
    )
    is_online: bool | None = Field(default=False)
    customer_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="customer.id")
    customer: "Customer" = Relationship(back_populates="users", sa_relationship_kwargs={"foreign_keys": "[User.customer_id]"})
    organization_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="organization.id")
    organization: Organization | None = Relationship(back_populates="users", sa_relationship_kwargs={"foreign_keys": "[User.organization_id]"})
    disabled: bool | None = Field(default=None)
    password: str | None = Field(default=None)
    active: bool | None = Field(default=True)
    last_login: str | None  = Field(default=None)
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[User.owner_id]"})
    created_at: str | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[User.modifier_id]"})
    updated_at: str | None  = Field(default_factory=datetime.now)