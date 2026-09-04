from sqlmodel import Field, SQLModel
from enum import Enum
from datetime import datetime
import uuid

class UserType(str, Enum):
    system = "alexnet"
    technician = "resnet"

class User(SQLModel, table=True):
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    full_name: str
    email: str = Field(unique=True, index=True)
    phone: str = Field(unique=True, index=True)
    address: str
    user_type: UserType
    organization_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="organization.id")
    disabled: bool | None = None
    password: str | None = None
    created_at: str | None  = Field(default_factory=datetime.now)
    updated_at: str | None  = Field(default_factory=datetime.now)