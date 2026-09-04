from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import Organization
from ..utils import FilterParams

async def get_token_header(x_token: Annotated[str, Header()]):
    if x_token != "fake-super-secret-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")

class OrganizationFilterParams(FilterParams):
    organization_id: UUID

class OrganizationModel(BaseModel):
    model_config = {"extra": "forbid"}
    organization_name: str # user organization
    logo: str
    address: str

router = APIRouter(
    prefix="/v1/organizations",
    tags=["organizations"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Organization not found"}},
)

@router.get("/{organization_id}")
async def get_organization(
    organization_id: Annotated[UUID, Path(title="The ID of the organization to get")],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single organization
    """
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization

@router.get("/")
async def get_organizations(
    filter_query: Annotated[OrganizationFilterParams, Query()],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered organizations
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(Organization).offset(offset).limit(limit)
    organizations = db.exec(statement).all()
    return organizations

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_customer(
    organization: OrganizationModel, 
    db: Annotated[Session, Depends(get_db)]
) -> Organization:
    """
       Create new customer
    """
    organization = Organization(
        organization_name = organization.organization_name,
        logo = organization.logo,
        address = organization.address,
        created_at=str(datetime.now()),
        updated_at=str(datetime.now())
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)
    return organization

@router.put("/{organization_id}", status_code=status.HTTP_200_OK)
async def update_organization(
    organization_id: Annotated[UUID, Path(title="The ID of the organization to update")],
    organization: OrganizationModel, 
    db: Annotated[Session, Depends(get_db)]
) -> Organization:
    """
        Update existing organization
    """
    current_organization = db.get(Organization, organization_id)
    if not current_organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization_dict = organization.model_dump(exclude_unset=True)
    for k, v in organization_dict.items():
        current_organization[k] = v
    current_organization.updated_at = str(datetime.now())
    db.add(current_organization)
    db.commit()
    db.refresh(current_organization)
    return current_organization