from sqlmodel import Field, SQLModel
from datetime import datetime
import uuid

class Organization(SQLModel, table=True):
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    organization_name: str # user organization
    logo: str
    address: str
    created_at: str | None  = Field(default_factory=datetime.now)
    updated_at: str | None  = Field(default_factory=datetime.now)