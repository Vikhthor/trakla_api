from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import MaintenanceSchedule, MaintenanceScheduleStatus, MaintenanceScheduleType, \
    MaintenanceSchedulePriority, MaintenanceScheduleAssigneeType, User, OrderItem, AssetType
from ..utils import FilterParams, get_current_user

class MaintenanceScheduleFilterParams(FilterParams):
    organization_id: UUID

class MaintenanceItems(BaseModel):
    item_name: str
    currency: str | None = None
    quantity: float
    unit_price: float

class MaintenanceScheduleModel(BaseModel):
    model_config = {"extra": "forbid"}
    customer_id: UUID | None = None
    address: str | None = None
    address_geolocation: str | None = None
    status: MaintenanceScheduleStatus | None = "Active"
    organization_id: UUID
    maintenance_type: MaintenanceScheduleType | None = "Preventive"
    subject: str
    description: str
    priority: MaintenanceSchedulePriority | None = "Low"
    asset_type_id: UUID | str | None = None
    instructions: str | None = None
    assignee_type: MaintenanceScheduleAssigneeType | None = "Technician"
    assignee_id: UUID | None = None
    require_pow: bool | None = None
    currency: str
    labour_cost: float
    tax: float
    maintenance_items: list[MaintenanceItems]
    interval: int
    interval_unit: str
    next_schedule_date: str
    end_date: str | None = None
    reminder_days_before: str

class MaintenanceScheduleUpdateModel(BaseModel):
    model_config = {"extra": "forbid"}
    customer_id: UUID | None = None
    address: str | None = None
    address_geolocation: str | None = None
    status: MaintenanceScheduleStatus | None = "Active"
    organization_id: UUID
    maintenance_type: MaintenanceScheduleType | None = "Preventive"
    subject: str
    description: str
    priority: MaintenanceSchedulePriority | None = "Low"
    asset_type_id: UUID | None = None
    instructions: str | None = None
    assignee_type: MaintenanceScheduleAssigneeType | None = "Technician"
    assignee_id: UUID | None = None
    require_pow: bool | None = None
    currency: str
    labour_cost: float
    tax: float
    maintenance_items: list[MaintenanceItems]
    interval: int
    interval_unit: str
    next_schedule_date: str
    end_date: str | None = None
    reminder_days_before: str

router = APIRouter(
    prefix="/v1/maintenance-schedules",
    tags=["maintenance-schedules"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Maintenance schedule not found"}},
)

@router.get("/{schedule_id}")
async def get_maintenance_schedule(
    schedule_id: Annotated[UUID, Path(title="The ID of the schedule to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single maintenance schedule
    """
    schedule = db.get(MaintenanceSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Maintenance schedule not found")
    resp_data = {
        **schedule.model_dump(),
        "assignee": schedule.assignee,
        "customer_name": schedule.customer.customer_name,
        "maintenance_items": schedule.maintenance_items,
        "created_by": schedule.created_by
    }
    return resp_data

@router.get("/")
async def get_maintenance_schedules(
    filter_query: Annotated[MaintenanceScheduleFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered maintenance schedule
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(MaintenanceSchedule).offset(offset).limit(limit)
    schedules = db.exec(statement).all()
    resp_data = [{
        **schedule.model_dump(),
        "assignee": schedule.assignee,
        "customer_name": schedule.customer.customer_name,
        "maintenance_items": schedule.maintenance_items,
        "created_by": schedule.created_by
    } for schedule in schedules]
    return resp_data

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_maintenance_schedule(
    schedule: MaintenanceScheduleModel,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> MaintenanceSchedule:
    """
       Create new maintenance schedule
    """
    schedule_dict = schedule.model_dump(exclude_unset=True)
    maintenance_items = schedule_dict.pop("maintenance_items", []) or []
    asset_type_id = schedule_dict.pop("asset_type_id", None)
    asset_type = None
    if asset_type_id:
        try:
            if(isinstance(asset_type_id, str)):
                asset_type_id = UUID(asset_type_id)
            asset_type = db.get(AssetType, asset_type_id)
        except ValueError:
            asset_type = AssetType(
                asset_type_name = asset_type_id,
                organization_id = current_user.organization_id
            )
    schedule_dict.update({
        "asset_type": asset_type,
        "owner_id": current_user.id,
        "modifier_id": current_user.id,
        "created_at": str(datetime.now()),
        "updated_at": str(datetime.now())
    })
    new_schedule = MaintenanceSchedule(**schedule_dict)
    order_items = []
    for itm in maintenance_items:
        order_items.append(OrderItem(
            item_name = itm.get("item_name"),
            currency = itm.get("currency") or schedule_dict.get("currency"),
            quantity = itm.get("quantity"),
            unit_price = itm.get("unit_price"),
            total_cost = itm.get("quantity") * itm.get("unit_price"),
            organization_id = current_user.organization_id
        ))
    new_schedule.maintenance_items = order_items
    db.add(new_schedule)
    db.commit()
    db.refresh(new_schedule)
    return new_schedule

@router.put("/{schedule_id}", status_code=status.HTTP_200_OK)
async def update_order_item(
    schedule_id: Annotated[UUID, Path(title="The ID of the order schedule to update")],
    schedule: MaintenanceScheduleUpdateModel,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> MaintenanceSchedule:
    """
        Update existing maintenance schedule
    """
    current_schedule = db.get(MaintenanceSchedule, schedule_id)
    if not current_schedule:
        raise HTTPException(status_code=404, detail="Maintenance schedule not found")
    schedule_dict = schedule.model_dump(exclude_unset=True)
    for k, v in schedule_dict.items():
        if k == "maintenance_items":
            current_schedule.maintenance_items = []
            for itm in v:
                current_schedule.maintenance_items.append(
                    OrderItem(
                        item_name = itm.get("item_name"),
                        currency = itm.get("currency") or schedule_dict.get("currency"),
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
                    if(isinstance(v, str)):
                        v = UUID(v)
                    asset_type = db.get(AssetType, v)
                except ValueError:
                    asset_type = AssetType(
                        asset_type_name = v,
                        organization_id = current_user.organization_id
                    )
            current_schedule.sqlmodel_update({"asset_type": asset_type})
            continue
        current_schedule.sqlmodel_update({k: v})
    current_schedule.modifier_id = current_user.id
    current_schedule.updated_at = str(datetime.now())
    db.add(current_schedule)
    db.commit()
    db.refresh(current_schedule)
    return current_schedule

@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: Annotated[UUID, Path(title="The ID of the schedule to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing schedule
    """
    current_schedule = db.get(MaintenanceSchedule, schedule_id)
    if not current_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if current_schedule.organization_id != current_user.organization_id:
        return
    db.delete(current_schedule)
    db.commit()
    return