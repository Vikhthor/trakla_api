from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .user_roles import UserRoles
from .user import User

class UserRole(SQLModel, table=True):
    __tablename__ = "user_role"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    role_name: str = Field(unique=True, index=True)
    users: list[User] = Relationship(
        back_populates="roles", 
        link_model=UserRoles,
        sa_relationship_kwargs={
            "primaryjoin": "UserRole.id == UserRoles.role_id",
            "secondaryjoin": "User.id == UserRoles.user_id",
        }
    )
    permissions: list["UserPermission"] = Relationship(back_populates="role")
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[UserRole.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[UserRole.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)