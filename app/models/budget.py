from sqlmodel import Field, SQLModel, Relationship
from typing import Optional
from datetime import datetime, date
import uuid
from .user import User

class Budget(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    description: str
    start_date: date | None  = Field(default=None)
    end_date: date | None  = Field(default=None)
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    created_at: datetime | None  = Field(default_factory=datetime.now)
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Budget.owner_id]"})
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Budget.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)