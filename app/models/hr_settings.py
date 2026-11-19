from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .user import User

class HRSettings(SQLModel, table=True):
    __tablename__ = "hr_settings"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    verify_attendance_location: bool | None = Field(default=False)
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)
    verify_attendance_ip: bool | None = Field(default=False)
    ip_address: str | None = Field(default=None)
    standard_working_hours: int | None = Field(default=None)
    allow_work_from_home: bool | None = Field(default=False)
    organization_id: uuid.UUID | None  = Field(unique=True, default=None, index=True, foreign_key="organization.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[HRSettings.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[HRSettings.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)