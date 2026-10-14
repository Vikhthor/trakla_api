from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import Vendor, User, Contact, VendorGroup
from ..utils import FilterParams, get_current_user
import sqlalchemy
from sqlalchemy.orm import joinedload, selectinload

class VendorFilterParams(FilterParams):
    organization_id: UUID

class VendorModel(BaseModel):
    model_config = {"extra": "forbid"}
    vendor_name: str
    email: str | None = None
    phone: str | None = None
    contacts: list[UUID] | None = None
    group_name: str | None = None
    address: str | None = None
    organization_id: UUID | None


router = APIRouter(
    prefix="/v1/vendors",
    tags=["vendors"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Vendor not found"}},
)

@router.get("/{vendor_id}")
async def get_vendor(
    vendor_id: Annotated[UUID, Path(title="The ID of the vendor to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single vendor
    """
    vendor = db.exec(select(Vendor).where(
        Vendor.id == vendor_id,
        Vendor.organization_id == current_user.organization.id
    )).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    resp_data = {
        **vendor.model_dump(),
        "contacts": vendor.contacts,
        "vendor_group": vendor.group.group_name,
        "created_by": vendor.created_by
    }
    return resp_data

@router.get("/")
async def get_vendors(
    filter_query: Annotated[VendorFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered vendors
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(Vendor).where(
        Vendor.organization_id == current_user.organization_id
    ).offset(offset).limit(limit).options(selectinload(Vendor.created_by))
    vendors = db.exec(statement).all()
    resp_data = [{
        **vendor.model_dump(),
        "vendor_group": vendor.group.group_name,
        "contacts": vendor.contacts,
        "created_by": vendor.created_by
    } for vendor in vendors]
    return resp_data

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_vendor(
    vendor: VendorModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Vendor:
    """
       Create new vendor
    """
    contacts = []
    primary_contact_id = None
    if vendor.contacts:
        for contact_id in vendor.contacts:
            contact = db.exec(select(Contact).where(
                Contact.id == contact_id,
                Contact.organization_id == current_user.organization.id
            )).first()
            if contact:
                contacts.append(contact)
                if not primary_contact_id:
                    primary_contact_id = contact_id

    group = None
    if vendor.group_name:
        statement = select(VendorGroup).where(
            VendorGroup.organization_id == current_user.organization_id,
            VendorGroup.group_name == vendor.group_name
        )
        group = db.exec(statement).first()
        if not group:
            group = VendorGroup(
                group_name = vendor.group_name,
                organization_id = current_user.organization_id,
                owner_id=current_user.id,
                modifier_id=current_user.id,
                created_at=str(datetime.now()),
                updated_at=str(datetime.now())
            )

    vendor = Vendor(
        vendor_name = vendor.vendor_name,
        email = vendor.email,
        phone = vendor.phone,
        address = vendor.address,
        group = group,
        contacts = contacts,
        primary_contact_id = primary_contact_id,
        organization_id = vendor.organization_id or current_user.organization_id,
        owner_id=current_user.id,
        modifier_id=current_user.id,
        created_at=str(datetime.now()),
        updated_at=str(datetime.now())
    )
    try:
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        return vendor
    except sqlalchemy.exc.IntegrityError as e:
        # e.args => ('(sqlite3.IntegrityError) UNIQUE constraint failed: vendor.phone',)
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}: {vendor.model_dump().get('phone')}"
        ) from e


@router.put("/{vendor_id}", status_code=status.HTTP_200_OK)
async def update_vendor(
    vendor_id: Annotated[int, Path(title="The ID of the vendor to update")],
    vendor: VendorModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Vendor:
    """
        Update existing vendor
    """
    current_vendor = db.get(Vendor, vendor_id)
    if not current_vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    if current_vendor.organization_id != current_user.organization_id:
        return current_vendor
    vendor_dict = vendor.model_dump(exclude_unset=True)
    for k, v in vendor_dict.items():
        if k == 'organization_id':
            continue

        if k == 'contacts':
            current_vendor.contacts = []
            if v:
                for contact_id in v:
                    contact = db.exec(select(Contact).where(
                        Contact.id == contact_id,
                        Contact.organization_id == current_user.organization.id
                    )).first()
                    if contact:
                        current_vendor.contacts.append(contact)
            continue

        if k == "group_name":
            statement = select(VendorGroup).where(
                VendorGroup.organization_id == current_user.organization_id,
                VendorGroup.group_name == v
            )
            group = db.exec(statement).first()
            if not group:
                group = VendorGroup(
                    group_name = v,
                    organization_id = current_user.organization_id,
                    owner_id=current_user.id,
                    modifier_id=current_user.id,
                    created_at=str(datetime.now()),
                    updated_at=str(datetime.now())
                )
            current_vendor.group = group
            continue
        current_vendor.sqlmodel_update({k: v})
    
    full_name = vendor_dict.get("first_name")
    if vendor_dict.get("last_name"):
        full_name = f"{vendor_dict.get("first_name")} {vendor_dict.get("last_name")}"
    current_vendor.full_name = full_name
    current_vendor.updated_at = str(datetime.now())
    current_vendor.modifier_id = current_user.id
    db.add(current_vendor)
    db.commit()
    db.refresh(current_vendor)
    return current_vendor

@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: Annotated[UUID, Path(title="The ID of the vendor to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing vendor
    """
    current_vendor = db.get(Vendor, vendor_id)
    if not current_vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    if current_vendor.organization_id != current_user.organization_id:
        return
    db.delete(current_vendor)
    db.commit()
    return