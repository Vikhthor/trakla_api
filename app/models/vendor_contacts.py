from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid

class VendorContacts(SQLModel, table=True):
    __tablename__ = "vendor_contacts"
    contact_id: uuid.UUID | None = Field(default=None, foreign_key="contact.id", primary_key=True)
    vendor_id: uuid.UUID | None = Field(default=None, foreign_key="vendor.id", primary_key=True)
    # contact: "Contact" = Relationship(back_populates="vendors")
    # vendor: "Vendor" = Relationship(back_populates="contacts")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[VendorContacts.owner_id]"})
    created_at: str | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[VendorContacts.modifier_id]"})
    updated_at: str | None  = Field(default_factory=datetime.now)