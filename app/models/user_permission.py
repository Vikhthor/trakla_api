from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .user_role import UserRole
from .user import User

class UserPermission(SQLModel, table=True):
    __tablename__ = "user_permission"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    resource: str
    can_read: bool | None = False
    can_write: bool | None = False
    can_create: bool | None = False
    can_delete: bool | None = False
    policy: str | None = None
    role_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user_role.id")
    role: UserRole | None = Relationship(back_populates="permissions")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[UserPermission.owner_id]"})
    created_at: str | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[UserPermission.modifier_id]"})
    updated_at: str | None  = Field(default_factory=datetime.now)