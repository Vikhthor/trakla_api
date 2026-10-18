from sqlmodel import Field, SQLModel, Relationship
from typing import Optional
from enum import Enum
from datetime import datetime, date
import uuid
from .user import User
from .order_item import OrderItem
from .asset_type import AssetType
from .customer import Customer

class WorkOrderCategory(str, Enum):
    preventive = "Preventive Maintenance"
    predictive = "Predictive Maintenance"
    corrective = "Corrective Maintenance"
    routine = "Routine Maintenance"
    emergency = "Emergency Maintenance"
    condition = "Condition-Based Maintenance"
    inspection = "Inspection Request"
    replacement = "Replacement Request"
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
    completed = "Completed"
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
    __tablename__ = "work_order"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    customer_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="customer.id")
    customer: Customer | None = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkOrder.customer_id]"})
    address: str | None = Field(default=None)
    address_geolocation: str | None = Field(default=None)
    status: WorkOrderStatus = Field(default="Open")
    organization_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="organization.id")
    subject: str
    description: str
    category: WorkOrderCategory = "Preventive Maintenance"
    priority: WorkOrderPriority = "Low"
    asset_type_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="asset_type.id")
    asset_type: AssetType | None = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkOrder.asset_type_id]"})
    opening_date: str | None  = Field(default_factory=datetime.now) # read-only. creation date of the order
    closing_date: str | None = Field(default=None) # read-only. completion date of the order
    due_date: str | None = Field(default=None) # read-only. due date of order
    instructions: str | None = Field(default=None)
    scheduled_date: date | None = Field(default=None, index=True)
    actual_date: str | None = Field(default=None) # read-only. actual date of order execution
    assignee_type: WorkOrderAssigneeType | None = Field(default=None)
    assignee_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    assignee: User | None = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkOrder.assignee_id]"})
    require_pow: bool | None = Field(default=False)
    proof_of_work: list["File"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": (
                "and_(WorkOrder.id == foreign(File.record_id), "
                "File.record_type == 'Work Order', "
                "File.record_field == 'proof_of_work')"
            ),
            "viewonly": True,
            "uselist": True,
        }
    )
    completion_status: WorkOrderCompletionStatus = "Pending"
    workflow_status: str | None = Field(default=None)
    currency: Currency | None = "NGN"
    labour_cost: float | None = Field(default=None)
    tax: float | None = Field(default=None)
    order_items: list[OrderItem] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[OrderItem.work_order_id]"}
    )
    service_request_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="service_request.id")
    maintenance_schedule_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="maintenance_schedule.id")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkOrder.owner_id]"})
    created_at: datetime | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkOrder.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)
    # bill_of_materials - See BOM item
