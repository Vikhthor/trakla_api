from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime, date
import uuid
from .user import User
from .order_item import OrderItem
from .asset_type import AssetType
from .customer import Customer

class MaintenanceScheduleStatus(str, Enum):
    active = "Active"
    paused = "Paused"
    completed = "Completed"

class MaintenanceScheduleType(str, Enum):
    preventive = "Preventive"
    corrective = "Corrective"
    predictive = "Predictive"
    routine = "Routine"
    emergency = "Emergency"
    inspection = "Inspection"
    repair = "Repair"
    replacement = "Replacement"
    calibration = "Calibration"

class MaintenanceSchedulePriority(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"
    critical = "Critical"

class MaintenanceScheduleAssigneeType(str, Enum):
    technician = "Technician"

class MaintenanceSchedule(SQLModel, table=True):
    __tablename__ = "maintenance_schedule"
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    customer_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="customer.id")
    customer: Customer | None = Relationship(sa_relationship_kwargs={"foreign_keys": "[MaintenanceSchedule.customer_id]"})
    address: str | None = None
    address_geolocation: str | None = None
    status: MaintenanceScheduleStatus  = Field(default="Active")
    organization_id: uuid.UUID = Field(default=None, index=True, foreign_key="organization.id")
    maintenance_type: MaintenanceScheduleType = Field(default="Preventive")
    subject: str
    description: str
    priority: MaintenanceSchedulePriority = Field(default="Low")
    asset_type_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="asset_type.id")
    asset_type: AssetType | None = Relationship(sa_relationship_kwargs={"foreign_keys": "[MaintenanceSchedule.asset_type_id]"})
    instructions: str | None = None
    assignee_type: MaintenanceScheduleAssigneeType = Field(default="Technician")
    assignee_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    assignee: User | None = Relationship(sa_relationship_kwargs={"foreign_keys": "[MaintenanceSchedule.assignee_id]"})
    require_pow: bool | None = Field(default=False)
    currency: str
    labour_cost: float
    tax: float
    interval: int
    interval_unit: str
    next_schedule_date: date | None = Field(default=None, index=True)
    end_date: str | None = Field(default=None)
    reminder_days_before: str # comma separated integers
    maintenance_items: list[OrderItem] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[OrderItem.schedule_id]"}
    )
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[MaintenanceSchedule.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[MaintenanceSchedule.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)