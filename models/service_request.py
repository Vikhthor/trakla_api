from sqlmodel import Field, SQLModel
from enum import Enum
from datetime import datetime
import uuid

class ServiceRequestStatus(str, Enum):
    open = "Open"
    closed = "Closed"
    resolved = "Resolved"

class ServiceRequest(SQLModel, table=True):
    __tablename__ = "service_request"
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    subject: str
    customer_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="customer.id")
    status: ServiceRequestStatus = Field(default='Open')
    created_at: str | None  = Field(default_factory=datetime.now)
    updated_at: str | None  = Field(default_factory=datetime.now)