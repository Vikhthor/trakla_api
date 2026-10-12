from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header
from pydantic import BaseModel, AfterValidator, Field, ConfigDict
from enum import Enum
from typing import Annotated, Literal
import random
from datetime import datetime, date
from uuid import UUID
from ..db import Session, get_db, select, col, or_, get_count, func, case
from ..models import WorkOrder, User, Customer, ServiceRequest, Technician
from ..utils import FilterParams, get_current_user, getdate, get_datetime, add_to_date, get_first_day, flt

class AnalyticsFilterParams(FilterParams):
    organization_id: UUID
    customer_id: UUID | None = None
    from_date: str | None = None
    to_date: str | None = None

class StatusTimelinePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: date
    total_count: int
    open: int
    completed: int

router = APIRouter(
    prefix="/v1/analytics",
    tags=["analytics"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Data not found"}},
)

@router.get("/dashboard-stats")
async def get_dashboard_stats(
    filter_query: Annotated[AnalyticsFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get dashboard stats data
    """
    # pylint: disable=not-callable
    from_date = filter_query.from_date
    to_date = get_datetime(filter_query.to_date)
    if from_date:
        from_date = getdate(from_date)
    else:
        from_date = get_first_day(add_to_date(to_date, months=-6))

    customer_id = filter_query.customer_id #TODO: Define util function to get customer from user

    resp_data = []

    total_work_orders = get_count(WorkOrder, db, {
        "organization_id": current_user.organization_id,
        "assignee_id": current_user.id if current_user.user_type == "technician" else None,
        "customer_id": customer_id
    })
    new_work_orders = get_count(WorkOrder, db, {
        "organization_id": current_user.organization_id,
        "created_at": ["between", [from_date, to_date]],
        "assignee_id": current_user.id if current_user.user_type == "technician" else None,
        "customer_id": customer_id
    })
    work_order_rate = 0
    if total_work_orders != new_work_orders:
        work_order_rate = flt((new_work_orders/(total_work_orders-new_work_orders))*100, 2)
    work_order_remark = "No changes"
    if work_order_rate > 0:
        work_order_remark = "Trending Up this period"
    elif work_order_rate < 0:
        work_order_remark = "Trending Down this period"

    resp_data.append({
        "type": "total_work_orders",
        "result": total_work_orders,
        "rate": work_order_rate,
        'rate_description': "New work orders for the last 6 months",
        'rate_remark': work_order_remark
    })
    if current_user.user_type != "technician":
        # Get Customers Stats
        total_customers = get_count(Customer, db, {
            "organization_id": current_user.organization_id
        })
        new_customers = get_count(Customer, db, {
            "organization_id": current_user.organization_id,
            "created_at": ["between", [from_date, to_date]]
        })
        customer_rate = 100
        if total_customers != new_customers:
            customer_rate = flt((new_customers/(total_customers-new_customers))*100, 2)
        customer_remark = "No changes"
        if customer_rate > 0:
            customer_remark = "Trending Up this period"
        elif customer_rate < 0:
            customer_remark = "Trending Down this period"
        
        resp_data.append({
            "type": "total_customers",
            "result": total_customers,
            "rate": customer_rate,
            'rate_description': "New customers for the last 6 months",
            'rate_remark': customer_remark
        })

        # Get Service Request Stats
        total_service_requests = get_count(ServiceRequest, db, {
            "organization_id": current_user.organization_id
        })
        new_service_requests = get_count(ServiceRequest, db, {
            "organization_id": current_user.organization_id,
            "created_at": ["between", [from_date, to_date]]
        })
        service_request_rate = 0
        if total_service_requests != new_service_requests:
            service_request_rate = flt((new_service_requests/(total_service_requests-new_service_requests))*100, 2)
        service_request_remark = "No changes"
        if service_request_rate > 0:
            service_request_remark = "Trending Up this period"
        elif service_request_rate < 0:
            service_request_remark = "Trending Down this period"

        resp_data.append({
            "type": "total_service_requests",
            "result": total_service_requests,
            "rate": service_request_rate,
            'rate_description': "New service requests for the last 6 months",
            'rate_remark': service_request_remark
        })
    else:
        techncian = db.exec(select(Technician).where(Technician.user_id == current_user.id)).first()
        statement = select(func.count(WorkOrder.id))\
            .join(ServiceRequest)\
            .where(
                ServiceRequest.id == WorkOrder.service_request_id,
                ServiceRequest.rating > 0,
                WorkOrder.assignee_id == current_user.id
            )
        total_rated_orders = db.exec(statement).scalar()

        work_order_review_rate = 0
        if total_work_orders:
            work_order_review_rate = flt((total_rated_orders/total_work_orders)*100, 2)

        rating_remark = "No ratings"
        if rating_remark == 3:
            rating_remark = "Average rating"
        elif rating_remark >= 3:
            rating_remark = "Above average rating"
        elif rating_remark < 3:
            rating_remark = "Below average rating"
        
        resp_data.append({
            "type": "total_rating",
            "result": 0 if not techncian else techncian.rating,
            "rate": work_order_review_rate,
            'rate_description': "Reviewed work orders for the last 6 months",
            'rate_remark': rating_remark
        })
    
    total_active_orders = get_count(WorkOrder, db, {
        "organization_id": current_user.organization_id,
        "status": ["in", ["Scheduled", "Assigned", "In Progress", "Quality Check"]],
        "assignee_id": current_user.id if current_user.user_type == "technician" else None,
        "customer_id": customer_id
    })
    total_completed_orders = get_count(WorkOrder, db, {
        "organization_id": current_user.organization_id,
        "status": ["in", ["Closed", "Completed", "Cancelled"]],
        "assignee_id": current_user.id if current_user.user_type == "technician" else None,
        "customer_id": customer_id
    })

    uncompleted_orders = total_work_orders - total_completed_orders
    active_orders_rate = 0
    if uncompleted_orders != total_active_orders:
        active_orders_rate = flt((total_active_orders/(uncompleted_orders-total_active_orders))*100, 2)
    active_orders_remark = "Engagement meets SLA expectations"
    if active_orders_rate < 50:
        active_orders_remark = "Engagement falls below SLA expectations"
    elif uncompleted_orders and active_orders_rate > 50:
        active_orders_remark = "Engagement exceeds SLA expectations"

    resp_data.append({
        "type": "total_active_orders",
        "result": total_active_orders,
        "rate": active_orders_rate,
        'rate_description': "Work order engagement SLA",
        'rate_remark': active_orders_remark
    })

    completed_orders_rate = 100
    if total_work_orders:
        completed_orders_rate = flt((total_completed_orders/total_work_orders)*100, 2)
    completed_orders_remark = "Completion meets SLA expectations"
    if completed_orders_rate < 50:
        completed_orders_remark = "Completion falls below SLA expectations"
    elif total_work_orders and completed_orders_rate > 50:
        completed_orders_remark = "Completion exceeds SLA expectations"

    resp_data.append({
        "type": "total_completed_orders",
        "result": total_completed_orders,
        "rate": completed_orders_rate,
        'rate_description': "Work order completion SLA",
        'rate_remark': completed_orders_remark
    })
    return resp_data

@router.get("/status-timeline", response_model=list[StatusTimelinePoint])
async def get_status_timeline(
    filter_query: Annotated[AnalyticsFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
       Get work orders status timeline aggregates
    """
    from_date = filter_query.from_date
    to_date = getdate(filter_query.to_date)
    if from_date:
        from_date = getdate(from_date)
    else:
        from_date = get_first_day(add_to_date(to_date, months=-3))

    # pylint: disable=not-callable
    # pylint: disable=no-member
    # Extract the month/year boundary (PostgreSQL example using func.date_trunc('month', WorkOrder.created_at))
    # For SQLite, use: func.strftime('%Y-%m', WorkOrder.created_at)
    # For MySQL, use: func.date_format(WorkOrder.created_at, '%Y-%m')
    month_bucket = func.strftime('%Y-%m-%d', WorkOrder.created_at).label("date")
    open_statuses = ["Open","Scheduled","Assigned","In Progress","On Hold","Quality Check"]
    closed_statuses = ["Closed","Completed","Cancelled"]
    stmt = select(
        month_bucket,
        func.sum(case((col(WorkOrder.status).in_(open_statuses), 1), else_=0)).label("open"),
        func.sum(case((col(WorkOrder.status).in_(closed_statuses), 1), else_=0)).label("completed"),
        func.count(WorkOrder.id).label("total_count")  # Optional: overall total
    ).where(
        WorkOrder.organization_id == current_user.organization_id,
        WorkOrder.created_at >= from_date,
        WorkOrder.created_at <= to_date,
    ).group_by(month_bucket).order_by(month_bucket.asc())
    results = db.exec(stmt).all()
    print("results XXXXXXXXXX",results)
    return results

@router.get("/operation-highlights")
async def get_operation_highlights(
    filter_query: Annotated[AnalyticsFilterParams, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
        Get filtered operational resources
    """
    # pylint: disable=no-member
    open_statuses = ["Open","Scheduled","Assigned","In Progress","On Hold","Quality Check"]
    statement = select(WorkOrder).where(
        WorkOrder.organization_id == current_user.organization_id,
        col(WorkOrder.status).in_(open_statuses)
    ).order_by(col(WorkOrder.created_at).desc())
    pending_work_orders = db.exec(statement).all()

    statement = select(WorkOrder).where(
        WorkOrder.organization_id == current_user.organization_id,
        col(WorkOrder.status).in_(open_statuses),
        col(WorkOrder.maintenance_schedule_id).is_not(None)
    ).order_by(col(WorkOrder.created_at).desc())
    pending_maintenance = db.exec(statement).all()

    statement = select(ServiceRequest).where(
        ServiceRequest.organization_id == current_user.organization_id,
        ServiceRequest.status == "Open"
    ).order_by(col(ServiceRequest.created_at).desc())
    pending_service_requests = db.exec(statement).all()

    statement = select(Technician).where(
        Technician.organization_id == current_user.organization_id,
    ).order_by(col(Technician.rating).desc())
    result = db.exec(statement).all()
    top_technicians = [{**technician.model_dump(), "user": technician.user} for technician in result]

    resp_data = {
        "pending_work_orders": [{
            **order.model_dump(),
            "customer_name": order.customer.customer_name,
            "assignee": order.assignee,
            "order_items": order.order_items,
            "created_by": order.created_by
        } for order in pending_work_orders],
        "pending_service_requests": pending_service_requests,
        "top_technicians": top_technicians,
        "pending_maintenance": pending_maintenance
    }
    return resp_data