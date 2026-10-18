from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid

class UserRoles(SQLModel, table=True):
    __tablename__ = "user_roles"
    user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", primary_key=True)
    role_id: uuid.UUID | None = Field(default=None, foreign_key="user_role.id", primary_key=True)
    # user: "User" = Relationship(back_populates="roles")
    # role: "UserRole" = Relationship(back_populates="users")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[UserRoles.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[UserRoles.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)