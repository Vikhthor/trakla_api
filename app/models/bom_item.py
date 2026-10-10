from sqlmodel import Field, SQLModel
from datetime import datetime
import uuid

class BillOfMaterialItem(SQLModel, table=True):
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    asset_type_name: str
    work_order: str
    maintenance_schedule: str
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    created_at: str | None  = Field(default_factory=datetime.now)
    updated_at: str | None  = Field(default_factory=datetime.now)