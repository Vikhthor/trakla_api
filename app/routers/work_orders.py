from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from math import asin, cos, radians, sin, sqrt
from geopy.distance import geodesic
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import WorkOrder, WorkOrderStatus, WorkOrderCategory, WorkOrderPriority, \
    WorkOrderAssigneeType, WorkOrderCompletionStatus, Currency, User, OrderItem, AssetType
from ..utils import FilterParams, get_current_user

EARTH_RADIUS_M = 6_371_000  # mean Earth radius in meters

class WorkOrderFilterParams(FilterParams):
    organization_id: UUID

class OrderItems(BaseModel):
    item_name: str
    currency: str | None = None
    quantity: float
    unit_price: float

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
    asset_type_id: UUID | str | None = None
    scheduled_date: str | None = None
    due_date: str | None = None
    instructions: str | None = None
    assignee_type: WorkOrderAssigneeType | None = None
    assignee_id: UUID | None = None
    require_pow: bool | None = None
    completion_status: WorkOrderCompletionStatus = "Pending"
    currency: Currency | None = "NGN"
    labour_cost: float | None = None
    tax: float | None = None
    order_items: list[OrderItems]
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
    scheduled_date: str | None = None
    due_date: str | None = None
    instructions: str | None = None
    assignee_type: WorkOrderAssigneeType | None = None
    assignee_id: UUID | None = None
    require_pow: bool | None = None
    proof_of_work: str | None = None
    completion_status: WorkOrderCompletionStatus = "Pending"
    currency: Currency | None = "NGN"
    labour_cost: float | None = None
    tax: float | None = None
    order_items: list[OrderItems]
    service_request_id: UUID | None = None

router = APIRouter(
    prefix="/v1/work-orders",
    tags=["work-orders"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Work order not found"}},
)

def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))

# lagos = (6.5244, 3.3792)   # (lat, lon)
# abuja = (9.0765, 7.3986)
# d = geodesic(lagos, abuja)
# print(d.meters)
# See also geopy.distance.great_circle

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
    resp_data = {
        **order.model_dump(),
        "customer_name": order.customer.customer_name,
        "assignee": order.assignee,
        "order_items": order.order_items,
        "created_by": order.created_by
    }
    return resp_data

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
    resp_data = [{
        **order.model_dump(),
        "customer_name": order.customer.customer_name,
        "assignee": order.assignee,
        "order_items": order.order_items,
        "created_by": order.created_by
    } for order in orders]
    return resp_data

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_work_order(
    work_order: WorkOrderModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> WorkOrder:
    """
       Create new work order
    """
    if work_order.assignee_id and work_order.status == "Open":
        work_order.status = "Assigned"

    asset_type = None
    if work_order.asset_type_id:
        try:
            asset_type_id = work_order.asset_type_id
            if(isinstance(work_order.asset_type_id, str)):
                asset_type_id = UUID(work_order.asset_type_id)
            asset_type = db.get(AssetType, asset_type_id)
        except ValueError:
            asset_type = AssetType(
                asset_type_name = work_order.asset_type_id,
                organization_id = current_user.organization_id
            )

    order_items = []
    items = work_order.order_items or []
    for itm in items:
        order_items.append(OrderItem(
            item_name = itm.item_name,
            currency = itm.currency or work_order.currency,
            quantity = itm.quantity,
            unit_price = itm.unit_price,
            total_cost = itm.quantity * itm.unit_price,
            organization_id = current_user.organization_id
        ))

    order = WorkOrder(
        customer_id = work_order.customer_id,
        address = work_order.address,
        address_geolocation = work_order.address_geolocation,
        status = work_order.status,
        organization_id = work_order.organization_id or current_user.organization_id,
        subject = work_order.subject,
        description = work_order.description,
        category = work_order.category,
        priority = work_order.priority,
        asset_type = asset_type,
        scheduled_date = work_order.scheduled_date,
        due_date = work_order.due_date,
        instructions = work_order.instructions,
        assignee_type = work_order.assignee_type,
        assignee_id = work_order.assignee_id,
        require_pow = work_order.require_pow,
        completion_status = work_order.completion_status,
        currency = work_order.currency,
        labour_cost = work_order.labour_cost,
        tax = work_order.tax,
        order_items = order_items,
        service_request_id = work_order.service_request_id,
        owner_id=current_user.id,
        modifier_id=current_user.id,
        created_at=str(datetime.now()),
        updated_at=str(datetime.now())
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

@router.put("/{order_id}", status_code=status.HTTP_200_OK)
async def update_work_order(
    order_id: Annotated[int, Path(title="The ID of the work order to update")],
    service_request: WorkOrderUpdateModel, 
    current_user: Annotated[User, Depends(get_current_user)],
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
        if k == "order_items":
            current_order.order_items = []
            for itm in v:
                current_order.order_items.append(
                    OrderItem(
                        item_name = itm.get("item_name"),
                        currency = itm.get("currency") or req_dict.get("currency"),
                        quantity = itm.get("quantity"),
                        unit_price = itm.get("unit_price"),
                        total_cost = itm.get("quantity") * itm.get("unit_price"),
                        organization_id = current_user.organization_id
                    )
                )
            continue
        if k == "asset_type_id":
            asset_type = None
            if v:
                try:
                    asset_type = db.get(AssetType, UUID(v))
                except ValueError:
                    asset_type = AssetType(
                        asset_type_name = v,
                        organization_id = current_user.organization_id
                    )
            current_order.sqlmodel_update({"asset_type": asset_type})
            continue
        current_order.sqlmodel_update({k: v})

    if current_order.status == "Open" and current_order.assignee_id:
        current_order.status = "Assigned"

    current_order.updated_at = str(datetime.now())
    current_order.modifier_id = current_user.id
    db.add(current_order)
    db.commit()
    db.refresh(current_order)
    return current_order

@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_order(
    order_id: Annotated[UUID, Path(title="The ID of the order to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing work order
    """
    current_order = db.get(WorkOrder, order_id)
    if not current_order:
        raise HTTPException(status_code=404, detail="Work order not found")
    if current_order.organization_id != current_user.organization_id:
        return
    db.delete(current_order)
    db.commit()
    return