from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import AssetType, User
from ..utils import FilterParams, get_current_user

# from fastapi.security import OAuth2PasswordBearer

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# @app.get("/items/")
# async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
#     return {"token": token}

# async def get_token_header(x_token: Annotated[str, Header()]):
#     if x_token != "fake-super-secret-token":
#         raise HTTPException(status_code=400, detail="X-Token header invalid")

class AssetTypeFilterParams(FilterParams):
    organization_id: UUID

class AssetTypeModel(BaseModel):
    model_config = {"extra": "forbid"}
    asset_type_name: str
    organization_id: int | None


router = APIRouter(
    prefix="/v1/asset-types",
    tags=["asset_types"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Asset type not found"}},
)

@router.get("/{asset_type_id}")
async def get_asset_type(
    asset_type_id: Annotated[UUID, Path(title="The ID of the asset type to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single customer group
    """
    asset_type = db.exec(select(AssetType).where(
        AssetType.id == asset_type_id,
        AssetType.organization_id == current_user.organization.id
    )).first()
    if not asset_type:
        raise HTTPException(status_code=404, detail="Customer group not found")
    return asset_type

@router.get("/")
async def get_asset_types(
    filter_query: Annotated[AssetTypeFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered asset types
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(AssetType).where(
        AssetType.organization_id == current_user.organization_id
    ).offset(offset).limit(limit)
    # statement = select(Hero).where(Hero.name == "Spider-Boy")
    asset_types = db.exec(statement).all()
    return asset_types

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_asset_type(
    asset_type: AssetTypeModel, 
    db: Annotated[Session, Depends(get_db)]
) -> AssetType:
    """
       Create new asset type
    """
    group = AssetType(
        asset_type_name = asset_type.asset_type_name,
        organization_id = asset_type.organization_id,
        created_at=str(datetime.now()),
        updated_at=str(datetime.now())
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

@router.put("/{asset_type_id}", status_code=status.HTTP_200_OK)
async def update_asset_type(
    asset_type_id: Annotated[int, Path(title="The ID of the customer group to update")],
    asset_type: AssetTypeModel, 
    db: Annotated[Session, Depends(get_db)]
) -> AssetType:
    """
        Update existing customer
    """
    current_asset_type = db.get(AssetType, asset_type_id)
    if not current_asset_type:
        raise HTTPException(status_code=404, detail="Customer group not found")
    asset_type_dict = asset_type.model_dump(exclude_unset=True)
    for k, v in asset_type_dict.items():
        if k == 'organization_id':
            continue
        current_asset_type.sqlmodel_update({k: v})
    current_asset_type.updated_at = str(datetime.now())
    db.add(current_asset_type)
    db.commit()
    db.refresh(current_asset_type)
    return current_asset_type