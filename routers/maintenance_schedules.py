from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import MaintenanceSchedule, MaintenanceScheduleStatus, MaintenanceScheduleType, MaintenanceSchedulePriority, MaintenanceScheduleAssigneeType
from ..utils import FilterParams

class MaintenanceScheduleFilterParams(FilterParams):
    organization_id: UUID

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
    asset_type_id: UUID | None = None
    instructions: str | None = None
    assignee_type: MaintenanceScheduleAssigneeType | None = "Technician"
    assignee_id: UUID | None = None
    currency: str
    labour_cost: float
    tax: float
    interval: int
    interval_unit: str
    next_schedule_date: str
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
    currency: str
    labour_cost: float
    tax: float
    interval: int
    interval_unit: str
    next_schedule_date: str
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
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single maintenance schedule
    """
    schedule = db.get(MaintenanceSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Maintenance schedule not found")
    return schedule

@router.get("/")
async def get_maintenance_schedules(
    filter_query: Annotated[MaintenanceScheduleFilterParams, Query()],
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
    return schedules

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_maintenance_schedule(
    schedule: MaintenanceScheduleModel,
    db: Annotated[Session, Depends(get_db)]
) -> MaintenanceSchedule:
    """
       Create new maintenance schedule
    """
    schedule_dict = schedule.model_dump(exclude_unset=True)
    new_schedule = MaintenanceSchedule(**schedule_dict)
    db.add(new_schedule)
    db.commit()
    db.refresh(new_schedule)
    return new_schedule

@router.put("/{schedule_id}", status_code=status.HTTP_200_OK)
async def update_order_item(
    schedule_id: Annotated[UUID, Path(title="The ID of the order schedule to update")],
    schedule: MaintenanceScheduleUpdateModel,
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
        current_schedule[k] = v
    current_schedule.updated_at = str(datetime.now())
    db.add(current_schedule)
    db.commit()
    db.refresh(current_schedule)
    return current_schedule
