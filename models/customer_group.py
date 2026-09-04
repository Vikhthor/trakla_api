from sqlmodel import Field, SQLModel
from datetime import datetime
import uuid

class CustomerGroup(SQLModel, table=True):
    __tablename__ = "customer_group"
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    group_name: str
    organization_id: int | None  = Field(default=None, index=True, foreign_key="organization.id")
    created_at: str | None  = Field(default_factory=datetime.now)
    updated_at: str | None  = Field(default_factory=datetime.now)