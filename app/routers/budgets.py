from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header, File, UploadFile

from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal, Any
import random
from datetime import datetime, date
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_, func
from ..models import Budget, BudgetItem, BudgetTransaction, RecurringTransaction, User, File as FileUpload, \
    Vendor, Technician, Customer
from ..utils import FilterParams, get_current_user, upload_file, get_datetime, getdate
import sqlalchemy
from sqlalchemy.orm import joinedload, selectinload

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

class BudgetFilterParams(FilterParams):
    organization_id: UUID

class BudgetItemFilterParams(FilterParams):
    organization_id: UUID
    budget_id: UUID

class BudgetModel(BaseModel):
    model_config = {"extra": "forbid"}
    title: str | None = None
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    organization_id: UUID | None

class BudgetItemModel(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = None
    is_category: bool | None = False
    budget_amount: float | None = None
    parent_category_id: UUID | None = None
    budget_id: UUID | None = None
    color: str | None = None
    organization_id: UUID | None

class BudgetTransactionModel(BaseModel):
    model_config = {"extra": "forbid"}
    payment_date: date | None = getdate()
    description: str
    debit_amount: float | None = 0
    credit_amount: float | None = 0
    budget_item_id: UUID | None = None
    budget_id: UUID
    status: str | None = "Paid"
    party_type: str | None = None
    party_id: UUID | None = None
    organization_id: UUID | None

class BudgetTransactionUpdateModel(BaseModel):
    model_config = {"extra": "forbid"}
    payment_date: date | None = getdate()
    description: str | None = None
    debit_amount: float | None = 0
    credit_amount: float | None = 0
    budget_item_id: UUID | None = None
    status: str | None = "Paid"
    party_type: str | None = None
    party_id: UUID | None = None

class RecurringTransactionModel(BaseModel):
    model_config = {"extra": "forbid"}
    description: str | None = None
    debit_amount: float | None = 0
    credit_amount: float | None = 0
    budget_item_id: UUID | None = None
    budget_id: UUID | None = None
    party_type: str | None = None
    party_id: UUID | None = None
    status: str | None = None
    interval: int
    interval_unit: str
    next_schedule_date: str
    end_date: str | None =  None
    reminder_days_before: str | None = None
    organization_id: UUID | None

class RecurringTransactionUpdateModel(RecurringTransactionModel):
    model_config = {"extra": "forbid"}
    interval: int | None = None
    interval_unit: str | None = None
    next_schedule_date: str | None = None

router = APIRouter(
    prefix="/v1/budgets",
    tags=["budgets"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Budget not found"}},
)

#### Budget Item Endpoints ####

@router.get("/item")
async def get_budget_items(
    filter_query: Annotated[BudgetItemFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered budgets
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(BudgetItem).where(
        BudgetItem.budget_id == filter_query.budget_id,
        BudgetItem.organization_id == current_user.organization_id
    ).offset(offset).limit(limit).options(selectinload(BudgetItem.created_by))
    budget_items = db.exec(statement).all()
    items = [{
        **budget_item.model_dump(),
        "created_by": budget_item.created_by
    } for budget_item in budget_items]

    budget_txns = db.exec(
        select(BudgetTransaction).where(
            BudgetTransaction.budget_id == filter_query.budget_id,
            BudgetTransaction.status == "Paid"
        )
    ).all()

    nodes = {row["id"]: {
        **row,
        "children": [],
        "actual_amount": sum([txn.debit_amount for txn in budget_txns if txn.budget_item_id == row["id"]]) - sum([txn.credit_amount for txn in budget_txns if txn.budget_item_id == row["id"]]),
        "balance": 0
    } for row in items}
    roots: list[dict[str, Any]] = []
    for row in items:
        node = nodes[row["id"]]
        parent = nodes.get(row.get("parent_category_id"))   # None if no parent or parent not found
        if parent is not None and parent is not node:
            parent["budget_amount"] += node.get("budget_amount")
            parent["actual_amount"] += node.get("actual_amount")
            parent["balance"] += (node.get("budget_amount") - node.get("actual_amount"))
            parent["children"].append(node)
        else:
            roots.append(node)

    return roots
    # return resp_data

@router.post("/item", status_code=status.HTTP_201_CREATED)
async def create_budget_item(
    budget_item: BudgetItemModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> BudgetItem:
    """
       Create new budget
    """
    item = BudgetItem(
        name = budget_item.name,
        is_category = budget_item.is_category,
        budget_amount = budget_item.budget_amount if not budget_item.is_category else 0,
        parent_category_id = budget_item.parent_category_id,
        budget_id = budget_item.budget_id,
        color = budget_item.color,
        organization_id = budget_item.organization_id or current_user.organization_id,
        owner_id=current_user.id,
        modifier_id=current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.put("/item/{item_id}", status_code=status.HTTP_200_OK)
async def update_budget_item(
    item_id: Annotated[UUID, Path(title="The ID of the budget item to update")],
    budget_item: BudgetItemModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Budget:
    """
        Update existing budget
    """
    current_budget = db.get(BudgetItem, item_id)
    if not current_budget:
        raise HTTPException(status_code=404, detail="Budget item not found")
    if current_budget.organization_id != current_user.organization_id:
        return current_budget
    budget_dict = budget_item.model_dump(exclude_unset=True)
    for k, v in budget_dict.items():
        if k == 'organization_id':
            continue
        current_budget.sqlmodel_update({k: v})

    if current_budget.is_category:
        current_budget.budget_amount = 0
    current_budget.updated_at = get_datetime()
    current_budget.modifier_id = current_user.id
    db.add(current_budget)
    db.commit()
    db.refresh(current_budget)
    return current_budget

@router.delete("/item/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget_item(
    item_id: Annotated[UUID, Path(title="The ID of the budget item to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing budget
    """
    current_budget = db.get(BudgetItem, item_id)
    if not current_budget:
        raise HTTPException(status_code=404, detail="Budget Item not found")
    if current_budget.organization_id != current_user.organization_id:
        return
    db.delete(current_budget)
    db.commit()
    return

#### Budget Transaction Endpoints ####

party_models = {
    "Vendor": Vendor,
    "Facility": Customer,
    "Technician": Technician
}
def get_party_name(txn, db, current_user):
    if not (txn.party_type and txn.party_id):
        return
    party_model = party_models.get(txn.party_type)
    if not party_model:
        return
    
    party = db.exec(select(party_model).where(
        party_model.id == txn.party_id,
        party_model.organization_id == current_user.organization.id
    )).first()
    if party:
        if txn.party_type == "Vendor":
            return party.vendor_name
        elif txn.party_type == "Facility":
            return party.customer_name
        elif txn.party_type == "Technician":
            return party.full_name

@router.get("/transaction")
async def get_budget_transactions(
    filter_query: Annotated[BudgetItemFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered budget transactions
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(BudgetTransaction).where(
        BudgetTransaction.budget_id == filter_query.budget_id,
        BudgetTransaction.organization_id == current_user.organization_id
    ).offset(offset).limit(limit).options(selectinload(BudgetTransaction.created_by))
    budget_txns = db.exec(statement).all()

    resp_data = [{
        **budget_txn.model_dump(),
        "budget_item": budget_txn.budget_item,
        "attachments": budget_txn.attachments,
        "party_name": get_party_name(budget_txn, db, current_user),
        "created_by": budget_txn.created_by
    } for budget_txn in budget_txns]
    return resp_data

@router.post("/transaction", status_code=status.HTTP_201_CREATED)
async def create_budget_transaction(
    budget_transaction: BudgetTransactionModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> BudgetTransaction:
    """
       Create new budget transaction
    """
    txn = BudgetTransaction(
        payment_date = budget_transaction.payment_date,
        description = budget_transaction.description,
        debit_amount = budget_transaction.debit_amount,
        credit_amount = budget_transaction.credit_amount,
        status = budget_transaction.status,
        budget_item_id = budget_transaction.budget_item_id,
        budget_id = budget_transaction.budget_id,
        party_type = budget_transaction.party_type,
        party_id = budget_transaction.party_id,
        organization_id = budget_transaction.organization_id or current_user.organization_id,
        owner_id=current_user.id,
        modifier_id=current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn

@router.put("/transaction/{txn_id}", status_code=status.HTTP_200_OK)
async def update_budget_transaction(
    txn_id: Annotated[UUID, Path(title="The ID of the budget transaction to update")],
    budget_txn: BudgetTransactionUpdateModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> BudgetTransaction:
    """
        Update existing budget
    """
    current_budget_txn = db.get(BudgetTransaction, txn_id)
    if not current_budget_txn:
        raise HTTPException(status_code=404, detail="Budget transaction not found")
    if current_budget_txn.organization_id != current_user.organization_id:
        return current_budget_txn
    budget_txn_dict = budget_txn.model_dump(exclude_unset=True)
    for k, v in budget_txn_dict.items():
        if k == 'organization_id':
            continue
        current_budget_txn.sqlmodel_update({k: v})
    
    current_budget_txn.updated_at = get_datetime()
    current_budget_txn.modifier_id = current_user.id
    db.add(current_budget_txn)
    db.commit()
    db.refresh(current_budget_txn)
    return current_budget_txn

@router.put("/transaction/upload-attachments/{txn_id}", status_code=status.HTTP_200_OK)
async def upload_attachments(
    txn_id: Annotated[UUID, Path(title="The ID of the work order to update")],
    attachments: list[UploadFile],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
    Upload attachments
    """
    attachment_files = []
    for file in attachments:
        # if file.content_type not in ALLOWED_TYPES:
        #     raise HTTPException(status_code=415, detail="Unsupported file type")
        file_data = upload_file(file)
        attachment_files.append(file_data)

    current_txn = db.get(BudgetTransaction, txn_id)
    if not current_txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    for file in attachment_files:
        file_upload = FileUpload(
            file_name = file.get("filename"),
            file_type = file.get("file_type"),
            file_size = file.get("file_size"),
            formated_size = file.get("formated_size"),
            file_url = file.get("url"),
            record_type = "Budget Transaction",
            record_id = current_txn.id,
            record_field = "attachments",
            owner_id = current_user.id
        )
        db.add(file_upload)

    current_txn.updated_at = get_datetime()
    current_txn.modifier_id = current_user.id
    db.add(current_txn)
    db.commit()
    db.refresh(current_txn)
    return current_txn

@router.delete("/transaction/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget_transaction(
    txn_id: Annotated[UUID, Path(title="The ID of the budget transaction to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing budget
    """
    current_budget_txn = db.get(BudgetTransaction, txn_id)
    if not current_budget_txn:
        raise HTTPException(status_code=404, detail="Budget transaction not found")
    if current_budget_txn.organization_id != current_user.organization_id:
        return
    db.delete(current_budget_txn)
    db.commit()
    return

#### Recurring Transaction Endpoints ####

@router.get("/recurring")
async def get_recurring_transactions(
    filter_query: Annotated[BudgetItemFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered recurring transactions
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(RecurringTransaction).where(
        RecurringTransaction.budget_id == filter_query.budget_id,
        RecurringTransaction.organization_id == current_user.organization_id
    ).offset(offset).limit(limit).options(selectinload(RecurringTransaction.created_by))
    recurring_txns = db.exec(statement).all()
    resp_data = [{
        **recurring_txn.model_dump(),
        "budget_item": recurring_txn.budget_item,
        "party_name": get_party_name(recurring_txn, db, current_user),
        "created_by": recurring_txn.created_by
    } for recurring_txn in recurring_txns]
    return resp_data

@router.post("/recurring", status_code=status.HTTP_201_CREATED)
async def create_recurring_transaction(
    recurring_transaction: RecurringTransactionModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> RecurringTransaction:
    """
       Create new recurring transaction
    """
    txn = RecurringTransaction(
        description = recurring_transaction.description,
        debit_amount = recurring_transaction.debit_amount,
        credit_amount = recurring_transaction.credit_amount,
        budget_item_id = recurring_transaction.budget_item_id,
        budget_id = recurring_transaction.budget_id,
        status = recurring_transaction.status,
        party_type = recurring_transaction.party_type,
        party_id = recurring_transaction.party_id,
        interval = recurring_transaction.interval,
        interval_unit = recurring_transaction.interval_unit,
        next_schedule_date = getdate(recurring_transaction.next_schedule_date),
        end_date = recurring_transaction.end_date,
        reminder_days_before = recurring_transaction.reminder_days_before,
        organization_id = recurring_transaction.organization_id or current_user.organization_id,
        owner_id=current_user.id,
        modifier_id=current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn

@router.put("/recurring/{txn_id}", status_code=status.HTTP_200_OK)
async def update_recurring_transaction(
    txn_id: Annotated[UUID, Path(title="The ID of the recurring transaction to update")],
    recurring_txn: RecurringTransactionUpdateModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> BudgetTransaction:
    """
        Update existing recurring transaction
    """
    current_recurring_txn = db.get(RecurringTransaction, txn_id)
    if not current_recurring_txn:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    if current_recurring_txn.organization_id != current_user.organization_id:
        return current_recurring_txn
    recurring_txn_dict = recurring_txn.model_dump(exclude_unset=True)
    for k, v in recurring_txn_dict.items():
        if k == 'organization_id':
            continue
        if k == "next_schedule_date" and v:
            v = getdate(v)
        current_recurring_txn.sqlmodel_update({k: v})
    
    current_recurring_txn.updated_at = get_datetime()
    current_recurring_txn.modifier_id = current_user.id
    db.add(current_recurring_txn)
    db.commit()
    db.refresh(current_recurring_txn)
    return current_recurring_txn

@router.delete("/recurring/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurring_transaction(
    txn_id: Annotated[UUID, Path(title="The ID of the recurring transaction to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing recurring transaction
    """
    current_recurring_txn = db.get(RecurringTransaction, txn_id)
    if not current_recurring_txn:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    if current_recurring_txn.organization_id != current_user.organization_id:
        return
    db.delete(current_recurring_txn)
    db.commit()
    return

#### Budget Details Endpoints ####

@router.get("/{budget_id}")
async def get_budget(
    budget_id: Annotated[UUID, Path(title="The ID of the budget to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single budget
    """
    budget = db.exec(select(Budget).where(
        Budget.id == budget_id,
        Budget.organization_id == current_user.organization.id
    )).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget

@router.get("/")
async def get_budgets(
    filter_query: Annotated[BudgetFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered budgets
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(Budget).where(
        Budget.organization_id == current_user.organization_id
    ).offset(offset).limit(limit).options(selectinload(Budget.created_by))
    budgets = db.exec(statement).all()

    total_budget_amount = db.exec(
        select(func.sum(BudgetItem.budget_amount))\
            .join(Budget)\
            .where(
                Budget.id == BudgetItem.budget_id,
                BudgetItem.is_category == 0
            )
    ).one()
    total_spent_amount = db.exec(
        select(func.sum(BudgetTransaction.debit_amount)-func.sum(BudgetTransaction.credit_amount))\
            .join(Budget)\
            .where(
                Budget.id == BudgetTransaction.budget_id,
                BudgetTransaction.status == "Paid"
            )
    ).one()

    resp_data = [{
        **budget.model_dump(),
        "total_budget_amount": total_budget_amount,
        "total_spent_amount": total_spent_amount,
        "status": "Active" if get_datetime() <= get_datetime(budget.end_date) else "Completed",
        "created_by": budget.created_by
    } for budget in budgets]
    return resp_data

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_budget(
    budget: BudgetModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Budget:
    """
       Create new budget
    """
    budget = Budget(
        title = budget.title,
        description = budget.description,
        start_date = budget.start_date,
        end_date = budget.end_date,
        organization_id = budget.organization_id or current_user.organization_id,
        owner_id=current_user.id,
        modifier_id=current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    try:
        db.add(budget)
        db.commit()
        db.refresh(budget)
        return budget
    except sqlalchemy.exc.IntegrityError as e:
        # e.args => ('(sqlite3.IntegrityError) UNIQUE constraint failed: budget.phone',)
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}: {budget.model_dump().get('phone')}"
        ) from e

@router.put("/{budget_id}", status_code=status.HTTP_200_OK)
async def update_budget(
    budget_id: Annotated[UUID, Path(title="The ID of the budget to update")],
    budget: BudgetModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Budget:
    """
        Update existing budget
    """
    current_budget = db.get(Budget, budget_id)
    if not current_budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if current_budget.organization_id != current_user.organization_id:
        return current_budget
    budget_dict = budget.model_dump(exclude_unset=True)
    for k, v in budget_dict.items():
        if k == 'organization_id':
            continue
        current_budget.sqlmodel_update({k: v})
    
    current_budget.updated_at = get_datetime()
    current_budget.modifier_id = current_user.id
    db.add(current_budget)
    db.commit()
    db.refresh(current_budget)
    return current_budget

@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: Annotated[UUID, Path(title="The ID of the budget to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing budget
    """
    current_budget = db.get(Budget, budget_id)
    if not current_budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if current_budget.organization_id != current_user.organization_id:
        return
    db.delete(current_budget)
    db.commit()
    return
