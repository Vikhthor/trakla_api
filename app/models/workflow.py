from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .user import User

class WorkflowType(str, Enum):
    work_order = "Work Order"
    service_request = "Service Request"

class Workflow(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workflow_name: str
    workflow_type: WorkflowType = Field(default="Work Order")
    is_active: bool = Field(default=True)
    send_email_alert: bool = Field(default=True)
    workflow_states: list["WorkflowState"] = Relationship(back_populates="workflow")
    workflow_transitions: list["WorkflowTransition"] = Relationship(back_populates="workflow")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Workflow.owner_id]"})
    created_at: datetime | None = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Workflow.modifier_id]"})
    updated_at: datetime | None = Field(default_factory=datetime.now)