from sqlmodel import Field, SQLModel, Relationship
from typing import Optional
from datetime import datetime
import uuid
from .user import User
from .budget import Budget

class BudgetItem(SQLModel, table=True):
    __tablename__ = "budget_item"
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    is_category: bool | None = Field(default=False)
    budget_amount: float | None = Field(default=0)
    parent_category_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="budget_item.id")
    parent_category: Optional["BudgetItem"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[BudgetItem.parent_category_id]"})
    budget_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="budget.id")
    budget: Optional[Budget] = Relationship(sa_relationship_kwargs={"foreign_keys": "[BudgetItem.budget_id]"})
    color: str | None = Field(default=None)
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    created_at: datetime | None  = Field(default_factory=datetime.now)
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[BudgetItem.owner_id]"})
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[BudgetItem.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)