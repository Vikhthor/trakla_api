from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .user import User

class ServiceRequestStatus(str, Enum):
    open = "Open"
    closed = "Closed"
    resolved = "Resolved"

class ServiceRequest(SQLModel, table=True):
    __tablename__ = "service_request"
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    subject: str
    description: str
    user_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="user.id")
    customer_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="customer.id")
    organization_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="organization.id")
    status: ServiceRequestStatus = Field(default='Open')
    rating: float | None = Field(default=None)
    workflow_status: str | None  = Field(default=None)
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[ServiceRequest.owner_id]"})
    created_at: str | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[ServiceRequest.modifier_id]"})
    updated_at: str | None  = Field(default_factory=datetime.now)