from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime, timedelta

from app.core.database import get_db
from app.models.leave import Leave
from app.models.employee import Employee
from app.services.attendance_service import evaluate_and_save_employee_daily_attendance

router = APIRouter()

class LeaveCreate(BaseModel):
    employee_id: str
    leave_type: str
    start_date: date
    end_date: date
    is_half_day: bool = False
    half_day_session: Optional[str] = None  # 'first_half', 'second_half'
    reason: Optional[str] = None
    applied_by: Optional[str] = "clerk"

class LeaveUpdate(BaseModel):
    leave_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_half_day: Optional[bool] = None
    half_day_session: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None

class LeaveStatusUpdate(BaseModel):
    status: str  # 'APPROVED', 'PENDING', 'REJECTED'
    approved_by: Optional[str] = None

def recalculate_leave_days(db: Session, employee_id: int, start_date: date, end_date: date):
    """Trigger daily attendance re-evaluation for the employee across leave dates."""
    cur = start_date
    while cur <= end_date:
        try:
            evaluate_and_save_employee_daily_attendance(db, str(employee_id), cur, force_override=True)
        except Exception as e:
            print(f"Error recalculating attendance for emp {employee_id} on {cur}: {e}")
        cur += timedelta(days=1)

@router.get("/")
def get_leaves(
    employee_id: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    query = db.query(Leave)

    if employee_id:
        query = query.filter(Leave.employee_id == employee_id)

    if status_filter and status_filter.upper() != "ALL":
        query = query.filter(Leave.status == status_filter.upper())

    if year and month:
        start_of_month = date(year, month, 1)
        if month == 12:
            end_of_month = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_of_month = date(year, month + 1, 1) - timedelta(days=1)
        # Leaves that overlap with this month
        query = query.filter(
            Leave.start_date <= end_of_month,
            Leave.end_date >= start_of_month
        )

    leaves = query.order_by(Leave.start_date.desc(), Leave.id.desc()).all()
    return [l.to_dict() for l in leaves]

@router.get("/{leave_id}")
def get_leave(leave_id: int, db: Session = Depends(get_db)):
    leave = db.query(Leave).filter(Leave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave record not found")
    return leave.to_dict()

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_leave(payload: LeaveCreate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == payload.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee {payload.employee_id} not found")

    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be earlier than start date")

    # Compute days count
    if payload.is_half_day:
        days_count = 0.5
    else:
        days_count = float((payload.end_date - payload.start_date).days + 1)

    new_leave = Leave(
        employee_id=payload.employee_id,
        leave_type=payload.leave_type.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        days_count=days_count,
        is_half_day=payload.is_half_day,
        half_day_session=payload.half_day_session,
        reason=payload.reason.strip() if payload.reason else "",
        status="APPROVED",  # Directly approved when logged by clerk/admin
        applied_by=payload.applied_by or "clerk",
        approved_by=payload.applied_by or "admin"
    )
    db.add(new_leave)
    db.commit()
    db.refresh(new_leave)

    # Recalculate daily attendance for affected days
    recalculate_leave_days(db, new_leave.employee_id, new_leave.start_date, new_leave.end_date)

    return new_leave.to_dict()

@router.put("/{leave_id}")
def update_leave(leave_id: int, payload: LeaveUpdate, db: Session = Depends(get_db)):
    leave = db.query(Leave).filter(Leave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    old_start = leave.start_date
    old_end = leave.end_date

    if payload.leave_type is not None:
        leave.leave_type = payload.leave_type.strip()
    if payload.start_date is not None:
        leave.start_date = payload.start_date
    if payload.end_date is not None:
        leave.end_date = payload.end_date
    if payload.is_half_day is not None:
        leave.is_half_day = payload.is_half_day
    if payload.half_day_session is not None:
        leave.half_day_session = payload.half_day_session
    if payload.reason is not None:
        leave.reason = payload.reason.strip()
    if payload.status is not None:
        leave.status = payload.status.upper()

    # Recalculate days count
    if leave.is_half_day:
        leave.days_count = 0.5
    else:
        leave.days_count = float((leave.end_date - leave.start_date).days + 1)

    db.commit()
    db.refresh(leave)

    # Recalculate old range and new range
    min_date = min(old_start, leave.start_date)
    max_date = max(old_end, leave.end_date)
    recalculate_leave_days(db, leave.employee_id, min_date, max_date)

    return leave.to_dict()

@router.patch("/{leave_id}/status")
def update_leave_status(leave_id: int, payload: LeaveStatusUpdate, db: Session = Depends(get_db)):
    leave = db.query(Leave).filter(Leave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    leave.status = payload.status.upper()
    if payload.approved_by:
        leave.approved_by = payload.approved_by

    db.commit()
    db.refresh(leave)

    recalculate_leave_days(db, leave.employee_id, leave.start_date, leave.end_date)
    return leave.to_dict()

@router.delete("/{leave_id}")
def delete_leave(leave_id: int, db: Session = Depends(get_db)):
    leave = db.query(Leave).filter(Leave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    emp_id = leave.employee_id
    start_d = leave.start_date
    end_d = leave.end_date

    db.delete(leave)
    db.commit()

    # Re-evaluate without leave
    recalculate_leave_days(db, emp_id, start_d, end_d)
    return {"success": True, "message": "Leave record deleted successfully"}
