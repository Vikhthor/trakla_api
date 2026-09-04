from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import OrderItem
from ..utils import FilterParams

class OrderItemFilterParams(FilterParams):
    organization_id: UUID

class OrderItemModel(BaseModel):
    model_config = {"extra": "forbid"}
    item_name: str
    organization_id: UUID

class OrderItemUpdateModel(BaseModel):
    model_config = {"extra": "forbid"}
    item_name: str
    organization_id: UUID

router = APIRouter(
    prefix="/v1/order-items",
    tags=["order-items"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Order item not found"}},
)

@router.get("/{item_id}")
async def get_order_item(
    item_id: Annotated[UUID, Path(title="The ID of the item to get")],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single item
    """
    order_item = db.get(OrderItem, item_id)
    if not order_item:
        raise HTTPException(status_code=404, detail="Order item not found")
    return order_item

@router.get("/")
async def get_order_items(
    filter_query: Annotated[OrderItemFilterParams, Query()],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered order item
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(OrderItem).offset(offset).limit(limit)
    order_items = db.exec(statement).all()
    return order_items

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_order_item(
    order_item: OrderItemModel,
    db: Annotated[Session, Depends(get_db)]
) -> OrderItem:
    """
       Create new order item
    """
    order_itm = OrderItem(
        item_name = order_item.item_name,
        organization_id = order_item.organization_id
    )
    db.add(order_itm)
    db.commit()
    db.refresh(order_itm)
    return order_itm

@router.put("/{item_id}", status_code=status.HTTP_200_OK)
async def update_order_item(
    item_id: Annotated[UUID, Path(title="The ID of the order item to update")],
    order_item: OrderItemUpdateModel, 
    db: Annotated[Session, Depends(get_db)]
) -> OrderItem:
    """
        Update existing order item
    """
    current_item = db.get(OrderItem, item_id)
    if not current_item:
        raise HTTPException(status_code=404, detail="Order item not found")
    item_dict = order_item.model_dump(exclude_unset=True)
    for k, v in item_dict.items():
        current_item[k] = v
    current_item.updated_at = str(datetime.now())
    db.add(current_item)
    db.commit()
    db.refresh(current_item)
    return current_item
