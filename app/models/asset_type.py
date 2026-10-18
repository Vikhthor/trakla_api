from sqlmodel import Field, SQLModel
from datetime import datetime
import uuid

class AssetType(SQLModel, table=True):
    __tablename__ = "asset_type"
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    asset_type_name: str
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    created_at: datetime | None  = Field(default_factory=datetime.now)
    updated_at: datetime | None  = Field(default_factory=datetime.now)