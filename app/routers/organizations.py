from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header, File, UploadFile

from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import Organization, User, File as FileUpload
from ..utils import FilterParams, get_current_user, upload_file

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

async def get_token_header(x_token: Annotated[str, Header()]):
    if x_token != "fake-super-secret-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")

class OrganizationFilterParams(FilterParams):
    organization_id: UUID | None = None

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

    resp_data = {
        **organization.model_dump(),
        "brand_icon": "" if not organization.brand_icon else organization.brand_icon.file_name,
        "logo": "" if not organization.logo else organization.logo.file_name,
    }
    return resp_data

@router.get("/")
async def get_organizations(
    filter_query: Annotated[OrganizationFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered organizations
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(Organization).where(
        Organization.id == current_user.organization.id
    ).offset(offset).limit(limit)
    organizations = db.exec(statement).all()

    resp_data = [{
        **organization.model_dump(),
        "brand_icon": "" if not organization.brand_icon else organization.brand_icon.file_name,
        "logo": "" if not organization.logo else organization.logo.file_name,
    } for organization in organizations]
    return resp_data

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
        current_organization.sqlmodel_update({k: v})
    current_organization.updated_at = str(datetime.now())
    db.add(current_organization)
    db.commit()
    db.refresh(current_organization)

    resp_data = {
        **current_organization.model_dump(),
        "brand_icon": "" if not current_organization.brand_icon else current_organization.brand_icon.file_name,
        "logo": "" if not current_organization.logo else current_organization.logo.file_name,
    }
    return resp_data

@router.put("/upload-image/{organization_id}", status_code=status.HTTP_200_OK)
async def upload_profile_image(
    organization_id: Annotated[UUID, Path(title="The ID of the user to update")],
    session_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    brand_icon: Annotated[UploadFile | None, File(description="organization brand icon image")] = None,
    logo: Annotated[UploadFile | None, File(description="organization brand icon image")] = None
):
    """
    Upload profile image
    """
    images = {
        "brand_icon": brand_icon,
        "logo": logo
    }

    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    for field_name, image in images.items():
        if not image:
            continue

        if image.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=415, detail="Unsupported file type")
        
        file_data = upload_file(image)

        file_upload = FileUpload(
            file_name = file_data.get("filename"),
            file_type = file_data.get("file_type"),
            file_size = file_data.get("file_size"),
            formated_size = file_data.get("formated_size"),
            file_url = file_data.get("url"),
            record_type = "Organization",
            record_id = organization_id,
            record_field = field_name,
            owner_id = session_user.id
        )
        db.add(file_upload)
    
    organization.updated_at = str(datetime.now())
    organization.modifier_id = session_user.id
    db.add(organization)
    db.commit()
    db.refresh(organization)
    
    resp_data = {
        **organization.model_dump(),
        "brand_icon": "" if not organization.brand_icon else organization.brand_icon.file_name,
        "logo": "" if not organization.logo else organization.logo.file_name,
    }
    return resp_data