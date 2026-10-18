from sqlmodel import Field, SQLModel, Relationship
from typing import Optional
from datetime import datetime
import uuid
from .user import User

class VendorGroup(SQLModel, table=True):
    __tablename__ = "vendor_group"
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    group_name: str
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    created_at: datetime | None  = Field(default_factory=datetime.now)
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[VendorGroup.owner_id]"})
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[VendorGroup.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)