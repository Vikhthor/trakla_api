from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .user import User
from .vendor_contacts import VendorContacts
from .customer_contacts import CustomerContacts

class ContactGender(str, Enum):
    male = "Male"
    female = "Female"

class Contact(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str | None  = Field(default=None)
    first_name: str
    last_name: str | None  = Field(default=None)
    full_name: str | None  = Field(default=None)
    email: str = Field(index=True)
    phone: str = Field(index=True)
    gender: ContactGender | None  = Field(default=None)
    image: "File" = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": (
                "and_(Contact.id == foreign(File.record_id), "
                "File.record_type == 'Contact', "
                "File.record_field == 'image')"
            ),
            "viewonly": True
        }
    )
    role: str | None  = Field(default=None)
    address: str | None  = Field(default=None)
    user_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    vendors: list["Vendor"] = Relationship(back_populates="contacts", link_model=VendorContacts)
    customers: list["Customer"] = Relationship(back_populates="contacts", link_model=CustomerContacts)
    organization_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="organization.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Contact.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Contact.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)