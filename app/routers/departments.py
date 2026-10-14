from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import Department, User
from ..utils import FilterParams, get_current_user

# from fastapi.security import OAuth2PasswordBearer

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# @app.get("/items/")
# async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
#     return {"token": token}

# async def get_token_header(x_token: Annotated[str, Header()]):
#     if x_token != "fake-super-secret-token":
#         raise HTTPException(status_code=400, detail="X-Token header invalid")

class DepartmentFilterParams(FilterParams):
    organization_id: UUID

class DepartmentModel(BaseModel):
    model_config = {"extra": "forbid"}
    department_name: str
    organization_id: int | None


router = APIRouter(
    prefix="/v1/departments",
    tags=["departments"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Department not found"}},
)

@router.get("/{department_id}")
async def get_department(
    department_id: Annotated[UUID, Path(title="The ID of the department to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single department
    """
    department = db.exec(select(Department).where(
        Department.id == department_id,
        Department.organization_id == current_user.organization.id
    )).first()
    if not department:
        raise HTTPException(status_code=404, detail="Customer group not found")
    return department

@router.get("/")
async def get_departments(
    filter_query: Annotated[DepartmentFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered departments
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(Department).where(
        Department.organization_id == current_user.organization_id
    ).offset(offset).limit(limit)
    # statement = select(Hero).where(Hero.name == "Spider-Boy")
    departments = db.exec(statement).all()
    return departments

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_department(
    department: DepartmentModel, 
    db: Annotated[Session, Depends(get_db)]
) -> Department:
    """
       Create new department
    """
    group = Department(
        department_name = department.department_name,
        organization_id = department.organization_id,
        created_at=str(datetime.now()),
        updated_at=str(datetime.now())
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

@router.put("/{department_id}", status_code=status.HTTP_200_OK)
async def update_department(
    department_id: Annotated[int, Path(title="The ID of the customer group to update")],
    department: DepartmentModel, 
    db: Annotated[Session, Depends(get_db)]
) -> Department:
    """
        Update existing customer
    """
    current_department = db.get(Department, department_id)
    if not current_department:
        raise HTTPException(status_code=404, detail="Customer group not found")
    department_dict = department.model_dump(exclude_unset=True)
    for k, v in department_dict.items():
        if k == 'organization_id':
            continue
        current_department.sqlmodel_update({k: v})
    current_department.updated_at = str(datetime.now())
    db.add(current_department)
    db.commit()
    db.refresh(current_department)
    return current_department