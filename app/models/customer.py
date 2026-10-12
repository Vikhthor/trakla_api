from sqlmodel import Field, SQLModel, Relationship
from typing import Optional
from datetime import datetime
import uuid
from .user import User
from .customer_contacts import CustomerContacts

class Customer(SQLModel, table=True):
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    customer_name: str
    email: str | None = Field(default=None)
    phone: str | None = Field(default=None)
    address: str | None = Field(default=None)
    address_geolocation: str | None = Field(default=None)
    group_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="customer_group.id")
    group: "CustomerGroup" = Relationship(sa_relationship_kwargs={"foreign_keys": "[Customer.group_id]"})
    primary_contact_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="contact.id")
    primary_contact: "Contact" = Relationship(sa_relationship_kwargs={"foreign_keys": "[Customer.primary_contact_id]"})
    contacts: list["Contact"] = Relationship(back_populates="customers", link_model=CustomerContacts)
    users: list[User] = Relationship(back_populates="customer", sa_relationship_kwargs={"foreign_keys": "[User.customer_id]"})
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Customer.owner_id]"})
    created_at: str | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Customer.modifier_id]"})
    updated_at: str | None  = Field(default_factory=datetime.now)