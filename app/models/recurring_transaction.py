from sqlmodel import Field, SQLModel, Relationship
from typing import Optional
from enum import Enum
from datetime import datetime, date
import uuid
from .user import User
from .budget import Budget
from .budget_item import BudgetItem

class RecurringTxnStatus(str, Enum):
    active = "Active"
    paused = "Paused"
    completed = "Completed"

class RecurringTransaction(SQLModel, table=True):
    __tablename__ = "recurring_transaction"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    description: str
    debit_amount: float | None = Field(default=0)
    credit_amount: float | None = Field(default=0)
    budget_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="budget.id")
    budget: Optional[Budget] = Relationship(sa_relationship_kwargs={"foreign_keys": "[RecurringTransaction.budget_id]"})
    budget_item_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="budget_item.id")
    budget_item: Optional[BudgetItem] = Relationship(sa_relationship_kwargs={"foreign_keys": "[RecurringTransaction.budget_item_id]"})
    status: RecurringTxnStatus  = Field(default="Active")
    party_type: str | None = None
    party_id: uuid.UUID | None = None
    interval: int
    interval_unit: str
    next_schedule_date: date | None = Field(default=None, index=True)
    end_date: str | None = Field(default=None)
    reminder_days_before: str | None = Field(default=None) # comma separated integers
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    created_at: datetime | None  = Field(default_factory=datetime.now)
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[RecurringTransaction.owner_id]"})
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[RecurringTransaction.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)