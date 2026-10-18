from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime
from uuid import UUID
from ..db import engine, Session, get_db, select, col, or_
from ..models import ServiceRequest, ServiceRequestStatus, User
from ..utils import FilterParams, get_current_user, get_datetime

class ServiceRequestFilterParams(FilterParams):
    organization_id: UUID

class ServiceRequestModel(BaseModel):
    model_config = {"extra": "forbid"}
    subject: str
    description: str
    customer_id: UUID
    organization_id: UUID | None = None
    status: ServiceRequestStatus | None = None

class ServiceRequestUpdateModel(BaseModel):
    model_config = {"extra": "forbid"}
    subject: str | None = None
    description: str | None = None
    customer_id: UUID | None = None
    status: ServiceRequestStatus | None = None

router = APIRouter(
    prefix="/v1/service-requests",
    tags=["service-requests"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Service request not found"}},
)

@router.get("/{request_id}")
async def get_service_request(
    request_id: Annotated[UUID, Path(title="The ID of the service request to get")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get single service request
    """
    service_req = db.exec(select(ServiceRequest).where(
        ServiceRequest.id == request_id,
        ServiceRequest.organization_id == current_user.organization.id
    )).first()
    if not service_req:
        raise HTTPException(status_code=404, detail="Service request not found")
    resp_data = {
        **service_req.model_dump(),
        "customer_name": service_req.customer.customer_name,
        "created_by": service_req.created_by
    }
    return resp_data

@router.get("/")
async def get_service_requests(
    filter_query: Annotated[ServiceRequestFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get filtered service request
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(ServiceRequest).where(
        ServiceRequest.organization_id == current_user.organization_id
    ).offset(offset).limit(limit)
    service_reqs = db.exec(statement).all()
    resp_data = [{
        **service_req.model_dump(),
        "customer_name": service_req.customer.customer_name,
        "created_by": service_req.created_by
    } for service_req in service_reqs]
    return resp_data

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_service_request(
    service_request: ServiceRequestModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> ServiceRequest:
    """
       Create new service request
    """
    service_req = ServiceRequest(
        subject = service_request.subject,
        description = service_request.description,
        customer_id = service_request.customer_id,
        organization_id = service_request.organization_id or current_user.organization_id,
        owner_id=current_user.id,
        modifier_id=current_user.id,
        created_at=get_datetime(),
        updated_at=get_datetime()
    )
    db.add(service_req)
    db.commit()
    db.refresh(service_req)
    return service_req

@router.put("/{request_id}", status_code=status.HTTP_200_OK)
async def update_service_request(
    request_id: Annotated[UUID, Path(title="The ID of the service request to update")],
    service_request: ServiceRequestUpdateModel, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> ServiceRequest:
    """
        Update existing service request
    """
    current_req = db.get(ServiceRequest, request_id)
    if not current_req:
        raise HTTPException(status_code=404, detail="Service request not found")
    req_dict = service_request.model_dump(exclude_unset=True)
    for k, v in req_dict.items():
        current_req.sqlmodel_update({k: v})
    current_req.updated_at = get_datetime()
    current_req.modifier_id = current_user.id
    db.add(current_req)
    db.commit()
    db.refresh(current_req)
    return current_req

@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_order(
    request_id: Annotated[UUID, Path(title="The ID of the service request to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """
        Delete existing service request
    """
    current_order = db.get(ServiceRequest, request_id)
    if not current_order:
        raise HTTPException(status_code=404, detail="Service request not found")
    if current_order.organization_id != current_user.organization_id:
        return
    db.delete(current_order)
    db.commit()
    return