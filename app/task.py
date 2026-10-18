from .utils import getdate, add_to_date, get_datetime
from datetime import datetime, time, timedelta
from .db import engine, Session, get_db, select, col, or_, exists
from .models import MaintenanceSchedule, WorkOrder

MAINTENANCE_TYPE_MAP = {
    "Preventive": "Preventive Maintenance",
    "Corrective": "Corrective Maintenance",
    "Predictive": "Predictive Maintenance",
    "Routine": "Routine Maintenance",
    "Emergency": "Emergency Maintenance",
    "Inspection": "Inspection Request",
    "Repair": "General Repair",
    "Replacement": "Replacement Request",
    "Calibration": "Other"
}

async def create_maintenance_order():
    start = getdate()
    end = add_to_date(start, days=1)
    with await get_db() as db:
        statement = select(MaintenanceSchedule).where(
            MaintenanceSchedule.next_schedule_date >= start,
            MaintenanceSchedule.next_schedule_date < end,
            MaintenanceSchedule.status == "Active",
            ~exists(
                select(WorkOrder.id).where(
                    WorkOrder.maintenance_schedule_id == MaintenanceSchedule.id,
                    WorkOrder.scheduled_date >= start,
                    WorkOrder.scheduled_date < end,
                )
            )
        )
        due_maintenances = db.exec(statement).all()
        for maintenance in due_maintenances:
            work_order = WorkOrder(
                customer_id = maintenance.customer_id,
                address = maintenance.address,
                address_geolocation = maintenance.address_geolocation,
                organization_id = maintenance.organization_id,
                subject = maintenance.subject,
                description = maintenance.description,
                category = MAINTENANCE_TYPE_MAP[maintenance.maintenance_type],
                priority = maintenance.priority,
                asset_type_id = maintenance.asset_type_id,
                scheduled_date = work_order.scheduled_date,
                instructions = maintenance.instructions,
                assignee_type = maintenance.assignee_type,
                assignee_id = maintenance.assignee_id,
                require_pow = maintenance.require_pow,
                currency = maintenance.currency,
                labour_cost = maintenance.labour_cost,
                tax = maintenance.tax,
                # order_items = order_items,
                owner_id=maintenance.owner_id,
                modifier_id=maintenance.modifier_id,
                created_at=str(get_datetime()),
                updated_at=str(get_datetime())
            )

            # Update next schedule date on schedule
            repeat_interval = maintenance.interval or 0
            repeat_days = repeat_interval if maintenance.interval_unit == "Days" else 0
            repeat_weeks = repeat_interval if maintenance.interval_unit == "Weeks" else 0
            repeat_months = repeat_interval if maintenance.interval_unit == "Months" else 0
            repeat_years = repeat_interval if maintenance.interval_unit == "Years" else 0
            next_schedule_date = add_to_date(
                maintenance.next_schedule_date,
                days=repeat_days,
                weeks=repeat_weeks,
                months=repeat_months,
                years=repeat_years
            )
            maintenance.next_schedule_date = next_schedule_date

            db.add(work_order)
            db.add(maintenance)
        db.commit()


#TODO: Mark schedule as completed
#TODO: Send maintenance reminders