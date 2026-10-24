from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta, time
from typing import List, Dict, Any

from app.core.database import get_db
from app.models.employee import Employee
from app.models.attendance import DailyAttendance, AttendancePunchEvent

router = APIRouter()

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    today = date.today()
    today_dt = datetime.combine(today, time.min)

    total_employees = db.query(Employee).filter(Employee.status == "Active").count()
    if total_employees == 0:
        return {
            "total_employees": 0,
            "present_today": 0,
            "absent_today": 0,
            "late_today": 0,
            "half_day_today": 0,
            "missing_punches_today": 0,
            "attendance_rate": 0.0,
            "average_work_hours": 0.0,
            "today_date": today.strftime("%Y-%m-%d")
        }

    # If no records exist for today yet, check if there's any latest date in daily_attendance
    latest_att = db.query(DailyAttendance.attendance_date).order_by(DailyAttendance.attendance_date.desc()).first()
    target_dt = today_dt
    if latest_att and latest_att[0]:
        # If today has zero records, use latest available date for display so dashboard isn't completely blank
        today_records = db.query(DailyAttendance).filter(DailyAttendance.attendance_date == today_dt).count()
        if today_records == 0:
            target_dt = latest_att[0]

    daily_records = db.query(DailyAttendance).filter(DailyAttendance.attendance_date == target_dt).all()
    
    present_count = 0
    absent_count = 0
    late_count = 0
    half_day_count = 0
    missing_count = 0
    total_mins = 0.0

    for r in daily_records:
        if r.attendance_status == "P":
            present_count += 1
        elif r.attendance_status == "HD":
            half_day_count += 1
        elif r.attendance_status == "A":
            absent_count += 1

        if r.late_minutes > 0:
            late_count += 1
        if r.missing_punch_flag:
            missing_count += 1
        total_mins += r.credited_work_minutes

    active_work_records = [r for r in daily_records if r.attendance_status in ("P", "HD")]
    avg_hours = round((total_mins / (len(active_work_records) * 60.0)), 1) if active_work_records else 0.0
    effective_present = present_count + (0.5 * half_day_count)
    att_rate = round((effective_present / total_employees * 100), 1) if total_employees > 0 else 0.0

    return {
        "total_employees": total_employees,
        "present_today": present_count,
        "absent_today": absent_count,
        "late_today": late_count,
        "half_day_today": half_day_count,
        "missing_punches_today": missing_count,
        "attendance_rate": att_rate,
        "average_work_hours": avg_hours,
        "today_date": target_dt.strftime("%Y-%m-%d")
    }

@router.get("/trends")
def get_attendance_trends(days: int = 7, db: Session = Depends(get_db)):
    """
    Returns last N days of attendance stats for chart visualization.
    """
    latest_att = db.query(DailyAttendance.attendance_date).order_by(DailyAttendance.attendance_date.desc()).first()
    if not latest_att or not latest_att[0]:
        return []

    max_date = latest_att[0].date()
    start_date = max_date - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, time.min)

    records = db.query(DailyAttendance).filter(
        DailyAttendance.attendance_date >= start_dt,
        DailyAttendance.attendance_date <= datetime.combine(max_date, time.max)
    ).all()

    by_date: Dict[str, Dict[str, int]] = {}
    for r in records:
        d_str = r.attendance_date.strftime("%Y-%m-%d")
        if d_str not in by_date:
            by_date[d_str] = {
                "date": d_str,
                "day_label": r.attendance_date.strftime("%a %d"),
                "present": 0,
                "absent": 0,
                "half_day": 0,
                "late": 0,
                "weekly_off": 0
            }
        if r.attendance_status == "P":
            by_date[d_str]["present"] += 1
        elif r.attendance_status == "A":
            by_date[d_str]["absent"] += 1
        elif r.attendance_status == "HD":
            by_date[d_str]["half_day"] += 1
        elif r.attendance_status == "WO":
            by_date[d_str]["weekly_off"] += 1

        if r.late_minutes > 0:
            by_date[d_str]["late"] += 1

    return [by_date[k] for k in sorted(by_date.keys())]

@router.get("/department-stats")
def get_department_stats(db: Session = Depends(get_db)):
    latest_att = db.query(DailyAttendance.attendance_date).order_by(DailyAttendance.attendance_date.desc()).first()
    target_dt = latest_att[0] if latest_att else datetime.combine(date.today(), time.min)

    employees = db.query(Employee).filter(Employee.status == "Active").all()
    dept_map: Dict[str, Dict[str, Any]] = {}

    for e in employees:
        d = e.department or "Other"
        dept_map.setdefault(d, {"department": d, "total": 0, "present": 0, "late": 0})
        dept_map[d]["total"] += 1

    attendances = db.query(DailyAttendance).filter(DailyAttendance.attendance_date == target_dt).all()
    emp_to_att = {a.employee_id: a for a in attendances}

    for e in employees:
        d = e.department or "Other"
        att = emp_to_att.get(e.id)
        if att:
            if att.attendance_status in ("P", "HD"):
                dept_map[d]["present"] += 1
            if att.late_minutes > 0:
                dept_map[d]["late"] += 1

    result = []
    for d, data in dept_map.items():
        rate = round((data["present"] / data["total"] * 100), 1) if data["total"] > 0 else 0.0
        data["attendance_rate"] = rate
        result.append(data)

    return sorted(result, key=lambda x: x["total"], reverse=True)

@router.get("/recent-punches")
def get_recent_punches(limit: int = 8, db: Session = Depends(get_db)):
    punches = db.query(AttendancePunchEvent).order_by(AttendancePunchEvent.punched_at.desc()).limit(limit).all()
    emp_ids = [p.employee_id for p in punches if p.employee_id]
    emps = {e.id: e for e in db.query(Employee).filter(Employee.id.in_(emp_ids)).all()}

    res = []
    for p in punches:
        emp = emps.get(p.employee_id)
        res.append({
            "id": p.id,
            "employee_id": p.employee_id,
            "employee_name": emp.name if emp else f"ID #{p.employee_id}",
            "department": emp.department if emp else "—",
            "punched_at": p.punched_at.strftime("%Y-%m-%d %H:%M:%S"),
            "time_str": p.punched_at.strftime("%I:%M %p"),
            "direction": p.source_direction or "AUTO",
            "source_id": p.source_id or "Biometric Terminal"
        })
    return res
