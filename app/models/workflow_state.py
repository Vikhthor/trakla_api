from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from .workflow import Workflow
from .user import User

class WorkflowStateStyle(str, Enum):
    primary = "Primary"
    info = "Info"
    success = "Success"
    warning = "Warning"
    danger = "Danger"
    inverse = "Inverse"

class WorkflowState(SQLModel, table=True):
    __tablename__ = "workflow_state"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workflow_state_name: str
    style: WorkflowStateStyle | None  = Field(default=None)
    workflow_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="workflow.id")
    workflow: Workflow | None = Relationship(back_populates="workflow_states")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkflowState.owner_id]"})
    created_at: str | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkflowState.modifier_id]"})
    updated_at: str | None  = Field(default_factory=datetime.now)