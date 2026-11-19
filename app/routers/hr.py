from fastapi import FastAPI, Request, Query, Path, Depends, HTTPException, status, APIRouter, Header, File, UploadFile
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime, date, time
from math import asin, cos, radians, sin, sqrt
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import Employee, User, File as FileUpload, Attendance, AttendanceRequest, \
    AttendanceEvent, EmployeeHoliday, EmployeeShift, LeaveType, LeaveApplication, \
    HRSettings, UserRole, UserPermission, Department
from ..utils import FilterParams, get_current_user, get_datetime, upload_file, getdate, add_to_date
import sqlalchemy

class EmployeeFilterParams(FilterParams):
    organization_id: UUID
    email: str | None = None

class EmployeeShiftFilterParams(FilterParams):
    organization_id: UUID
    disabled: bool | None = None

class AttendanceFilterParams(FilterParams):
    organization_id: UUID
    from_date: date | None = None
    to_date: date | None = None
    employee_id: UUID | None = None
    attendance_date: date | None = None
    status: str | None = None

class AttendanceEventFilterParams(FilterParams):
    organization_id: UUID
    from_date: date | None = None
    to_date: date | None = None

class LeaveApplicationFilterParams(FilterParams):
    organization_id: UUID
    from_date: date | None = None
    to_date: date | None = None

class ShiftData(BaseModel):
    id: UUID
    shift_name: str | None = None

class EmployeeModel(BaseModel):
    model_config = {"extra": "forbid"}
    first_name: str
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    gender: str | None = None
    image: str | None = None
    status: str | None = None
    designation: str | None = None
    address: str | None = None
    department_id: UUID | None = None
    department_name: str| None = None
    is_department_head: bool | None = False
    supervisor_id: UUID | None = None
    employee_shift_id: UUID | None = None
    organization_id: UUID
    shifts: list[ShiftData] | None = None

class AttendanceModel(BaseModel):
    model_config = {"extra": "forbid"}
    employee_id: UUID
    attendance_date: date
    status: str | None = None
    in_time: datetime | None = None
    out_time: datetime | None = None
    leave_application_id: UUID | None = None
    attendance_request_id: UUID | None = None
    employee_shift_id: UUID | None = None
    organization_id: UUID

class AttendanceRequestModel(BaseModel):
    model_config = {"extra": "forbid"}
    employee_id: UUID
    from_date: date
    to_date: date
    reason: str | None = None
    status: str | None = None
    employee_shift_id: UUID | None = None
    organization_id: UUID

class AttendanceEventModel(BaseModel):
    model_config = {"extra": "forbid"}
    employee_id: UUID
    event_type: str
    event_time: datetime
    attendance_id: UUID | None = None
    employee_shift_id: UUID | None = None
    latitude: float | None = None
    longitude: float | None = None
    organization_id: UUID

class EmployeeHolidayModel(BaseModel):
    model_config = {"extra": "forbid"}
    title: str
    description: str | None = None
    start_date: date
    end_date: date
    organization_id: UUID

class EmployeeShiftModel(BaseModel):
    model_config = {"extra": "forbid"}
    shift_name: str = Field(unique=True, index=True)
    start_time: time
    end_time: time
    color: str | None = None
    interval: int
    interval_unit: str
    repeat_days: str | None = None
    disabled: bool | None = False
    employees: list[UUID] | None = None
    organization_id: UUID

class LeaveTypeModel(BaseModel):
    model_config = {"extra": "forbid"}
    name: str
    description: str | None = None
    include_holiday: bool | None = False
    allow_carry_forward: bool | None = False
    max_leave_days: int | None = None
    max_consecutive_days: int | None = None
    interval: int
    interval_unit: str
    next_allocation_date: date
    disabled: bool | None = False
    organization_id: UUID

class LeaveApplicationModel(BaseModel):
    model_config = {"extra": "forbid"}
    employee_id: UUID
    leave_type_id: UUID
    from_date: date
    to_date: date
    is_half_day: bool | None = False
    half_day_date: date | None = None
    description: str | None = None
    status: str | None = None
    organization_id: UUID

class HRSettingsModel(BaseModel):
    model_config = {"extra": "forbid"}
    verify_attendance_location: bool | None = False
    latitude: float | None = None
    longitude: float | None = None
    verify_attendance_ip: bool | None = False
    ip_address: str | None = None
    standard_working_hours: int | None = None
    allow_work_from_home: bool | None = False
    organization_id: UUID

router = APIRouter(
    prefix="/v1/hr",
    tags=["hr"],
    responses={404: {"description": "Employee not found"}},
)

##### HR Settings Endpoints #####

