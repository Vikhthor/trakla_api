from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .user import User

class Technician(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str | None  = Field(default=None)
    first_name: str
    last_name: str
    full_name: str | None  = Field(default=None)
    email: str = Field(unique=True, index=True)
    phone: str = Field(unique=True, index=True)
    image: "File" = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": (
                "and_(Technician.id == foreign(File.record_id), "
                "File.record_type == 'Technician', "
                "File.record_field == 'image')"
            ),
            "viewonly": True
        }
    )
    address: str | None  = Field(default=None)
    geolocation: str | None  = Field(default=None)
    user_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    user: User | None = Relationship(sa_relationship_kwargs={"foreign_keys": "[Technician.user_id]"})
    organization_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="organization.id")
    rating: float | None = Field(default=None)
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Technician.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Technician.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)