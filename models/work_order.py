from sqlmodel import Field, SQLModel
from enum import Enum
from datetime import datetime
import uuid

class WorkOrderCategory(str, Enum):
    preventive = "Preventive Maintenance"
    predictive = "Predictive Maintenance"
    condition = "Condition-Based Maintenance"
    inspection = "Inspection Request"
    recall = "Recall"
    compliance = "Compliance/Safety"
    repair = "General Repair"
    other = "Other"

class WorkOrderCompletionStatus(str, Enum):
    pending = "Pending"
    partial = "Partially Completed"
    completed = "Fully Completed"

class WorkOrderStatus(str, Enum):
    open = "Open"
    scheduled = "Scheduled"
    assigned = "Assigned"
    in_progress = "In Progress"
    on_hold = "On Hold"
    quality_check = "Quality Check"
    closed = "Closed"
    cancelled = "Cancelled"

class WorkOrderPriority(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"
    critical = "Critical"

class WorkOrderAssigneeType(str, Enum):
    technician = "Technician"

class Currency(str, Enum):
    ngn = "NGN"

class WorkOrder(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    customer_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="customer.id")
    address: str | None = None
    address_geolocation: str | None = None
    status: WorkOrderStatus = "Open"
    organization_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="organization.id")
    subject: str
    description: str
    category: WorkOrderCategory = "Preventive Maintenance"
    priority: WorkOrderPriority = "Low"
    asset_type_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="asset_type.id")
    opening_date: str | None  = Field(default_factory=datetime.now) # read-only. creation date of the order
    closing_date: str # read-only. completion date of the order
    due_date: str # read-only. due date of order
    instructions: str | None = None
    scheduled_date: str # scheduled date accepted by assignee
    actual_date: str # read-only. actual date of order execution
    assignee_type: WorkOrderAssigneeType | None = None
    assignee_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    completion_status: WorkOrderCompletionStatus = "Pending"
    currency: Currency | None = "NGN"
    labour_cost: float | None = None
    tax: float | None = None
    service_request_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="service_request.id")
    maintenance_schedule_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="maintenance_schedule.id")
    created_at: str | None  = Field(default_factory=datetime.now)
    updated_at: str | None  = Field(default_factory=datetime.now)
    # bill_of_materials - See BOM item
