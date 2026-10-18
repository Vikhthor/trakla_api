from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import UserRole, UserPermission, User
from ..utils import FilterParams, get_current_user, get_datetime

# from fastapi.security import OAuth2PasswordBearer

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# @app.get("/items/")
# async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
#     return {"token": token}

# async def get_token_header(x_token: Annotated[str, Header()]):
#     if x_token != "fake-super-secret-token":
#         raise HTTPException(status_code=400, detail="X-Token header invalid")

class UserRoleFilterParams(FilterParams):
    organization_id: UUID

class RolePermission(BaseModel):
    resource: str
    can_read: bool | None = False
    can_write: bool | None = False
    can_create: bool | None = False
    can_delete: bool | None = False

class UserRoleModel(BaseModel):
    model_config = {"extra": "forbid"}
    role_name: str
    permissions: list[RolePermission]
    organization_id: UUID | None


router = APIRouter(
    prefix="/v1/roles",
    tags=["roles"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Role not found"}},
)

@router.get("/{role_id}")
async def get_role(
    role_id: Annotated[UUID, Path(title="The ID of the user role to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single user role
    """
    role = db.exec(select(UserRole).where(
        UserRole.id == role_id,
        UserRole.organization_id == current_user.organization.id
    )).first()
    if not role:
        raise HTTPException(status_code=404, detail="User role not found")
    resp_data = {
        **role.model_dump(),
        "permissions": role.permissions,
        "created_by": role.created_by
    }
    return resp_data

@router.get("/")
async def get_roles(
    filter_query: Annotated[UserRoleFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered roles
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(UserRole).where(
        UserRole.organization_id == current_user.organization_id
    ).offset(offset).limit(limit)
    # statement = select(Hero).where(Hero.name == "Spider-Boy")
    roles = db.exec(statement).all()
    resp_data = [{
        **role.model_dump(),
        "permissions": role.permissions,
        "created_by": role.created_by
    } for role in roles]
    return resp_data

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_role(
    role: UserRoleModel,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> UserRole:
    """
       Create new role
    """
    role_permissions = []
    for perm in role.permissions:
        perm_exists = db.exec(select(UserPermission).where(
            UserPermission.resource == perm.resource,
            UserPermission.can_read == perm.can_read,
            UserPermission.can_write == perm.can_write,
            UserPermission.can_create == perm.can_write,
            UserPermission.can_delete == perm.can_delete
        )).first()
        if perm_exists:
            role_permissions.append(perm_exists)
        else:
            role_permissions.append(UserPermission(
                resource = perm.resource,
                can_read = perm.can_read,
                can_write = perm.can_write,
                can_create = perm.can_write,
                can_delete = perm.can_delete
            ))
    role = UserRole(
        role_name = role.role_name,
        permissions = role_permissions,
        organization_id = role.organization_id,
        owner_id=current_user.id,
        modifier_id=current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

@router.put("/{role_id}", status_code=status.HTTP_200_OK)
async def update_role(
    role_id: Annotated[UUID, Path(title="The ID of the customer group to update")],
    role: UserRoleModel,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> UserRole:
    """
        Update existing customer
    """
    current_role = db.get(UserRole, role_id)
    if not current_role:
        raise HTTPException(status_code=404, detail="Customer group not found")
    role_dict = role.model_dump(exclude_unset=True)
    for k, v in role_dict.items():
        if k == 'organization_id':
            continue
        if k == 'permissions':
            role_permissions = []
            for perm in v:
                perm_exists = db.exec(select(UserPermission).where(
                    UserPermission.resource == perm.resource,
                    UserPermission.can_read == perm.can_read,
                    UserPermission.can_write == perm.can_write,
                    UserPermission.can_create == perm.can_write,
                    UserPermission.can_delete == perm.can_delete
                )).first()
                if perm_exists:
                    role_permissions.append(perm_exists)
                else:
                    role_permissions.append(UserPermission(
                        resource = perm.resource,
                        can_read = perm.can_read,
                        can_write = perm.can_write,
                        can_create = perm.can_write,
                        can_delete = perm.can_delete
                    ))
            v = role_permissions
        current_role.sqlmodel_update({k: v})
    current_role.updated_at = get_datetime()
    current_role.modifier_id = current_user.id
    db.add(current_role)
    db.commit()
    db.refresh(current_role)
    return current_role