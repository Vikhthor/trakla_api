from sqlmodel import Field, SQLModel
from enum import Enum
from datetime import datetime
import uuid

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
    address: str | None = None
    address_geolocation: str | None = None
    status: MaintenanceScheduleStatus  = Field(default="Active")
    organization_id: uuid.UUID = Field(default=None, index=True, foreign_key="organization.id")
    maintenance_type: MaintenanceScheduleType = Field(default="Preventive")
    subject: str
    description: str
    priority: MaintenanceSchedulePriority = Field(default="Low")
    asset_type_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="asset_type.id")
    instructions: str | None = None
    assignee_type: MaintenanceScheduleAssigneeType = Field(default="Technician")
    assignee_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    currency: str
    labour_cost: float
    tax: float
    interval: int
    interval_unit: str
    next_schedule_date: str
    reminder_days_before: str # comma separated integers
    # bill_of_material - See BOM item
    created_at: str | None  = Field(default_factory=datetime.now)
    updated_at: str | None  = Field(default_factory=datetime.now)