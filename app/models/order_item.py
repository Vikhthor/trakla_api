from sqlmodel import Field, SQLModel
from datetime import datetime
import uuid

class OrderItem(SQLModel, table=True):
    __tablename__ = "order_item"
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    item_name: str
    quantity: float
    currency: str
    unit_price: float
    total_cost: float
    work_order_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="work_order.id")
    schedule_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="maintenance_schedule.id")
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    created_at: str | None  = Field(default_factory=datetime.now)
    updated_at: str | None  = Field(default_factory=datetime.now)