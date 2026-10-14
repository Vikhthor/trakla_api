from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header, File, UploadFile

from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import Contact, User
from ..utils import FilterParams, get_current_user
import sqlalchemy
from sqlalchemy.orm import joinedload, selectinload

class ContactFilterParams(FilterParams):
    organization_id: UUID

class ContactModel(BaseModel):
    model_config = {"extra": "forbid"}
    title: str | None = None
    first_name: str
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    gender: str | None = None
    image: str | None = None
    role: str | None = None
    address: str | None = None
    address_geolocation: str | None = None
    organization_id: UUID | None


router = APIRouter(
    prefix="/v1/contacts",
    tags=["contacts"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Contact not found"}},
)

@router.get("/{contact_id}")
async def get_contact(
    contact_id: Annotated[UUID, Path(title="The ID of the contact to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single contact
    """
    contact = db.exec(select(Contact).where(
        Contact.id == contact_id,
        Contact.organization_id == current_user.organization.id
    )).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.get("/")
async def get_contacts(
    filter_query: Annotated[ContactFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered contacts
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(Contact).where(
        Contact.organization_id == current_user.organization_id
    ).offset(offset).limit(limit).options(selectinload(Contact.created_by))
    contacts = db.exec(statement).all()
    resp_data = [{
        **contact.model_dump(),
        "created_by": contact.created_by
    } for contact in contacts]
    return resp_data

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact: ContactModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Contact:
    """
       Create new contact
    """
    full_name = contact.first_name
    if contact.last_name:
        full_name = f"{contact.first_name} {contact.last_name}"
    contact = Contact(
        title = contact.title,
        first_name = contact.first_name,
        last_name = contact.last_name,
        full_name = full_name,
        email = contact.email,
        phone = contact.phone,
        gender = contact.gender,
        image = contact.image,
        role = contact.role,
        address = contact.address,
        organization_id = contact.organization_id or current_user.organization_id,
        owner_id=current_user.id,
        modifier_id=current_user.id,
        created_at=str(datetime.now()),
        updated_at=str(datetime.now())
    )
    try:
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact
    except sqlalchemy.exc.IntegrityError as e:
        # e.args => ('(sqlite3.IntegrityError) UNIQUE constraint failed: contact.phone',)
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}: {contact.model_dump().get('phone')}"
        ) from e


@router.put("/{contact_id}", status_code=status.HTTP_200_OK)
async def update_contact(
    contact_id: Annotated[int, Path(title="The ID of the contact to update")],
    contact: ContactModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Contact:
    """
        Update existing contact
    """
    current_contact = db.get(Contact, contact_id)
    if not current_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    if current_contact.organization_id != current_user.organization_id:
        return current_contact
    contact_dict = contact.model_dump(exclude_unset=True)
    for k, v in contact_dict.items():
        if k == 'organization_id':
            continue
        current_contact.sqlmodel_update({k: v})
    
    full_name = contact_dict.get("first_name")
    if contact_dict.get("last_name"):
        full_name = f"{contact_dict.get("first_name")} {contact_dict.get("last_name")}"
    current_contact.full_name = full_name
    current_contact.updated_at = str(datetime.now())
    current_contact.modifier_id = current_user.id
    db.add(current_contact)
    db.commit()
    db.refresh(current_contact)
    return current_contact

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: Annotated[UUID, Path(title="The ID of the contact to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing contact
    """
    current_contact = db.get(Contact, contact_id)
    if not current_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    if current_contact.organization_id != current_user.organization_id:
        return
    db.delete(current_contact)
    db.commit()
    return