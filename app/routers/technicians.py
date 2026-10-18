from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header, File, UploadFile
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import Technician, User, File as FileUpload
from ..utils import FilterParams, get_current_user, upload_file, get_datetime
from .users import get_password_hash
import sqlalchemy
from sqlalchemy.orm import joinedload, selectinload

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

class TechnicianFilterParams(FilterParams):
    organization_id: UUID
    is_online: bool | None = None

class TechnicianModel(BaseModel):
    model_config = {"extra": "forbid"}
    title: str | None = None
    first_name: str
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    password: str | None = None
    image: str | None = None
    address: str | None = None
    geolocation: str | None = None
    user_id: str | None = None
    rating: float | None = None
    organization_id: UUID | None


router = APIRouter(
    prefix="/v1/technicians",
    tags=["technicians"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Technician not found"}},
)

@router.get("/{technician_id}")
async def get_technician(
    technician_id: Annotated[UUID, Path(title="The ID of the technician to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single technician
    """
    technician = db.exec(select(Technician).where(
        Technician.id == technician_id,
        Technician.organization_id == current_user.organization.id
    )).first()
    if not technician:
        raise HTTPException(status_code=404, detail="Technician not found")
    resp_data = {
        **technician.model_dump(),
        "user": technician.user,
        "created_by": technician.created_by
    }
    return resp_data

@router.get("/")
async def get_technicians(
    filter_query: Annotated[TechnicianFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered technicians
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(Technician).where(
        Technician.organization_id == current_user.organization_id
    ).offset(offset).limit(limit).options(selectinload(Technician.created_by))
    technicians = db.exec(statement).all()
    resp_data = [{
        **technician.model_dump(),
        "image": "" if not technician.image else technician.image.file_name,
        "user": technician.user,
        "created_by": technician.created_by
    } for technician in technicians]
    return resp_data

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_technician(
    technician: TechnicianModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Technician:
    """
       Create new technician
    """
    full_name = technician.first_name
    if technician.last_name:
        full_name = f"{technician.first_name} {technician.last_name}"
    user = None
    user_id = None
    statement = select(User).where(or_(
        User.email == technician.email,
        User.phone == technician.phone,
    ))
    user = db.exec(statement).first()
    if user:
        user_id = user.id
    else:
        user = User(
            first_name = technician.first_name,
            last_name = technician.last_name,
            full_name = full_name,
            email = technician.email,
            phone = technician.phone,
            password = get_password_hash(technician.password),
            address = technician.address,
            user_type = "Technician",
            organization_id = technician.organization_id or current_user.organization_id
        )
    technician = Technician(
        title = technician.title,
        first_name = technician.first_name,
        last_name = technician.last_name,
        full_name = full_name,
        email = technician.email,
        phone = technician.phone,
        image = technician.image,
        address = technician.address,
        user_id = user_id,
        user = user,
        organization_id = technician.organization_id or current_user.organization_id,
        owner_id=current_user.id,
        modifier_id=current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    try:
        db.add(technician)
        db.commit()
        db.refresh(technician)
        return technician
    except sqlalchemy.exc.IntegrityError as e:
        # e.args => ('(sqlite3.IntegrityError) UNIQUE constraint failed: technician.phone',)
        duplicate_field = e.args[0].split('.')[-1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Duplicate entry for {duplicate_field}: {technician.model_dump().get('phone')}"
        ) from e


@router.put("/{technician_id}", status_code=status.HTTP_200_OK)
async def update_technician(
    technician_id: Annotated[UUID, Path(title="The ID of the technician to update")],
    technician: TechnicianModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Technician:
    """
        Update existing technician
    """
    current_technician = db.get(Technician, technician_id)
    if not current_technician:
        raise HTTPException(status_code=404, detail="Technician not found")
    if current_technician.organization_id != current_user.organization_id:
        return current_technician
    technician_dict = technician.model_dump(exclude_unset=True)
    for k, v in technician_dict.items():
        if k == 'organization_id':
            continue
        current_technician.sqlmodel_update({k: v})
    
    full_name = technician_dict.get("first_name")
    if technician_dict.get("last_name"):
        full_name = f"{technician_dict.get("first_name")} {technician_dict.get("last_name")}"
    current_technician.full_name = full_name
    current_technician.updated_at = get_datetime()
    current_technician.modifier_id = current_user.id
    db.add(current_technician)
    db.commit()
    db.refresh(current_technician)
    return current_technician

@router.put("/upload-image/{technician_id}", status_code=status.HTTP_200_OK)
async def upload_profile_image(
    technician_id: Annotated[UUID, Path(title="The ID of the technician to update")],
    image: Annotated[UploadFile, File(description="Technician profile image")],
    session_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
    Upload profile image
    """
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported file type")

    current_technician = db.get(Technician, technician_id)
    if not current_technician:
        raise HTTPException(status_code=404, detail="Technician not found")

    file_data = upload_file(image)

    file_upload = FileUpload(
        file_name = file_data.get("filename"),
        file_type = file_data.get("file_type"),
        file_size = file_data.get("file_size"),
        formated_size = file_data.get("formated_size"),
        file_url = file_data.get("url"),
        record_type = "Technician",
        record_id = current_technician.id,
        record_field = "image",
        owner_id = session_user.id
    )
    db.add(file_upload)
    
    current_technician.updated_at = get_datetime()
    current_technician.modifier_id = session_user.id
    db.add(current_technician)
    db.commit()
    db.refresh(current_technician)
    resp_data = {
        **current_technician.model_dump(),
        "image": "" if not current_technician.image else current_technician.image.file_name,
        "created_by": current_technician.created_by
    }
    return resp_data

@router.delete("/{technician_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_technician(
    technician_id: Annotated[UUID, Path(title="The ID of the technician to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing technician
    """
    current_technician = db.get(Technician, technician_id)
    if not current_technician:
        raise HTTPException(status_code=404, detail="Technician not found")
    if current_technician.organization_id != current_user.organization_id:
        return
    db.delete(current_technician)
    db.commit()
    return