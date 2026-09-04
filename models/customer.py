from sqlmodel import Field, SQLModel
from datetime import datetime
import uuid

class Customer(SQLModel, table=True):
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    customer_name: str
    email: str
    phone: str
    address: str
    address_geolocation: str | None = None # geojson
    group_id: int | None  = Field(default=None, index=True, foreign_key="customer_group.id")
    organization_id: int | None  = Field(default=None, index=True, foreign_key="organization.id")
    created_at: str | None  = Field(default_factory=datetime.now)
    updated_at: str | None  = Field(default_factory=datetime.now)