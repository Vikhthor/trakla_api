from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import WorkOrder, WorkOrderStatus, WorkOrderCategory, WorkOrderPriority, WorkOrderAssigneeType, WorkOrderCompletionStatus, Currency
from ..utils import FilterParams

class WorkOrderFilterParams(FilterParams):
    organization_id: UUID

class WorkOrderModel(BaseModel):
    model_config = {"extra": "forbid"}
    customer_id: UUID | None = None
    address: str | None = None
    address_geolocation: str | None = None
    status: WorkOrderStatus | None = "Open"
    organization_id: UUID
    subject: str
    description: str
    category: WorkOrderCategory = "Preventive Maintenance"
    priority: WorkOrderPriority = "Low"
    asset_type_id: UUID | None = None
    due_date: str
    instructions: str | None = None
    assignee_type: WorkOrderAssigneeType | None = None
    assignee_id: UUID | None = None
    completion_status: WorkOrderCompletionStatus = "Pending"
    currency: Currency | None = "NGN"
    labour_cost: float | None = None
    tax: float | None = None
    service_request_id: UUID | None = None

class WorkOrderUpdateModel(BaseModel):
    model_config = {"extra": "forbid"}
    subject: str | None = None
    description: str
    status: WorkOrderStatus | None = None
    customer_id: UUID | None = None
    address: str | None = None
    address_geolocation: str | None = None
    status: WorkOrderStatus = "Open"
    category: WorkOrderCategory = "Preventive Maintenance"
    priority: WorkOrderPriority = "Low"
    asset_type_id: UUID | None = None
    due_date: str
    instructions: str | None = None
    assignee_type: WorkOrderAssigneeType | None = None
    assignee_id: UUID | None = None
    completion_status: WorkOrderCompletionStatus = "Pending"
    currency: Currency | None = "NGN"
    labour_cost: float | None = None
    tax: float | None = None
    service_request_id: UUID | None = None

router = APIRouter(
    prefix="/v1/work-orders",
    tags=["work-orders"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Work order not found"}},
)

@router.get("/{order_id}")
async def get_work_order(
    order_id: Annotated[UUID, Path(title="The ID of the work order to get")],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single work order
    """
    order = db.get(WorkOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found")
    return order

@router.get("/")
async def get_work_orders(
    filter_query: Annotated[WorkOrderFilterParams, Query()],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered work orders
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(WorkOrder).offset(offset).limit(limit)
    orders = db.exec(statement).all()
    return orders

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_work_order(
    work_order: WorkOrderModel, 
    db: Annotated[Session, Depends(get_db)]
) -> WorkOrder:
    """
       Create new work order
    """
    if work_order.assignee_id and work_order.status == "Open":
        work_order.status = "Assigned"
    order = WorkOrder(
        customer_id = work_order.customer_id,
        address = work_order.address,
        address_geolocation = work_order.address_geolocation,
        status = work_order.status,
        organization_id = work_order.organization_id,
        subject = work_order.subject,
        description = work_order.description,
        category = work_order.category,
        priority = work_order.priority,
        asset_type_id = work_order.asset_type_id,
        due_date = work_order.due_date,
        instructions = work_order.instructions,
        assignee_type = work_order.assignee_type,
        assignee_id = work_order.assignee_id,
        completion_status = work_order.completion_status,
        currency = work_order.currency,
        labour_cost = work_order.labour_cost,
        tax = work_order.tax,
        service_request_id = work_order.service_request_id
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

@router.put("/{order_id}", status_code=status.HTTP_200_OK)
async def update_work_order(
    order_id: Annotated[int, Path(title="The ID of the work order to update")],
    service_request: WorkOrderUpdateModel, 
    db: Annotated[Session, Depends(get_db)]
) -> WorkOrder:
    """
        Update existing work order
    """
    current_order = db.get(WorkOrder, order_id)
    if not current_order:
        raise HTTPException(status_code=404, detail="Work order not found")
    req_dict = service_request.model_dump(exclude_unset=True)
    for k, v in req_dict.items():
        if k == "status":
            if v == "Scheduled" and current_order.status != "Scheduled":
                current_order.scheduled_date = str(datetime.now())
            elif v == "Closed" and current_order.status != "Closed":
                current_order.closing_date = str(datetime.now())
            elif v == "In Progress" and current_order.status != "In Progress":
                current_order.actual_date = str(datetime.now())
        current_order[k] = v

    if current_order.status == "Open" and current_order.assignee_id:
        current_order.status = "Assigned"

    current_order.updated_at = str(datetime.now())
    db.add(current_order)
    db.commit()
    db.refresh(current_order)
    return current_order
