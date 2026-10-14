from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import VendorGroup, User
from ..utils import FilterParams, get_current_user

# from fastapi.security import OAuth2PasswordBearer

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# @app.get("/items/")
# async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
#     return {"token": token}

# async def get_token_header(x_token: Annotated[str, Header()]):
#     if x_token != "fake-super-secret-token":
#         raise HTTPException(status_code=400, detail="X-Token header invalid")

class VendorGroupFilterParams(FilterParams):
    organization_id: UUID

class VendorGroupModel(BaseModel):
    model_config = {"extra": "forbid"}
    group_name: str
    organization_id: int | None


router = APIRouter(
    prefix="/v1/vendor_groups",
    tags=["vendor_groups"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Vendor group not found"}},
)

@router.get("/{group_id}")
async def get_vendor_group(
    group_id: Annotated[UUID, Path(title="The ID of the vendor group to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single vendor group
    """
    vendor_group = db.exec(select(VendorGroup).where(
        VendorGroup.id == group_id,
        VendorGroup.organization_id == current_user.organization.id
    )).first()
    if not vendor_group:
        raise HTTPException(status_code=404, detail="Vendor group not found")
    return vendor_group

@router.get("/")
async def get_vendor_groups(
    filter_query: Annotated[VendorGroupFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered vendor groups
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(VendorGroup).where(
        VendorGroup.organization_id == current_user.organization_id
    ).offset(offset).limit(limit)
    # statement = select(Hero).where(Hero.name == "Spider-Boy")
    vendor_groups = db.exec(statement).all()
    return vendor_groups

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_vendor_group(
    vendor_group: VendorGroupModel, 
    db: Annotated[Session, Depends(get_db)]
) -> VendorGroup:
    """
       Create new vendor group
    """
    group = VendorGroup(
        group_name = vendor_group.group_name,
        organization_id = vendor_group.organization_id,
        created_at=str(datetime.now()),
        updated_at=str(datetime.now())
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

@router.put("/{group_id}", status_code=status.HTTP_200_OK)
async def update_vendor_group(
    group_id: Annotated[int, Path(title="The ID of the vendor group to update")],
    vendor_group: VendorGroupModel, 
    db: Annotated[Session, Depends(get_db)]
) -> VendorGroup:
    """
        Update existing vendor group
    """
    current_vendor_group = db.get(VendorGroup, group_id)
    if not current_vendor_group:
        raise HTTPException(status_code=404, detail="Vendor group not found")
    vendor_group_dict = vendor_group.model_dump(exclude_unset=True)
    for k, v in vendor_group_dict.items():
        if k == 'organization_id':
            continue
        current_vendor_group.sqlmodel_update({k: v})
    current_vendor_group.updated_at = str(datetime.now())
    db.add(current_vendor_group)
    db.commit()
    db.refresh(current_vendor_group)
    return current_vendor_group