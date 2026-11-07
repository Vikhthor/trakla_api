from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import User, File
from ..utils import FilterParams, get_current_user, get_datetime

class FileFilterParams(FilterParams):
    record_type: str | None = None
    record_id: UUID | None = None

class FileModel(BaseModel):
    model_config = {"extra": "forbid"}
    file_name: str
    record_type: str | None = None
    record_id: UUID | None = None
    record_field: str | None = None

router = APIRouter(
    prefix="/v1/files",
    tags=["files"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "File not found"}},
)

@router.get("/{file_id}")
async def get_file(
    file_id: Annotated[UUID, Path(title="The ID of the file to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single customer group
    """
    file = db.exec(select(File).where(
        File.id == file_id
    )).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file

@router.get("/")
async def get_files(
    filter_query: Annotated[FileFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered files
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(File).offset(offset).limit(limit)
    files = db.exec(statement).all()
    return files

@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: Annotated[UUID, Path(title="The ID of the file to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing file
    """
    current_file = db.get(File, file_id)
    if not current_file:
        raise HTTPException(status_code=404, detail="File not found")
    if current_file.owner_id != current_user.id:
        return
    db.delete(current_file)
    db.commit()
    return