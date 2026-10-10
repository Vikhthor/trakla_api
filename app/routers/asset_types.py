from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import AssetType
from ..utils import FilterParams

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
    responses={404: {"description": "Customer group not found"}},
)

@router.get("/{asset_type_id}")
async def get_asset_type(
    asset_type_id: Annotated[UUID, Path(title="The ID of the customer group to get")],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single customer group
    """
    asset_type = db.get(AssetType, asset_type_id)
    if not asset_type:
        raise HTTPException(status_code=404, detail="Customer group not found")
    return asset_type

@router.get("/")
async def get_asset_types(
    filter_query: Annotated[AssetTypeFilterParams, Query()],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered customers
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(AssetType).offset(offset).limit(limit)
    # statement = select(Hero).where(Hero.name == "Spider-Boy")
    customers = db.exec(statement).all()
    return customers

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_asset_type(
    asset_type: AssetTypeModel, 
    db: Annotated[Session, Depends(get_db)]
) -> AssetType:
    """
       Create new customer group
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