from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_, func, get_count
from ..models import Customer, Contact, User, CustomerGroup, ServiceRequest
from ..utils import FilterParams, get_current_user, get_datetime

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
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    address_geolocation: str | None = None
    contacts: list[UUID] | None = None
    group_name: str | None = None
    organization_id: UUID | None


router = APIRouter(
    prefix="/v1/customers",
    tags=["customers"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Customer not found"}},
)

@router.get("/{customer_id}")
async def get_customer(
    customer_id: Annotated[UUID, Path(title="The ID of the customer to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single customer
    """
    customer = db.exec(select(Customer).where(
        Customer.id == customer_id,
        Customer.organization_id == current_user.organization.id
    )).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    resp_data = {
        **customer.model_dump(),
        "contacts": customer.contacts,
        "created_by": customer.created_by
    }
    return resp_data

@router.get("/")
async def get_customers(
    filter_query: Annotated[CustomerFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered customers
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(
        Customer
    ).where(
        Customer.organization_id == current_user.organization_id,
    ).offset(offset).limit(limit)
    customers = db.exec(statement).all()

    resp_data = []
    for customer in customers:
        pending_request_count = get_count(ServiceRequest, db, {
            "organization_id": current_user.organization_id,
            "customer_id": customer.id,
            "status": "Open"
        })
        resp_data.append({
            **customer.model_dump(),
            "pending_request_count": pending_request_count,
            "customer_group": customer.group.group_name,
            "contacts": customer.contacts,
            "created_by": customer.created_by
        })
    return resp_data

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer: CustomerModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Customer:
    """
       Create new customer
    """
    contacts = []
    primary_contact_id = None
    if customer.contacts:
        for contact_id in customer.contacts:
            contact = db.exec(select(Contact).where(
                Contact.id == contact_id,
                Contact.organization_id == current_user.organization.id
            )).first()
            if contact:
                contacts.append(contact)
                if not primary_contact_id:
                    primary_contact_id = contact_id

    group = None
    if customer.group_name:
        statement = select(CustomerGroup).where(
            CustomerGroup.organization_id == current_user.organization_id,
            CustomerGroup.group_name == customer.group_name
        )
        group = db.exec(statement).first()
        if not group:
            group = CustomerGroup(
                group_name = customer.group_name,
                organization_id = current_user.organization_id,
                owner_id=current_user.id,
                modifier_id=current_user.id,
                created_at=get_datetime(),
                updated_at=get_datetime()
            )

    customer = Customer(
        customer_name = customer.customer_name,
        email = customer.email,
        phone = customer.phone,
        address = customer.address,
        address_geolocation = customer.address_geolocation,
        group = group,
        contacts = contacts,
        primary_contact_id = primary_contact_id,
        organization_id = customer.organization_id,
        owner_id=current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer

@router.put("/{customer_id}", status_code=status.HTTP_200_OK)
async def update_customer(
    customer_id: Annotated[UUID, Path(title="The ID of the customer to update")],
    customer: CustomerModel, 
    current_user: Annotated[User, Depends(get_current_user)],
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

        if k == 'contacts':
            current_customer.contacts = []
            if v:
                for contact_id in v:
                    contact = db.exec(select(Contact).where(
                        Contact.id == contact_id,
                        Contact.organization_id == current_user.organization.id
                    )).first()
                    if contact:
                        current_customer.contacts.append(contact)
            continue

        if k == "group_name":
            statement = select(CustomerGroup).where(
                CustomerGroup.organization_id == current_user.organization_id,
                CustomerGroup.group_name == v
            )
            group = db.exec(statement).first()
            if not group:
                group = CustomerGroup(
                    group_name = v,
                    organization_id = current_user.organization_id,
                    owner_id=current_user.id,
                    modifier_id=current_user.id,
                    created_at=get_datetime(),
                    updated_at=get_datetime()
                )
            current_customer.group = group
            continue
        
        current_customer.sqlmodel_update({k: v})
    
    current_customer.updated_at = get_datetime()
    current_customer.modifier_id = current_user.id
    db.add(current_customer)
    db.commit()
    db.refresh(current_customer)
    return current_customer

@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: Annotated[UUID, Path(title="The ID of the customer to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing customer
    """
    current_customer = db.get(Customer, customer_id)
    if not current_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if current_customer.organization_id != current_user.organization_id:
        return
    db.delete(current_customer)
    db.commit()
    return