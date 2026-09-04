from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import Customer
from ..utils import FilterParams

# from fastapi.security import OAuth2PasswordBearer

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# @app.get("/items/")
# async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
#     return {"token": token}

# async def get_token_header(x_token: Annotated[str, Header()]):
#     if x_token != "fake-super-secret-token":
#         raise HTTPException(status_code=400, detail="X-Token header invalid")

class CustomerFilterParams(FilterParams):
    organization_id: UUID

class CustomerModel(BaseModel):
    model_config = {"extra": "forbid"}
    customer_name: str
    email: str
    phone: str
    address: str | None = None
    address_geolocation: str | None = None
    group_id: str | None = None
    organization_id: int | None


router = APIRouter(
    prefix="/v1/customers",
    tags=["customers"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Customer not found"}},
)

@router.get("/{customer_id}")
async def get_customer(
    customer_id: Annotated[int, Path(title="The ID of the customer to get")],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single customer
    """
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@router.get("/")
async def get_customers(
    filter_query: Annotated[FilterParams, Query()],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered customers
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(Customer).offset(offset).limit(limit)
    # statement = select(Hero).where(Hero.name == "Spider-Boy")
    customers = db.exec(statement).all()
    return customers

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer: CustomerModel, 
    db: Annotated[Session, Depends(get_db)]
) -> Customer:
    """
       Create new customer
    """
    customer = Customer(
        customer_name = customer.customer_name,
        email = customer.email,
        phone = customer.phone,
        address = customer.address,
        address_geolocation = customer.address_geolocation,
        group_id = customer.group_id,
        organization_id = customer.organization_id,
        created_at=str(datetime.now()),
        updated_at=str(datetime.now())
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer

@router.put("/{customer_id}", status_code=status.HTTP_200_OK)
async def update_customer(
    customer_id: Annotated[int, Path(title="The ID of the customer to update")],
    customer: CustomerModel, 
    db: Annotated[Session, Depends(get_db)]
) -> Customer:
    """
        Update existing customer
    """
    current_customer = db.get(Customer, customer_id)
    if not current_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer_dict = customer.model_dump(exclude_unset=True)
    for k, v in customer_dict.items():
        if k == 'organization_id':
            continue
        current_customer[k] = v
    current_customer.updated_at = str(datetime.now())
    db.add(current_customer)
    db.commit()
    db.refresh(current_customer)
    return current_customer