from sqlmodel import Field, SQLModel, Relationship
from typing import Optional
from enum import Enum
from datetime import datetime, date
import uuid
from .user import User
from .budget import Budget
from .budget_item import BudgetItem
from .recurring_transaction import RecurringTransaction

class BudgetTransactionStatus(str, Enum):
    pending = "Pending"
    paid = "Paid"

class BudgetTransaction(SQLModel, table=True):
    __tablename__ = "budget_transaction"
    # id: int | None = Field(default=None, primary_key=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    description: str
    debit_amount: float | None = Field(default=0)
    credit_amount: float | None = Field(default=0)
    budget_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="budget.id")
    budget: Optional[Budget] = Relationship(sa_relationship_kwargs={"foreign_keys": "[BudgetTransaction.budget_id]"})
    budget_item_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="budget_item.id")
    budget_item: Optional[BudgetItem] = Relationship(sa_relationship_kwargs={"foreign_keys": "[BudgetTransaction.budget_item_id]"})
    status: BudgetTransactionStatus | None = "Paid"
    party_type: str | None = None
    party_id: uuid.UUID | None = None
    attachments: list["File"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": (
                "and_(BudgetTransaction.id == foreign(File.record_id), "
                "File.record_type == 'Budget Transaction', "
                "File.record_field == 'attachments')"
            ),
            "viewonly": True,
            "uselist": True,
        }
    )
    due_date: date | None = Field(default=None)
    payment_date: date | None = Field(default=None)
    recurring_txn_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="recurring_transaction.id")
    recurring_txn: Optional["RecurringTransaction"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[BudgetTransaction.recurring_txn_id]"})
    organization_id: uuid.UUID | None  = Field(default=None, index=True, foreign_key="organization.id")
    created_at: datetime | None  = Field(default_factory=datetime.now)
    owner_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    created_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[BudgetTransaction.owner_id]"})
    modifier_id: uuid.UUID | None = Field(default=None, index=True, foreign_key="user.id")
    updated_by: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[BudgetTransaction.modifier_id]"})
    updated_at: datetime | None  = Field(default_factory=datetime.now)