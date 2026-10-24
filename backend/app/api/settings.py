from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.database import get_db
from app.models.attendance import AttendancePunchEvent, DailyAttendance
from app.services.attendance_service import get_settings, save_settings
from app.services.seed_service import seed_demo_data
from app.schemas.settings import SystemSettings

from app.models.employee import Employee
from app.core.audit import log_audit

router = APIRouter()

@router.get("/")
def get_system_settings_api(db: Session = Depends(get_db)):
    return get_settings(db)

@router.post("/")
def update_system_settings_api(payload: SystemSettings, db: Session = Depends(get_db)):
    updated = save_settings(db, payload.model_dump())
    log_audit(
        db,
        action="UPDATE_SYSTEM_SETTINGS",
        category="system",
        username="admin",
        details="Updated general system attendance policy and thresholds."
    )
    return {"message": "Settings updated successfully", "settings": updated}

@router.post("/seed-demo")
def seed_demo(db: Session = Depends(get_db)):
    result = seed_demo_data(db, days=30)
    log_audit(
        db,
        action="SEED_DEMO_DATA",
        category="attendance",
        username="admin",
        details="Generated 30 days of simulated biometric attendance data for 12 demo employees."
    )
    return result

@router.post("/clear-data")
def clear_attendance_data(db: Session = Depends(get_db)):
    db.query(DailyAttendance).delete()
    db.query(AttendancePunchEvent).delete()
    db.commit()
    log_audit(
        db,
        action="CLEAR_ATTENDANCE_DATA",
        category="attendance",
        username="admin",
        details="Cleared all biometric punches and calculated daily attendance entries."
    )
    return {"message": "All biometric punches and daily attendance calculations have been cleared."}

@router.post("/remove-demo-data")
def remove_demo_data(db: Session = Depends(get_db)):
    demo_emp_ids = ["EMP101", "EMP102", "EMP103", "EMP104", "EMP105", "EMP106", "EMP107", "EMP108", "EMP109", "EMP110", "EMP111", "EMP112"]
    db.query(DailyAttendance).filter(DailyAttendance.employee_id.in_(demo_emp_ids)).delete(synchronize_session=False)
    db.query(AttendancePunchEvent).filter(
        or_(
            AttendancePunchEvent.employee_id.in_(demo_emp_ids),
            AttendancePunchEvent.source_id == "DEMO_BIOMETRIC_DEV_01"
        )
    ).delete(synchronize_session=False)
    deleted_count = db.query(Employee).filter(Employee.id.in_(demo_emp_ids)).delete(synchronize_session=False)
    db.commit()
    log_audit(
        db,
        action="REMOVE_DEMO_DATA",
        category="attendance",
        username="admin",
        details=f"Removed {deleted_count} demo employees (EMP101-EMP112) and their simulated attendance records."
    )
    return {
        "status": "success",
        "message": f"Successfully removed {deleted_count} demo employees (EMP101-EMP112) and their simulated attendance records."
    }

