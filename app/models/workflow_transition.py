from sqlmodel import Field, SQLModel, Relationship
from typing import Optional
from enum import Enum
from datetime import datetime
import uuid
from .workflow import Workflow
from .workflow_state import WorkflowState
from .user_role import UserRole
from .user import User

class WorkflowTransition(SQLModel, table=True):
    __tablename__ = "workflow_transition"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workflow_state_id: uuid.UUID = Field(foreign_key="workflow_state.id")
    workflow_state: WorkflowState = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkflowTransition.workflow_state_id]"})
    workflow_action: str
    next_workflow_state_id: uuid.UUID | None = Field(default=None, foreign_key="workflow_state.id")
    next_workflow_state: WorkflowState | None = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkflowTransition.next_workflow_state_id]"})
    allowed_role_id: uuid.UUID | None = Field(default=None, foreign_key="user_role.id")
    allowed_role: UserRole | None = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkflowTransition.allowed_role_id]"})
    allow_self_approval: bool = Field(default=False)
    send_email_to_creator: bool = Field(default=False)
    condition: str #TODO:Python eval string
    workflow_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="workflow.id")
    workflow: Workflow | None = Relationship(back_populates="workflow_transitions")
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkflowTransition.owner_id]"})
    created_at: str | None  = Field(default_factory=datetime.now)
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[WorkflowTransition.modifier_id]"})
    updated_at: str | None  = Field(default_factory=datetime.now)