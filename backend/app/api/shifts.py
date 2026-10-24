from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime, date, timedelta
import calendar
from typing import List, Optional, Dict, Any

from app.core.database import get_db
from app.models.shift import Shift, EmployeeShiftAssignment
from app.models.employee import Employee
from app.models.attendance import AttendancePunchEvent, DailyAttendance
from app.core.audit import log_audit
from app.schemas.shift import (
    ShiftCreate, ShiftUpdate, ShiftResponse, ShiftStatusToggle, ShiftRulesUpdate,
    MonthlyScheduleSaveRequest, AutoFillPatternRequest, DailyAssignmentItem
)

router = APIRouter()


# -------------------------------------------------------------
# SHIFT MASTER CRUD (Settings Page)
# -------------------------------------------------------------

@router.get("/", response_model=List[ShiftResponse])
def get_all_shifts(
    search: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    query = db.query(Shift)
    if search:
        query = query.filter(or_(
            Shift.code.ilike(f"%{search}%"),
            Shift.name.ilike(f"%{search}%")
        ))
    if status_filter and status_filter != "All":
        if status_filter in ("Active", "Enabled", "true", "1"):
            query = query.filter(Shift.is_active == True)
        elif status_filter in ("Inactive", "Disabled", "false", "0"):
            query = query.filter(Shift.is_active == False)

    return query.order_by(Shift.code.asc()).all()


@router.get("/active", response_model=List[ShiftResponse])
def get_active_shifts(db: Session = Depends(get_db)):
    """Return all active shifts for dropdowns, selectors, and calendar legends."""
    return db.query(Shift).filter(Shift.is_active == True).order_by(Shift.code.asc()).all()


@router.get("/{id}", response_model=ShiftResponse)
def get_shift_by_id(id: int, db: Session = Depends(get_db)):
    shift = db.query(Shift).filter(Shift.id == id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift


@router.post("/", response_model=ShiftResponse, status_code=status.HTTP_201_CREATED)
def create_shift(payload: ShiftCreate, db: Session = Depends(get_db)):
    # Validate uniqueness of code
    code_clean = payload.code.strip().upper()
    existing = db.query(Shift).filter(Shift.code.ilike(code_clean)).first()
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Shift with code '{code_clean}' already exists (ID: {existing.id}, Name: {existing.name})."
        )

    # Basic time validation
    if not payload.start_time or not payload.end_time:
        raise HTTPException(status_code=400, detail="Start time and end time are required.")

    data = payload.model_dump()
    data["code"] = code_clean
    new_shift = Shift(**data)
    db.add(new_shift)
    db.commit()
    db.refresh(new_shift)

    log_audit(
        db,
        action="CREATE_SHIFT",
        category="shift",
        username="admin",
        target_type="shift",
        target_id=new_shift.code,
        details=f"Created shift '{new_shift.code} - {new_shift.name}' ({new_shift.start_time} to {new_shift.end_time})."
    )

    return new_shift


@router.put("/{id}", response_model=ShiftResponse)
def update_shift(id: int, payload: ShiftUpdate, db: Session = Depends(get_db)):
    shift = db.query(Shift).filter(Shift.id == id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    data = payload.model_dump(exclude_unset=True)
    if "code" in data and data["code"]:
        code_clean = data["code"].strip().upper()
        existing = db.query(Shift).filter(Shift.code.ilike(code_clean), Shift.id != id).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Shift code '{code_clean}' is already used by another shift.")
        data["code"] = code_clean

    for k, v in data.items():
        setattr(shift, k, v)

    db.commit()
    db.refresh(shift)

    log_audit(
        db,
        action="UPDATE_SHIFT",
        category="shift",
        username="admin",
        target_type="shift",
        target_id=shift.code,
        details=f"Updated shift parameters for '{shift.code} - {shift.name}'."
    )

    return shift


@router.patch("/{id}/status", response_model=ShiftResponse)
def toggle_shift_status(id: int, payload: ShiftStatusToggle, db: Session = Depends(get_db)):
    shift = db.query(Shift).filter(Shift.id == id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    shift.is_active = payload.is_active
    db.commit()
    db.refresh(shift)

    log_audit(
        db,
        action="TOGGLE_SHIFT_STATUS",
        category="shift",
        username="admin",
        target_type="shift",
        target_id=shift.code,
        details=f"Set shift '{shift.code}' status to {'Active' if shift.is_active else 'Disabled'}."
    )

    return shift


@router.put("/{id}/rules", response_model=ShiftResponse)
def update_shift_rules(id: int, payload: ShiftRulesUpdate, db: Session = Depends(get_db)):
    shift = db.query(Shift).filter(Shift.id == id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    shift.first_half_start_cutoff = payload.first_half_start_cutoff
    shift.first_half_end_start = payload.first_half_end_start
    shift.first_half_end_end = payload.first_half_end_end
    shift.second_half_start_start = payload.second_half_start_start
    shift.second_half_start_end = payload.second_half_start_end
    shift.second_half_end_cutoff = payload.second_half_end_cutoff

    db.commit()
    db.refresh(shift)

    log_audit(
        db,
        action="UPDATE_SHIFT_RULES",
        category="shift",
        username="admin",
        target_type="shift",
        target_id=shift.code,
        details=f"Updated biometric punch rules and cutoffs for shift '{shift.code}'."
    )

    return shift


@router.delete("/{id}")
def delete_shift(id: int, db: Session = Depends(get_db)):
    shift = db.query(Shift).filter(Shift.id == id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    # Check if any assignments or attendance records exist using this shift
    assignments_count = db.query(EmployeeShiftAssignment).filter(EmployeeShiftAssignment.shift_id == id).count()
    if assignments_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete shift '{shift.code}'. It is assigned to {assignments_count} date schedules. Deactivate it instead."
        )

    shift_code = shift.code
    shift_name = shift.name
    db.delete(shift)
    db.commit()

    log_audit(
        db,
        action="DELETE_SHIFT",
        category="shift",
        username="admin",
        target_type="shift",
        target_id=shift_code,
        details=f"Deleted shift '{shift_code} - {shift_name}'."
    )

    return {"status": "success", "message": f"Shift '{shift_code} - {shift_name}' deleted successfully."}



# -------------------------------------------------------------
# EMPLOYEE MONTHLY SHIFT ASSIGNMENT (Calendar & Scheduling)
# -------------------------------------------------------------

@router.get("/employee/{employee_id}/monthly")
def get_employee_monthly_schedule(
    employee_id: str,
    year: int = Query(..., ge=2020, le=2050),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db)
):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found.")

    _, days_in_month = calendar.monthrange(year, month)
    start_d = date(year, month, 1)
    end_d = date(year, month, days_in_month)

    # Fetch all assignments in this month
    assignments = db.query(EmployeeShiftAssignment).filter(
        EmployeeShiftAssignment.employee_id == employee_id,
        EmployeeShiftAssignment.assignment_date >= start_d,
        EmployeeShiftAssignment.assignment_date <= end_d
    ).all()

    assign_map = {}
    for a in assignments:
        s = a.shift
        assign_map[str(a.assignment_date.day)] = {
            "shift_id": a.shift_id,
            "shift_code": s.code if s else ("OFF" if a.is_off else None),
            "shift_name": s.name if s else ("Day Off" if a.is_off else None),
            "color": s.color if s else ("slate" if a.is_off else None),
            "is_off": a.is_off,
            "notes": a.notes
        }

    # Also fetch all active shifts for legend
    active_shifts = db.query(Shift).filter(Shift.is_active == True).order_by(Shift.code.asc()).all()
    shifts_list = [
        {
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "color": s.color,
            "is_overnight": s.is_overnight
        }
        for s in active_shifts
    ]

    return {
        "employee": {
            "id": emp.id,
            "name": emp.name,
            "department": emp.department or "Operations",
            "designation": emp.designation or "Staff"
        },
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "days_in_month": days_in_month,
        "first_day_weekday": date(year, month, 1).weekday(), # 0=Monday, 6=Sunday
        "assignments": assign_map,
        "active_shifts": shifts_list
    }


@router.post("/employee/{employee_id}/monthly")
def save_employee_monthly_schedule(
    employee_id: str,
    payload: MonthlyScheduleSaveRequest,
    db: Session = Depends(get_db)
):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found.")

    year = payload.year
    month = payload.month
    _, days_in_month = calendar.monthrange(year, month)
    start_d = date(year, month, 1)
    end_d = date(year, month, days_in_month)

    # Validate shifts
    valid_shift_ids = {s.id: s for s in db.query(Shift).all()}

    saved_count = 0
    updated_dates = set()

    for item in payload.assignments:
        try:
            d_obj = datetime.strptime(item.date, "%Y-%m-%d").date()
        except ValueError:
            continue

        if d_obj.year != year or d_obj.month != month:
            continue

        updated_dates.add(d_obj)

        existing = db.query(EmployeeShiftAssignment).filter(
            EmployeeShiftAssignment.employee_id == employee_id,
            EmployeeShiftAssignment.assignment_date == d_obj
        ).first()

        s_id = item.shift_id if (item.shift_id in valid_shift_ids and not item.is_off) else None

        if not existing:
            new_assign = EmployeeShiftAssignment(
                employee_id=employee_id,
                shift_id=s_id,
                assignment_date=d_obj,
                is_off=item.is_off,
                notes=item.notes,
                status="SCHEDULED"
            )
            db.add(new_assign)
        else:
            existing.shift_id = s_id
            existing.is_off = item.is_off
            existing.notes = item.notes
            existing.status = "SCHEDULED"

        saved_count += 1

    db.commit()

    # Automatically recalculate attendance for any days in this month that have punches for this employee!
    from app.services.attendance_service import evaluate_and_save_employee_daily_attendance
    for d_obj in sorted(updated_dates):
        # If there are punches on this date, update the daily_attendance record
        evaluate_and_save_employee_daily_attendance(db, employee_id, d_obj)

    return {
        "status": "success",
        "message": f"Successfully saved {saved_count} shift assignments for {emp.name} ({calendar.month_name[month]} {year})."
    }


@router.post("/employee/{employee_id}/monthly/pattern")
def generate_auto_fill_pattern(
    employee_id: str,
    payload: AutoFillPatternRequest,
    db: Session = Depends(get_db)
):
    """
    Generate a deterministic, reproducible month schedule without random selection.
    Returns draft assignments for admin preview and adjustment before saving.
    """
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found.")

    year = payload.year
    month = payload.month
    _, days_in_month = calendar.monthrange(year, month)

    start_day = 1
    if payload.start_date:
        try:
            start_dt = datetime.strptime(payload.start_date, "%Y-%m-%d").date()
            if start_dt.year == year and start_dt.month == month:
                start_day = start_dt.day
        except ValueError:
            pass

    shifts_by_id = {s.id: s for s in db.query(Shift).all()}
    draft_assignments: Dict[str, Any] = {}

    if payload.pattern_mode == "weekly_standard":
        # Mon-Fri: primary_shift, Sat-Sun: OFF
        prim_shift = shifts_by_id.get(payload.primary_shift_id)
        for day in range(1, days_in_month + 1):
            cur_d = date(year, month, day)
            # weekday: 0=Mon, 5=Sat, 6=Sun
            is_weekend = cur_d.weekday() in (5, 6)
            if is_weekend:
                draft_assignments[str(day)] = {
                    "date": cur_d.strftime("%Y-%m-%d"),
                    "shift_id": None,
                    "shift_code": "OFF",
                    "shift_name": "Day Off",
                    "color": "slate",
                    "is_off": True
                }
            else:
                draft_assignments[str(day)] = {
                    "date": cur_d.strftime("%Y-%m-%d"),
                    "shift_id": prim_shift.id if prim_shift else None,
                    "shift_code": prim_shift.code if prim_shift else None,
                    "shift_name": prim_shift.name if prim_shift else None,
                    "color": prim_shift.color if prim_shift else "emerald",
                    "is_off": False
                }

    elif payload.pattern_mode == "work6_off1":
        # 6 working days on primary shift, 1 day off (Sunday or repeating)
        prim_shift = shifts_by_id.get(payload.primary_shift_id)
        for day in range(1, days_in_month + 1):
            cur_d = date(year, month, day)
            is_off = (cur_d.weekday() == 6) # Sunday Off
            draft_assignments[str(day)] = {
                "date": cur_d.strftime("%Y-%m-%d"),
                "shift_id": None if is_off else (prim_shift.id if prim_shift else None),
                "shift_code": "OFF" if is_off else (prim_shift.code if prim_shift else None),
                "shift_name": "Day Off" if is_off else (prim_shift.name if prim_shift else None),
                "color": "slate" if is_off else (prim_shift.color if prim_shift else "emerald"),
                "is_off": is_off
            }

    elif payload.pattern_mode == "custom_rotation" and payload.custom_sequence:
        # Expand custom sequence of steps deterministically
        flat_sequence = []
        for step in payload.custom_sequence:
            s_obj = shifts_by_id.get(step.shift_id) if step.shift_id else None
            for _ in range(max(1, step.days_count)):
                flat_sequence.append({
                    "shift_id": s_obj.id if (s_obj and not step.is_off) else None,
                    "shift_code": "OFF" if step.is_off else (s_obj.code if s_obj else None),
                    "shift_name": "Day Off" if step.is_off else (s_obj.name if s_obj else None),
                    "color": "slate" if step.is_off else (s_obj.color if s_obj else "emerald"),
                    "is_off": step.is_off
                })

        if flat_sequence:
            seq_len = len(flat_sequence)
            seq_idx = 0
            for day in range(1, days_in_month + 1):
                cur_d = date(year, month, day)
                if day >= start_day:
                    step_data = flat_sequence[seq_idx % seq_len]
                    draft_assignments[str(day)] = {
                        "date": cur_d.strftime("%Y-%m-%d"),
                        **step_data
                    }
                    seq_idx += 1

    return {
        "status": "success",
        "employee_id": employee_id,
        "year": year,
        "month": month,
        "draft_assignments": draft_assignments
    }


@router.delete("/employee/{employee_id}/monthly")
def clear_employee_monthly_schedule(
    employee_id: str,
    year: int = Query(..., ge=2020, le=2050),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db)
):
    _, days_in_month = calendar.monthrange(year, month)
    start_d = date(year, month, 1)
    end_d = date(year, month, days_in_month)

    deleted = db.query(EmployeeShiftAssignment).filter(
        EmployeeShiftAssignment.employee_id == employee_id,
        EmployeeShiftAssignment.assignment_date >= start_d,
        EmployeeShiftAssignment.assignment_date <= end_d
    ).delete(synchronize_session=False)
    db.commit()

    return {
        "status": "success",
        "message": f"Cleared {deleted} shift assignments for {calendar.month_name[month]} {year}."
    }
