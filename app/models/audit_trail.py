# https://www.1771technologies.com/docs/intro-getting-started https://www.shad-table.dev/ 
from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .user import User

class AuditTrail(SQLModel, table=True):
    __tablename__ = "audit_trail"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    record_type: str
    record_id: uuid.UUID
    change: str
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[AuditTrail.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[AuditTrail.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)