from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import CustomerGroup
from ..utils import FilterParams

# from fastapi.security import OAuth2PasswordBearer

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# @app.get("/items/")
# async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
#     return {"token": token}

# async def get_token_header(x_token: Annotated[str, Header()]):
#     if x_token != "fake-super-secret-token":
#         raise HTTPException(status_code=400, detail="X-Token header invalid")

class CustomerGroupFilterParams(FilterParams):
    organization_id: UUID

class CustomerGroupModel(BaseModel):
    model_config = {"extra": "forbid"}
    group_name: str
    organization_id: int | None


router = APIRouter(
    prefix="/v1/customer_groups",
    tags=["customer_groups"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Customer group not found"}},
)

@router.get("/{group_id}")
async def get_customer_group(
    group_id: Annotated[UUID, Path(title="The ID of the customer group to get")],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single customer group
    """
    customer_group = db.get(CustomerGroup, group_id)
    if not customer_group:
        raise HTTPException(status_code=404, detail="Customer group not found")
    return customer_group

@router.get("/")
async def get_customer_groups(
    filter_query: Annotated[CustomerGroupFilterParams, Query()],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered customers
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(CustomerGroup).offset(offset).limit(limit)
    # statement = select(Hero).where(Hero.name == "Spider-Boy")
    customers = db.exec(statement).all()
    return customers

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_customer_group(
    customer_group: CustomerGroupModel, 
    db: Annotated[Session, Depends(get_db)]
) -> CustomerGroup:
    """
       Create new customer group
    """
    group = CustomerGroup(
        group_name = customer_group.group_name,
        organization_id = customer_group.organization_id,
        created_at=str(datetime.now()),
        updated_at=str(datetime.now())
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

@router.put("/{group_id}", status_code=status.HTTP_200_OK)
async def update_customer_group(
    group_id: Annotated[int, Path(title="The ID of the customer group to update")],
    customer_group: CustomerGroupModel, 
    db: Annotated[Session, Depends(get_db)]
) -> CustomerGroup:
    """
        Update existing customer
    """
    current_customer_group = db.get(CustomerGroup, group_id)
    if not current_customer_group:
        raise HTTPException(status_code=404, detail="Customer group not found")
    customer_group_dict = customer_group.model_dump(exclude_unset=True)
    for k, v in customer_group_dict.items():
        if k == 'organization_id':
            continue
        current_customer_group.sqlmodel_update({k: v})
    current_customer_group.updated_at = str(datetime.now())
    db.add(current_customer_group)
    db.commit()
    db.refresh(current_customer_group)
    return current_customer_group