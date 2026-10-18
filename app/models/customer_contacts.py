from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid

class CustomerContacts(SQLModel, table=True):
    __tablename__ = "customer_contacts"
    contact_id: uuid.UUID | None = Field(default=None, foreign_key="contact.id", primary_key=True)
    customer_id: uuid.UUID | None = Field(default=None, foreign_key="customer.id", primary_key=True)
    # contact: "Contact" = Relationship(back_populates="customers")
    # customer: "Customer" = Relationship(back_populates="contacts")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[CustomerContacts.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[CustomerContacts.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)