@router.get("/settings/{settings_id}")
async def get_hr_settings(
    settings_id: Annotated[UUID, Path(title="The ID of the settings to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single settings
    """
    settings = db.exec(select(HRSettings).where(
        HRSettings.id == settings_id,
        HRSettings.organization_id == current_user.organization.id
    )).first()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return settings

@router.get("/settings")
async def get_organization_settings(
    filter_query: Annotated[EmployeeFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered hr settings
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(HRSettings).where(
        HRSettings.organization_id == current_user.organization_id
    ).offset(offset).limit(limit)
    settings = db.exec(statement).first()
    resp_data = {}
    if settings:
        resp_data = {
            **settings.model_dump(),
            "created_by": settings.created_by
        }
    return resp_data

@router.post("/settings", status_code=status.HTTP_201_CREATED)
async def create_hr_settings(
    settings: HRSettingsModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> HRSettings:
    """
       Create new HR settings
    """
    new_settings = HRSettings(
        verify_attendance_location = settings.verify_attendance_location,
        latitude = settings.latitude,
        longitude = settings.longitude,
        verify_attendance_ip = settings.verify_attendance_ip,
        ip_address = settings.ip_address,
        standard_working_hours = settings.standard_working_hours,
        allow_work_from_home = settings.allow_work_from_home,
        organization_id = settings.organization_id or current_user.organization_id,
        owner_id = current_user.id,
        modifier_id = current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    try:
        db.add(new_settings)
        db.commit()
        db.refresh(new_settings)
        return new_settings
    except sqlalchemy.exc.IntegrityError as e:
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}"
        ) from e
    return new_settings

@router.put("/settings", status_code=status.HTTP_200_OK)
async def update_organization_settings(
    settings: HRSettingsModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> HRSettings:
    """
        Update existing HR settings
    """
    statement = select(HRSettings).where(
        HRSettings.organization_id == current_user.organization_id
    )
    current_settings = db.exec(statement).first()
    if not current_settings:
        new_settings = HRSettings(
            verify_attendance_location = settings.verify_attendance_location,
            latitude = settings.latitude,
            longitude = settings.longitude,
            verify_attendance_ip = settings.verify_attendance_ip,
            ip_address = settings.ip_address,
            standard_working_hours = settings.standard_working_hours,
            allow_work_from_home = settings.allow_work_from_home,
            organization_id = settings.organization_id or current_user.organization_id,
            owner_id = current_user.id,
            modifier_id = current_user.id,
            created_at=get_datetime(),
            updated_at=get_datetime()
        )
        db.add(new_settings)
        db.commit()
        db.refresh(new_settings)
        return new_settings

    if current_settings.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="HR settings not found")
    
    settings_dict = settings.model_dump(exclude_unset=True)
    for k, v in settings_dict.items():
        if k == 'organization_id':
            continue
        current_settings.sqlmodel_update({k: v})
    
    current_settings.updated_at = get_datetime()
    current_settings.modifier_id = current_user.id
    db.add(current_settings)
    db.commit()
    db.refresh(current_settings)
    return current_settings

@router.put("/settings/{settings_id}", status_code=status.HTTP_200_OK)
async def update_hr_settings(
    settings_id: Annotated[UUID, Path(title="The ID of the HR settings to update")],
    settings: HRSettingsModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> HRSettings:
    """
        Update existing HR settings
    """
    current_settings = db.get(HRSettings, settings_id)
    if not current_settings or current_settings.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="HR settings not found")
    settings_dict = settings.model_dump(exclude_unset=True)
    for k, v in settings_dict.items():
        if k == 'organization_id':
            continue
        current_settings.sqlmodel_update({k: v})
    
    current_settings.updated_at = get_datetime()
    current_settings.modifier_id = current_user.id
    db.add(current_settings)
    db.commit()
    db.refresh(current_settings)
    return current_settings

##### Leave Application Endpoints #####

@router.get("/leave/{leave_id}")
async def get_leave_application(
    leave_id: Annotated[UUID, Path(title="The ID of the leave to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single leave application
    """
    leave = db.exec(select(LeaveApplication).where(
        LeaveApplication.id == leave_id,
        LeaveApplication.organization_id == current_user.organization.id
    )).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    return leave

@router.get("/leave")
async def get_leave_applications(
    filter_query: Annotated[LeaveApplicationFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered leave applications
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)

    query_filters = [LeaveApplication.organization_id == current_user.organization_id]
    if filter_query.from_date:
        query_filters.append(getattr(LeaveApplication,"from_date") >= filter_query.from_date)
    if filter_query.to_date:
        query_filters.append(getattr(LeaveApplication,"to_date") <= filter_query.to_date)

    statement = select(LeaveApplication).where(
        *query_filters
    ).offset(offset).limit(limit)
    leave_applications = db.exec(statement).all()
    resp_data = [{
        **leave.model_dump(),
        "leave_type": leave.leave_type,
        "employee": leave.employee,
        "created_by": leave.created_by
    } for leave in leave_applications]
    return resp_data

def validate_leave_application(leave, current_user, db):
    if getdate(leave.from_date) > getdate(leave.to_date):
        raise HTTPException(status_code=400, detail="From date should not be greater than To date")
    
    leave_type = db.exec(select(LeaveType).where(
        LeaveType.id == leave.leave_type_id,
        LeaveType.organization_id == current_user.organization.id
    )).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave type not found")

    leave_days = (getdate(leave.to_date) - getdate(leave.from_date)).days
    used_leave_days = leave_days
    remaining_leave_days = 0
    start_date = getdate(leave.from_date)
    allocation_start_date = getdate(leave_type.next_allocation_date)
    allocation_end_date = add_to_date(
        allocation_start_date,
        days=leave_type.interval if leave_type.interval_unit == "Days" else 0,
        weeks=leave_type.interval if leave_type.interval_unit == "Weeks" else 0,
        months=leave_type.interval if leave_type.interval_unit == "Months" else 0,
        years=leave_type.interval if leave_type.interval_unit == "Years" else 0,
    )
    while start_date > allocation_end_date:
        allocation_start_date = allocation_end_date
        allocation_end_date = add_to_date(
            allocation_start_date,
            days=leave_type.interval if leave_type.interval_unit == "Days" else 0,
            weeks=leave_type.interval if leave_type.interval_unit == "Weeks" else 0,
            months=leave_type.interval if leave_type.interval_unit == "Months" else 0,
            years=leave_type.interval if leave_type.interval_unit == "Years" else 0,
        )
    while start_date < allocation_start_date:
        allocation_end_date = allocation_start_date
        allocation_start_date = add_to_date(
            allocation_end_date,
            days=-(leave_type.interval) if leave_type.interval_unit == "Days" else 0,
            weeks=-(leave_type.interval) if leave_type.interval_unit == "Weeks" else 0,
            months=-(leave_type.interval) if leave_type.interval_unit == "Months" else 0,
            years=-(leave_type.interval) if leave_type.interval_unit == "Years" else 0,
        )

    if not leave_type.allow_carry_forward and getdate(leave.to_date) >= allocation_end_date:
        raise HTTPException(status_code=404, detail=f"Leave allocated ends on {allocation_end_date}")

    leave_filters = [
        LeaveApplication.organization_id == current_user.organization_id,
        LeaveApplication.employee_id == leave.employee_id,
        LeaveApplication.status == "Approved",
        LeaveApplication.from_date >= allocation_start_date,
        LeaveApplication.to_date <= allocation_end_date
    ]
    if hasattr(leave, 'id'):
        leave_filters.append(LeaveApplication.id != leave.id)
    
    used_leaves = db.exec(select(LeaveApplication).where(
        *leave_filters
    )).all()

    for employee_leave in used_leaves:
        used_leave_days += (getdate(employee_leave.from_date) - getdate(employee_leave.to_date)).days
    
    if leave_type.max_consecutive_days and leave_days > leave_type.max_consecutive_days:
        raise HTTPException(status_code=400, detail=f"Leave days must not be more than {leave_type.max_consecutive_days} day(s)")
    if leave_type.max_leave_days:
        remaining_leave_days = leave_type.max_leave_days - used_leave_days
        if used_leave_days > leave_type.max_leave_days:
            raise HTTPException(status_code=400, detail=f"Remaining leave days is {remaining_leave_days} day(s)")
    
    return remaining_leave_days

@router.post("/leave", status_code=status.HTTP_201_CREATED)
async def create_leave_application(
    leave: LeaveApplicationModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> LeaveApplication:
    """
       Create new leave application
    """
    leave_balance = validate_leave_application(leave, current_user, db)

    new_leave_application = LeaveApplication(
        employee_id = leave.employee_id,
        leave_type_id = leave.leave_type_id,
        from_date = leave.from_date,
        to_date = leave.to_date,
        is_half_day = leave.is_half_day,
        half_day_date = leave.half_day_date,
        description = leave.description,
        leave_balance = leave_balance,
        status = leave.status,
        organization_id = leave.organization_id or current_user.organization_id,
        owner_id = current_user.id,
        modifier_id = current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    try:
        db.add(new_leave_application)
        db.commit()
        db.refresh(new_leave_application)
        return new_leave_application
    except sqlalchemy.exc.IntegrityError as e:
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}"
        ) from e

@router.put("/leave/{leave_id}", status_code=status.HTTP_200_OK)
async def update_leave_application(
    leave_id: Annotated[UUID, Path(title="The ID of the leave application to update")],
    leave: LeaveApplicationModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> LeaveApplication:
    """
        Update existing leave application
    """
    current_leave_application = db.get(LeaveApplication, leave_id)
    if not current_leave_application:
        raise HTTPException(status_code=404, detail="Leave application not found")
    leave_dict = leave.model_dump(exclude_unset=True)
    for k, v in leave_dict.items():
        if k == 'organization_id':
            continue
        current_leave_application.sqlmodel_update({k: v})

    leave_balance = validate_leave_application(current_leave_application, current_user, db)
    current_leave_application.leave_balance = leave_balance

    current_leave_application.updated_at = get_datetime()
    current_leave_application.modifier_id = current_user.id
    db.add(current_leave_application)
    db.commit()
    db.refresh(current_leave_application)
    return current_leave_application

##### Leave Type Endpoints #####

@router.get("/leave-type/{type_id}")
async def get_leave_type(
    type_id: Annotated[UUID, Path(title="The ID of the leave type to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single leave type
    """
    leave_type = db.exec(select(LeaveType).where(
        LeaveType.id == type_id,
        LeaveType.organization_id == current_user.organization.id
    )).first()
    if not leave_type:
        raise HTTPException(status_code=404, detail="Leave type not found")
    return leave_type

@router.get("/leave-type")
async def get_leave_types(
    filter_query: Annotated[EmployeeFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered leave types
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(LeaveType).where(
        LeaveType.organization_id == current_user.organization_id
    ).offset(offset).limit(limit)
    leave_types = db.exec(statement).all()
    resp_data = [{
        **leave_type.model_dump(),
        "created_by": leave_type.created_by
    } for leave_type in leave_types]
    return resp_data

@router.post("/leave-type", status_code=status.HTTP_201_CREATED)
async def create_leave_type(
    leave_type: LeaveTypeModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> LeaveType:
    """
       Create new leave type
    """
    new_leave_type = LeaveType(
        name = leave_type.name,
        description = leave_type.description,
        include_holiday = leave_type.include_holiday,
        allow_carry_forward = leave_type.allow_carry_forward,
        max_leave_days = leave_type.max_leave_days,
        max_consecutive_days = leave_type.max_consecutive_days,
        interval = leave_type.interval,
        interval_unit = leave_type.interval_unit,
        next_allocation_date = leave_type.next_allocation_date,
        disabled = leave_type.disabled,
        organization_id = leave_type.organization_id or current_user.organization_id,
        owner_id = current_user.id,
        modifier_id = current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    try:
        db.add(new_leave_type)
        db.commit()
        db.refresh(new_leave_type)
        return new_leave_type
    except sqlalchemy.exc.IntegrityError as e:
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}"
        ) from e

@router.put("/leave-type/{type_id}", status_code=status.HTTP_200_OK)
async def update_leave_type(
    type_id: Annotated[UUID, Path(title="The ID of the leave type to update")],
    leave_type: LeaveTypeModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> LeaveType:
    """
        Update existing leave type
    """
    current_leave_type = db.get(LeaveType, type_id)
    if not current_leave_type:
        raise HTTPException(status_code=404, detail="Leave type not found")
    leave_type_dict = leave_type.model_dump(exclude_unset=True)
    for k, v in leave_type_dict.items():
        if k == 'organization_id':
            continue
        current_leave_type.sqlmodel_update({k: v})
    
    current_leave_type.updated_at = get_datetime()
    current_leave_type.modifier_id = current_user.id
    db.add(current_leave_type)
    db.commit()
    db.refresh(current_leave_type)
    return current_leave_type


##### Shift Endpoints #####

@router.get("/shift/{shift_id}")
async def get_shift(
    shift_id: Annotated[UUID, Path(title="The ID of the shift to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single shift
    """
    shift = db.exec(select(EmployeeShift).where(
        EmployeeShift.id == shift_id,
        EmployeeShift.organization_id == current_user.organization.id
    )).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift

@router.get("/shift")
async def get_shifts(
    filter_query: Annotated[EmployeeShiftFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered shifts
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)

    query_filters = [EmployeeShift.organization_id == current_user.organization_id]
    if filter_query.disabled is not None:
        query_filters.append(getattr(EmployeeShift,"disabled") == filter_query.disabled)
    
    statement = select(EmployeeShift).where(
        EmployeeShift.organization_id == current_user.organization_id
    ).offset(offset).limit(limit)
    shifts = db.exec(statement).all()
    resp_data = [{
        **shift.model_dump(),
        "employees": shift.employees,
        "created_by": shift.created_by
    } for shift in shifts]
    return resp_data

@router.post("/shift", status_code=status.HTTP_201_CREATED)
async def create_shift(
    shift: EmployeeShiftModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> EmployeeShift:
    """
       Create new shift
    """
    employees = []
    if shift.employees:
        for employee_id in shift.employees:
            employee = db.exec(select(Employee).where(
                Employee.id == employee_id,
                Employee.organization_id == current_user.organization.id
            )).first()
            if employee:
                employees.append(employee)
    
    new_shift = EmployeeShift(
        shift_name = shift.shift_name,
        start_time = shift.start_time,
        end_time = shift.end_time,
        color = shift.color,
        interval = shift.interval,
        interval_unit = shift.interval_unit,
        repeat_days = shift.repeat_days,
        disabled = shift.disabled,
        employees=employees,
        organization_id = shift.organization_id or current_user.organization_id,
        owner_id = current_user.id,
        modifier_id = current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    try:
        db.add(new_shift)
        db.commit()
        db.refresh(new_shift)
        return new_shift
    except sqlalchemy.exc.IntegrityError as e:
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}"
        ) from e

@router.put("/shift/{shift_id}", status_code=status.HTTP_200_OK)
async def update_shift(
    shift_id: Annotated[UUID, Path(title="The ID of the shift to update")],
    shift: EmployeeShiftModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> EmployeeShift:
    """
        Update existing shift
    """
    current_shift = db.get(EmployeeShift, shift_id)
    if not current_shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    shift_dict = shift.model_dump(exclude_unset=True)
    for k, v in shift_dict.items():
        if k == 'organization_id':
            continue
        if k == 'employees':
            employees = []
            if v:
                for employee_id in v:
                    employee = db.exec(select(Employee).where(
                        Employee.id == employee_id,
                        Employee.organization_id == current_user.organization.id
                    )).first()
                    if employee:
                        employees.append(employee)
            v = employees
        current_shift.sqlmodel_update({k: v})
    
    current_shift.updated_at = get_datetime()
    current_shift.modifier_id = current_user.id
    db.add(current_shift)
    db.commit()
    db.refresh(current_shift)
    return current_shift

##### Holiday Endpoints #####

@router.get("/holiday/{holiday_id}")
async def get_holiday(
    holiday_id: Annotated[UUID, Path(title="The ID of the holiday to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single holiday
    """
    holiday = db.exec(select(EmployeeHoliday).where(
        EmployeeHoliday.id == holiday_id,
        EmployeeHoliday.organization_id == current_user.organization.id
    )).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    return holiday

@router.get("/holiday")
async def get_holidays(
    filter_query: Annotated[EmployeeFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered holidays
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(EmployeeHoliday).where(
        EmployeeHoliday.organization_id == current_user.organization_id
    ).offset(offset).limit(limit)
    holidays = db.exec(statement).all()
    resp_data = [{
        **holiday.model_dump(),
        "created_by": holiday.created_by
    } for holiday in holidays]
    return resp_data

@router.post("/holiday", status_code=status.HTTP_201_CREATED)
async def create_holiday(
    holiday: EmployeeHolidayModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> EmployeeHoliday:
    """
       Create new holiday
    """
    new_holiday = EmployeeHoliday(
        title = holiday.title,
        description = holiday.description,
        start_date = holiday.start_date,
        end_date = holiday.end_date,
        organization_id = holiday.organization_id or current_user.organization_id,
        owner_id = current_user.id,
        modifier_id = current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    try:
        db.add(new_holiday)
        db.commit()
        db.refresh(new_holiday)
        return new_holiday
    except sqlalchemy.exc.IntegrityError as e:
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}"
        ) from e

@router.put("/holiday/{holiday_id}", status_code=status.HTTP_200_OK)
async def update_holiday(
    holiday_id: Annotated[UUID, Path(title="The ID of the holiday to update")],
    holiday: EmployeeHolidayModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> AttendanceEvent:
    """
        Update existing holiday
    """
    current_holiday = db.get(EmployeeHoliday, holiday_id)
    if not current_holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    holiday_dict = holiday.model_dump(exclude_unset=True)
    for k, v in holiday_dict.items():
        if k == 'organization_id':
            continue
        current_holiday.sqlmodel_update({k: v})
    
    current_holiday.updated_at = get_datetime()
    current_holiday.modifier_id = current_user.id
    db.add(current_holiday)
    db.commit()
    db.refresh(current_holiday)
    return current_holiday

@router.delete("/holiday/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(
    holiday_id: Annotated[UUID, Path(title="The ID of the holiday to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing holiday
    """
    current_holiday = db.get(EmployeeHoliday, holiday_id)
    if not current_holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    if current_holiday.organization_id != current_user.organization_id:
        return
    db.delete(current_holiday)
    db.commit()
    return

##### Attendance Event Endpoints #####

@router.get("/attendance-event/{event_id}")
async def get_attendance_event(
    event_id: Annotated[UUID, Path(title="The ID of the attendance event to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single attendance event
    """
    attendance_event = db.exec(select(AttendanceEvent).where(
        AttendanceEvent.id == event_id,
        AttendanceEvent.organization_id == current_user.organization.id
    )).first()
    if not attendance_event:
        raise HTTPException(status_code=404, detail="Attendance event not found")
    return attendance_event

@router.get("/attendance-event")
async def get_attendance_events(
    filter_query: Annotated[AttendanceEventFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered attendance events
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)

    query_filters = [AttendanceEvent.organization_id == current_user.organization_id]
    if filter_query.from_date:
        query_filters.append(getattr(AttendanceEvent,"event_time") >= filter_query.from_date)
    if filter_query.to_date:
        query_filters.append(getattr(AttendanceEvent,"event_time") <= filter_query.to_date)
    
    statement = select(AttendanceEvent).where(
        *query_filters
    ).offset(offset).limit(limit).order_by(AttendanceEvent.created_at.desc()) # pylint: disable=no-member    (pylint)
    attendance_events = db.exec(statement).all()
    resp_data = [{
        **event.model_dump(),
        "employee": event.employee,
        "created_by": event.created_by
    } for event in attendance_events]
    return resp_data

EARTH_RADIUS_M = 6_371_000  # mean Earth radius in meters
def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))

@router.post("/attendance-event", status_code=status.HTTP_201_CREATED)
async def create_attendance_event(
    attendance_event: AttendanceEventModel, 
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> AttendanceEvent:
    """
       Create new attendance event
    """
    settings = db.exec(select(HRSettings).where(
        HRSettings.organization_id == current_user.organization_id
    )).first()
    if settings:
        if settings.verify_attendance_location and (settings.longitude and settings.latitude):
            if not (attendance_event.latitude and attendance_event.longitude):
                raise HTTPException(status_code=400, detail="Geolocation is required for attendance")
            distance = distance_meters(
                settings.latitude,
                settings.longitude,
                attendance_event.latitude,
                attendance_event.longitude
            )
            if distance > 1000:
                raise HTTPException(status_code=400, detail="Attendance location is too far")
            
        if settings.verify_attendance_ip and settings.ip_address:
            client_ip = request.client.host
            if client_ip != settings.ip_address:
                raise HTTPException(status_code=400, detail="Invalid network IP address")

    attendance = None
    if attendance_event.attendance_id:
        attendance = db.exec(select(Attendance).where(
            Attendance.id == attendance_event.attendance_id,
            Attendance.organization_id == current_user.organization.id
        )).first()
        if attendance_event.event_type == "Out":
            attendance.out_time = get_datetime()
            db.add(attendance)
    else:
        attendance = Attendance(
            employee_id = attendance_event.employee_id,
            attendance_date = getdate(attendance_event.event_time),
            status = "Present",
            in_time = get_datetime() if attendance_event.event_type == "In" else None,
            out_time = get_datetime() if attendance_event.event_type == "Out" else None,
            employee_shift_id = attendance_event.employee_shift_id,
            organization_id = attendance_event.organization_id or current_user.organization_id,
            owner_id = current_user.id,
            modifier_id = current_user.id,
            created_at=get_datetime(),
            updated_at=get_datetime()
        )

    new_attendance_event = AttendanceEvent(
        employee_id = attendance_event.employee_id,
        event_type = attendance_event.event_type,
        event_time = attendance_event.event_time,
        employee_shift_id = attendance_event.employee_shift_id,
        latitude = attendance_event.latitude,
        longitude = attendance_event.longitude,
        attendance = attendance,
        organization_id = attendance_event.organization_id or current_user.organization_id,
        owner_id = current_user.id,
        modifier_id = current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    try:
        db.add(new_attendance_event)
        db.commit()
        db.refresh(new_attendance_event)
        return new_attendance_event
    except sqlalchemy.exc.IntegrityError as e:
        # e.args => ('(sqlite3.IntegrityError) UNIQUE constraint failed: contact.phone',)
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}"
        ) from e

@router.put("/attendance-event/{event_id}", status_code=status.HTTP_200_OK)
async def update_attendance_event(
    event_id: Annotated[UUID, Path(title="The ID of the attendance to update")],
    attendance_event: AttendanceEventModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> AttendanceEvent:
    """
        Update existing attendance event
    """
    current_attendance_event = db.get(AttendanceEvent, event_id)
    if not current_attendance_event:
        raise HTTPException(status_code=404, detail="Attendance not found")
    attendance_event_dict = attendance_event.model_dump(exclude_unset=True)
    for k, v in attendance_event_dict.items():
        if k == 'organization_id':
            continue
        current_attendance_event.sqlmodel_update({k: v})

    current_attendance_event.updated_at = get_datetime()
    current_attendance_event.modifier_id = current_user.id
    db.add(current_attendance_event)
    db.commit()
    db.refresh(current_attendance_event)
    return current_attendance_event

##### Attendance Request Endpoints #####

@router.get("/attendance-request/{attendance_req_id}")
async def get_attendance_req(
    attendance_req_id: Annotated[UUID, Path(title="The ID of the attendance request to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single attendance request
    """
    attendance_req = db.exec(select(AttendanceRequest).where(
        AttendanceRequest.id == attendance_req_id,
        AttendanceRequest.organization_id == current_user.organization.id
    )).first()
    if not attendance_req:
        raise HTTPException(status_code=404, detail="Attendance request not found")
    return attendance_req

@router.get("/attendance-request")
async def get_attendance_reqs(
    filter_query: Annotated[EmployeeFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered attendance requests
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(AttendanceRequest).where(
        AttendanceRequest.organization_id == current_user.organization_id
    ).offset(offset).limit(limit)
    attendance_reqs = db.exec(statement).all()
    resp_data = [{
        **attendance_req.model_dump(),
        "employee": attendance_req.employee,
        "created_by": attendance_req.created_by
    } for attendance_req in attendance_reqs]
    return resp_data

@router.post("/attendance-request", status_code=status.HTTP_201_CREATED)
async def create_attendance_req(
    attendance_req: AttendanceRequestModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> AttendanceRequest:
    """
       Create new attendance request
    """
    if getdate(attendance_req.from_date) > getdate(attendance_req.to_date):
        raise HTTPException(status_code=400, detail="From date should not be greater than To date")
    
    new_attendance_req = AttendanceRequest(
        employee_id = attendance_req.employee_id,
        from_date = attendance_req.from_date,
        to_date = attendance_req.to_date,
        status = attendance_req.status,
        reason = attendance_req.reason,
        employee_shift_id = attendance_req.employee_shift_id,
        organization_id = attendance_req.organization_id or current_user.organization_id,
        owner_id = current_user.id,
        modifier_id = current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    try:
        db.add(new_attendance_req)
        db.commit()
        db.refresh(new_attendance_req)
        return new_attendance_req
    except sqlalchemy.exc.IntegrityError as e:
        # e.args => ('(sqlite3.IntegrityError) UNIQUE constraint failed: contact.phone',)
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}"
        ) from e

@router.put("/attendance-request/{attendance_req_id}", status_code=status.HTTP_200_OK)
async def update_attendance_req(
    attendance_req_id: Annotated[UUID, Path(title="The ID of the attendance to update")],
    attendance_req: AttendanceRequestModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> AttendanceRequest:
    """
        Update existing attendance request
    """
    current_attendance_req = db.get(AttendanceRequest, attendance_req_id)
    if not current_attendance_req:
        raise HTTPException(status_code=404, detail="Attendance not found")
    
    attendance_req_dict = attendance_req.model_dump(exclude_unset=True)
    current_status = current_attendance_req.status

    for k, v in attendance_req_dict.items():
        if k == 'organization_id':
            continue
        current_attendance_req.sqlmodel_update({k: v})

    if getdate(current_attendance_req.from_date) > getdate(current_attendance_req.to_date):
        raise HTTPException(status_code=400, detail="From date should not be greater than To date")

    if current_status != attendance_req.status:
        if attendance_req.status == "Approved":
            current_date = getdate(current_attendance_req.from_date)
            end_date = getdate(current_attendance_req.to_date)
            while current_date <= end_date:
                new_attendance = Attendance(
                    employee_id = current_attendance_req.employee_id,
                    attendance_date = current_date,
                    status = "Present",
                    attendance_request_id = current_attendance_req.id,
                    employee_shift_id = current_attendance_req.employee_shift_id,
                    organization_id = current_attendance_req.organization_id,
                    owner_id = current_user.id,
                    modifier_id = current_user.id,
                    created_at=get_datetime(),
                    updated_at=get_datetime()
                )
                db.add(new_attendance)
                current_date = add_to_date(current_date, days=1)

        elif attendance_req.status == "Rejected":
            attendance_list = db.exec(select(AttendanceRequest).where(
                Attendance.attendance_request_id == attendance_req.id,
                Attendance.organization_id == current_user.organization_id
            )).all()
            for attendance in attendance_list:
                db.delete(attendance)

    current_attendance_req.updated_at = get_datetime()
    current_attendance_req.modifier_id = current_user.id
    db.add(current_attendance_req)
    db.commit()
    db.refresh(current_attendance_req)
    return current_attendance_req

##### Attendance Endpoints #####

@router.get("/attendance/{attendance_id}")
async def get_attendance(
    attendance_id: Annotated[UUID, Path(title="The ID of the attendance to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single attendance
    """
    attendance = db.exec(select(Attendance).where(
        Attendance.id == attendance_id,
        Attendance.organization_id == current_user.organization.id
    )).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance not found")
    return attendance

@router.get("/attendance")
async def get_attendance_list(
    filter_query: Annotated[AttendanceFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered attendance list
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)

    query_filters = [Attendance.organization_id == current_user.organization_id]
    if filter_query.employee_id:
        query_filters.append(getattr(Attendance,"employee_id") == filter_query.employee_id)
    if filter_query.attendance_date:
        query_filters.append(getattr(Attendance,"attendance_date") == filter_query.attendance_date)
    if filter_query.from_date:
        query_filters.append(getattr(Attendance,"attendance_date") >= filter_query.from_date)
    if filter_query.to_date:
        query_filters.append(getattr(Attendance,"attendance_date") <= filter_query.to_date)
    if filter_query.status:
        query_filters.append(getattr(Attendance,"status") <= filter_query.status)

    statement = select(Attendance).where(
        *query_filters
    ).offset(offset).limit(limit)
    attendance_list = db.exec(statement).all()
    resp_data = [{
        **attendance.model_dump(),
        "employee": attendance.employee,
        "events": attendance.events,
        "created_by": attendance.created_by
    } for attendance in attendance_list]
    return resp_data

@router.post("/attendance", status_code=status.HTTP_201_CREATED)
async def create_attendance(
    attendance: AttendanceModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Attendance:
    """
       Create new attendance
    """
    new_attendance = Attendance(
        employee_id = attendance.employee_id,
        attendance_date = attendance.attendance_date,
        status = attendance.status,
        in_time = attendance.in_time,
        out_time = attendance.out_time,
        leave_application_id = attendance.leave_application_id,
        attendance_request_id = attendance.attendance_request_id,
        employee_shift_id = attendance.employee_shift_id,
        organization_id = attendance.organization_id or current_user.organization_id,
        owner_id = current_user.id,
        modifier_id = current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    try:
        db.add(new_attendance)
        db.commit()
        db.refresh(new_attendance)
        return new_attendance
    except sqlalchemy.exc.IntegrityError as e:
        # e.args => ('(sqlite3.IntegrityError) UNIQUE constraint failed: contact.phone',)
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}"
        ) from e

@router.put("/attendance/{attendance_id}", status_code=status.HTTP_200_OK)
async def update_attendance(
    attendance_id: Annotated[UUID, Path(title="The ID of the attendance to update")],
    attendance: AttendanceModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Attendance:
    """
        Update existing attendance
    """
    current_attendance = db.get(Attendance, attendance_id)
    if not current_attendance:
        raise HTTPException(status_code=404, detail="Attendance not found")
    attendance_dict = attendance.model_dump(exclude_unset=True)
    for k, v in attendance_dict.items():
        if k == 'organization_id':
            continue
        current_attendance.sqlmodel_update({k: v})

    current_attendance.updated_at = get_datetime()
    current_attendance.modifier_id = current_user.id
    db.add(current_attendance)
    db.commit()
    db.refresh(current_attendance)
    return current_attendance

##### Employee Endpoints #####

@router.get("/employee/{employee_id}")
async def get_employee(
    employee_id: Annotated[UUID, Path(title="The ID of the employee to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single employee
    """
    employee = db.exec(select(Employee).where(
        Employee.id == employee_id,
        Employee.organization_id == current_user.organization.id
    )).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Customer group not found")
    return employee

@router.get("/employee")
async def get_employees(
    filter_query: Annotated[EmployeeFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered employees
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    
    query_filters = [Employee.organization_id == current_user.organization_id]
    if filter_query.email:
        query_filters.append(getattr(Employee,"email") == filter_query.email)
    
    statement = select(Employee).where(
        *query_filters
    ).offset(offset).limit(limit)
    employees = db.exec(statement).all()
    resp_data = [{
        **employee.model_dump(),
        "department": employee.department,
        "supervisor": employee.supervisor,
        "shifts": employee.shifts,
        "image": "" if not employee.image else employee.image.file_name,
        "created_by": employee.created_by
    } for employee in employees]
    return resp_data

def get_employee_role(current_user, db):
    user_role = db.exec(select(UserRole).where(
        UserRole.role_name == "Employee",
        UserRole.organization_id == current_user.organization.id
    )).first()
    if not user_role:
        role_permissions = []
        default_permissions = [
            {"resource": "Employee", "can_read": True, "can_write": False, "can_create": False, "can_delete": False},
            {"resource": "Employee Holiday", "can_read": True, "can_write": False, "can_create": False, "can_delete": False},
            {"resource": "Employee Attendance", "can_read": True, "can_write": True, "can_create": True, "can_delete": False},
            {"resource": "Attendance Request", "can_read": True, "can_write": True, "can_create": True, "can_delete": False},
            {"resource": "Employee Shift", "can_read": True, "can_write": False, "can_create": False, "can_delete": False},
            {"resource": "Leave Type", "can_read": True, "can_write": False, "can_create": False, "can_delete": False},
            {"resource": "Leave Application", "can_read": True, "can_write": True, "can_create": True, "can_delete": False},
        ]
        for perm in default_permissions:
            perm_exists = db.exec(select(UserPermission).where(
                UserPermission.resource == perm.get("resource"),
                UserPermission.can_read == perm.get("can_read"),
                UserPermission.can_write == perm.get("can_write"),
                UserPermission.can_create == perm.get("can_create"),
                UserPermission.can_delete == perm.get("can_delete")
            )).first()
            if perm_exists:
                role_permissions.append(perm_exists)
            else:
                role_permissions.append(UserPermission(
                    resource = perm.get("resource"),
                    can_read = perm.get("can_read"),
                    can_write = perm.get("can_write"),
                    can_create = perm.get("can_create"),
                    can_delete = perm.get("can_delete")
                ))
        user_role = UserRole(
            role_name = "Employee",
            permissions = role_permissions,
            organization_id = current_user.organization.id,
            owner_id=current_user.id,
            modifier_id=current_user.id,
            created_at=get_datetime(),
            updated_at=get_datetime()
        )
        db.add(user_role)
    return user_role

def create_employee_user(employee, current_user, db):
    full_name = employee.first_name
    if employee.last_name:
        full_name = f"{employee.first_name} {employee.last_name}"

    user = db.exec(select(User).where(
        User.email == employee.email,
        User.organization_id == current_user.organization.id
    )).first()

    employee_role = get_employee_role(current_user, db)
    if not user:
        user = User(
            first_name = employee.first_name,
            last_name = employee.last_name,
            full_name = full_name,
            email = employee.email,
            phone = employee.phone,
            address = employee.address,
            image = employee.image,
            user_type = "System",
            active = False,
            roles = [employee_role],
            department_id = employee.department_id,
            organization_id = employee.organization_id or current_user.organization_id,
        )
    else:
        if not employee_role in user.roles:
            user.roles.append(employee_role)
    db.add(user)

@router.post("/employee", status_code=status.HTTP_201_CREATED)
async def create_employee(
    employee: EmployeeModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Employee:
    """
       Create new employee
    """
    full_name = employee.first_name
    if employee.last_name:
        full_name = f"{employee.first_name} {employee.last_name}"

    shifts = []
    employee_shifts = employee.shifts or []
    for shift in employee_shifts:
        _shift = db.exec(select(EmployeeShift).where(EmployeeShift.id == shift.id).first())
        if _shift:
            shifts.append(_shift)

    create_employee_user(employee, current_user, db)

    department = None
    if employee.department_name:
        statement = select(Department).where(
            Department.organization_id == current_user.organization_id,
            Department.department_name == employee.department_name
        )
        department = db.exec(statement).first()
        if not department:
            department = Department(
                department_name = employee.department_name,
                organization_id = current_user.organization_id,
                owner_id=current_user.id,
                modifier_id=current_user.id,
                created_at=get_datetime(),
                updated_at=get_datetime()
            )

    new_employee = Employee(
        first_name = employee.first_name,
        last_name = employee.last_name,
        full_name = full_name,
        email = employee.email,
        phone = employee.phone,
        gender = employee.gender,
        image = employee.image,
        status = employee.status,
        designation = employee.designation,
        address = employee.address,
        department_id = employee.department_id,
        department=department,
        is_department_head = employee.is_department_head,
        supervisor_id = employee.supervisor_id,
        # employee_shift_id = employee.employee_shift_id,
        shifts = shifts,
        organization_id = employee.organization_id or current_user.organization_id,
        owner_id=current_user.id,
        modifier_id=current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    
    try:
        db.add(new_employee)
        db.commit()
        db.refresh(new_employee)
        return new_employee
    except sqlalchemy.exc.IntegrityError as e:
        # e.args => ('(sqlite3.IntegrityError) UNIQUE constraint failed: contact.phone',)
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}"
        ) from e

@router.put("/employee/{employee_id}", status_code=status.HTTP_200_OK)
async def update_employee(
    employee_id: Annotated[UUID, Path(title="The ID of the employee to update")],
    employee: EmployeeModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Employee:
    """
        Update existing employee
    """
    current_employee = db.get(Employee, employee_id)
    if not current_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    employee_dict = employee.model_dump(exclude_unset=True)
    for k, v in employee_dict.items():
        if k == 'organization_id':
            continue
        if k == 'department_name' and v:
            statement = select(Department).where(
                Department.organization_id == current_user.organization_id,
                Department.department_name == v
            )
            department = db.exec(statement).first()
            if not department:
                department = Department(
                    department_name = v,
                    organization_id = current_user.organization_id,
                    owner_id=current_user.id,
                    modifier_id=current_user.id,
                    created_at=get_datetime(),
                    updated_at=get_datetime()
                )
            current_employee.department = department
            continue
        current_employee.sqlmodel_update({k: v})

    full_name = employee_dict.get("first_name")
    if employee_dict.get("last_name"):
        full_name = f"{employee_dict.get("first_name")} {employee_dict.get("last_name")}"
    current_employee.full_name = full_name
    current_employee.updated_at = get_datetime()
    current_employee.modifier_id = current_user.id

    create_employee_user(current_employee, current_user, db)

    db.add(current_employee)
    db.commit()
    db.refresh(current_employee)
    return current_employee

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

@router.put("/employee/upload-image/{employee_id}", status_code=status.HTTP_200_OK)
async def upload_profile_image(
    employee_id: Annotated[UUID, Path(title="The ID of the employee to update")],
    image: Annotated[UploadFile, File(description="Employee profile image")],
    session_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
    Upload employee image
    """
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported file type")

    current_employee = db.get(Employee, employee_id)
    if not current_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    file_data = upload_file(image)

    file_upload = FileUpload(
        file_name = file_data.get("filename"),
        file_type = file_data.get("file_type"),
        file_size = file_data.get("file_size"),
        formated_size = file_data.get("formated_size"),
        file_url = file_data.get("url"),
        record_type = "Employee",
        record_id = current_employee.id,
        record_field = "image",
        owner_id = session_user.id
    )
    db.add(file_upload)
    
    current_employee.updated_at = get_datetime()
    current_employee.modifier_id = session_user.id
    db.add(current_employee)
    db.commit()
    db.refresh(current_employee)
    return current_employee