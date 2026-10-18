from sqlmodel import Field, SQLModel, Relationship
from typing import Optional
from datetime import datetime
import uuid

class Organization(SQLModel, table=True):
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    organization_name: str # user organization
    brand_icon: "File" = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": (
                "and_(Organization.id == foreign(File.record_id), "
                "File.record_type == 'Organization', "
                "File.record_field == 'brand_icon')"
            ),
            "viewonly": True
        }
    )
    logo: "File" = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": (
                "and_(Organization.id == foreign(File.record_id), "
                "File.record_type == 'Organization', "
                "File.record_field == 'logo')"
            ),
            "viewonly": True
        }
    )
    email: str | None = Field(default=None)
    phone: str | None = Field(default=None)
    address: str
    city: str | None = Field(default=None)
    state: str | None = Field(default=None)
    country: str
    subscription_plan: str | None = Field(default=None)
    users: list["User"] = Relationship(back_populates="organization", sa_relationship_kwargs={"foreign_keys": "[User.organization_id]"})
    enable_2fa: bool | None = Field(default=False)
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Organization.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Organization.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)