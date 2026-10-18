from sqlmodel import Field, SQLModel
from datetime import datetime
import uuid

class OrderCategory(SQLModel, table=True):
    __tablename__ = "order_category"
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    category_name: str
    description: str
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    created_at: datetime | None  = Field(default_factory=datetime.now)
    updated_at: datetime | None  = Field(default_factory=datetime.now)

# Preventive Maintenance | Predictive Maintenance | Condition-Based Maintenance | Inspection Request | Recall | Compliance/Safety | General Repair | Other