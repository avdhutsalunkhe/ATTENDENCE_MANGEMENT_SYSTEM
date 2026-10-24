from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime, date, time
from typing import List, Optional, Dict, Any
import pandas as pd
import io

from app.core.database import get_db
from app.models.employee import Employee
from app.models.attendance import AttendancePunchEvent, DailyAttendance
from app.schemas.attendance import (
    PunchEventResponse, DailyAttendanceResponse, DailyAttendanceUpdate,
    ManualPunchCreate, RecalculateRequest
)
from app.services.attendance_service import (
    import_punch_records, process_punches_for_date, get_settings
)

from app.core.importer_utils import (
    clean_emp_id, normalize_header, find_best_column, read_tabular_file, parse_punch_datetime
)

router = APIRouter()

@router.post("/import")
async def import_attendance_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload and parse attendance biometric files (.xlsx, .csv, .dat, .txt).
    Persists punches and calculates daily attendance automatically.
    """
    filename = file.filename or ""
    content = await file.read()
    records: List[Dict[str, Any]] = []

    try:
        if filename.endswith((".xlsx", ".xls", ".csv")):
            tables = read_tabular_file(content, filename)
            if not tables:
                raise HTTPException(status_code=400, detail="Uploaded attendance spreadsheet appears to be empty.")

            id_aliases = ['userid', 'user_id', 'user id', 'user id.', 'empid', 'emp_id', 'emp id', 'employeeid', 'employee_id', 'employee id', 'empcode', 'emp code', 'code', 'id', 'badge', 'badgenumber', 'acno', 'ac-no', 'ac-no.', 'enrollid', 'enroll id', 'pin', 'cardno']
            time_aliases = ['time', 'timestamp', 'punchtime', 'punch time', 'datetime', 'date time', 'date/time', 'logtime', 'log time', 'punchedat', 'punched at', 'checktime', 'check time', 'eventtime', 'event time', 'attendanceevents', 'punchdate']
            date_aliases = ['date', 'punchdate', 'punch date', 'logdate', 'log date', 'attdate', 'attendance date']
            name_aliases = ['name', 'employeename', 'employee_name', 'employee name', 'fullname', 'full name', 'empname', 'workername']
            direction_aliases = ['direction', 'type', 'status', 'event', 'inout', 'in_out', 'mode']

            all_cols_seen = []

            for sheet_name, df in tables:
                cols = list(df.columns)
                all_cols_seen.extend([str(c) for c in cols])

                id_col = find_best_column(cols, id_aliases)
                time_col = find_best_column(cols, time_aliases)
                date_col = find_best_column(cols, date_aliases)
                name_col = find_best_column(cols, name_aliases)
                dir_col = find_best_column(cols, direction_aliases)

                # Need at least an ID column and a time/date column
                if not id_col or (not time_col and not date_col):
                    continue

                for _, row in df.iterrows():
                    emp_id = clean_emp_id(row.get(id_col))
                    if not emp_id:
                        continue

                    p_dt = parse_punch_datetime(row, time_col=time_col, date_col=date_col)
                    if not p_dt or not isinstance(p_dt, datetime):
                        continue

                    # Direction inference
                    direction = "AUTO"
                    if dir_col and not pd.isna(row.get(dir_col)):
                        raw_dir = str(row.get(dir_col)).strip().upper()
                        if raw_dir in ("IN", "0", "CHECK-IN", "CHECKIN", "1"):
                            direction = "IN" if raw_dir in ("IN", "0", "CHECK-IN", "CHECKIN") else "OUT"
                        elif raw_dir in ("OUT", "CHECK-OUT", "CHECKOUT"):
                            direction = "OUT"

                    # Optional employee name in biometric log
                    emp_name = str(row.get(name_col)).strip() if (name_col and not pd.isna(row.get(name_col))) else None
                    if emp_name and emp_name.lower() in ('nan', 'none', ''):
                        emp_name = None

                    records.append({
                        "employee_id": emp_id,
                        "employee_name": emp_name,
                        "raw_timestamp": p_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "punched_at": p_dt,
                        "source_direction": direction
                    })

            if not records:
                cols_msg = ', '.join(set(all_cols_seen)) if all_cols_seen else "None"
                raise HTTPException(
                    status_code=400,
                    detail=f"No valid punch records could be parsed. Identified columns: [{cols_msg}]. Please ensure file contains an ID column (e.g. 'User ID.', 'UserId', 'EmpID') and a Timestamp/Time column."
                )

        elif filename.endswith((".dat", ".txt")):
            decoded = content.decode('utf-8', errors='ignore')
            for line in decoded.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Support tab, comma, or space separation
                parts = line.split('\t') if '\t' in line else (line.split(',') if ',' in line else line.split())
                if len(parts) >= 2:
                    emp_id = clean_emp_id(parts[0])
                    if not emp_id:
                        continue

                    if len(parts) >= 3 and ":" in parts[2] and "-" in parts[1]:
                        ts_str = f"{parts[1]} {parts[2]}"
                    else:
                        ts_str = parts[1].strip()

                    try:
                        p_dt = pd.to_datetime(ts_str)
                        if hasattr(p_dt, 'to_pydatetime'):
                            p_dt = p_dt.to_pydatetime()
                    except Exception:
                        continue

                    # Strictly extract employee ID and datetime only, ignoring extra biometric codes (1 0 1 0)
                    records.append({
                        "employee_id": emp_id,
                        "employee_name": None,
                        "raw_timestamp": p_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "punched_at": p_dt,
                        "source_direction": "AUTO"
                    })
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Please upload .xlsx, .xls, .csv, or biometric machine .dat/.txt log."
            )

        if not records:
            raise HTTPException(status_code=400, detail="No valid punch records could be found in the file.")

        result = import_punch_records(db, records, source_id=filename)
        return {
            "status": "success",
            "message": f"Successfully parsed {result['total_records']} lines. Imported {result['new_punches']} new punches ({result['duplicates']} duplicates skipped). Processed {len(result['dates_processed'])} calendar dates.",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@router.get("/punches")
def get_punches(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    employee_id: Optional[str] = None,
    date_filter: Optional[str] = Query(None, alias="date"),
    direction: Optional[str] = None
):
    query = db.query(AttendancePunchEvent)
    if employee_id:
        query = query.filter(AttendancePunchEvent.employee_id.ilike(f"%{employee_id}%"))
    if date_filter:
        try:
            d = datetime.strptime(date_filter, "%Y-%m-%d").date()
            query = query.filter(
                AttendancePunchEvent.punched_at >= datetime.combine(d, time.min),
                AttendancePunchEvent.punched_at <= datetime.combine(d, time.max)
            )
        except ValueError:
            pass
    if direction and direction != "All":
        query = query.filter(AttendancePunchEvent.source_direction == direction)

    total = query.count()
    punches = query.order_by(desc(AttendancePunchEvent.punched_at)).offset((page - 1) * size).limit(size).all()

    emp_ids = [p.employee_id for p in punches if p.employee_id]
    emps = {e.id: e for e in db.query(Employee).filter(Employee.id.in_(emp_ids)).all()}

    items = []
    for p in punches:
        emp = emps.get(p.employee_id)
        items.append({
            "id": p.id,
            "employee_id": p.employee_id,
            "employee_name": emp.name if emp else f"Emp #{p.employee_id}",
            "department": emp.department if emp else "—",
            "raw_timestamp": p.raw_timestamp,
            "punched_at": p.punched_at.isoformat(),
            "time_str": p.punched_at.strftime("%I:%M:%S %p"),
            "date_str": p.punched_at.strftime("%Y-%m-%d"),
            "source_direction": p.source_direction,
            "source_id": p.source_id,
            "is_duplicate": p.is_duplicate
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size
    }


@router.get("/daily")
def get_daily_attendance(
    db: Session = Depends(get_db),
    date_filter: Optional[str] = Query(None, alias="date"),
    department: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    shift_filter: Optional[str] = Query(None, alias="shift"),
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200)
):
    # Default to latest date or today
    if not date_filter:
        latest = db.query(DailyAttendance.attendance_date).order_by(DailyAttendance.attendance_date.desc()).first()
        target_date = latest[0].date() if (latest and latest[0]) else date.today()
    else:
        try:
            target_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
        except ValueError:
            target_date = date.today()

    target_dt = datetime.combine(target_date, time.min)

    query = db.query(DailyAttendance).join(Employee).filter(
        DailyAttendance.attendance_date == target_dt
    )

    if department and department != "All":
        query = query.filter(Employee.department == department)
    if status_filter and status_filter != "All":
        if status_filter == "Missing Punch":
            query = query.filter(DailyAttendance.missing_punch_flag == True)
        elif status_filter == "Late":
            query = query.filter(DailyAttendance.late_minutes > 0)
        else:
            query = query.filter(DailyAttendance.attendance_status == status_filter)
    if shift_filter and shift_filter != "All":
        if shift_filter == "UNASSIGNED":
            query = query.filter(or_(DailyAttendance.shift_id == None, DailyAttendance.attendance_status == "UNASSIGNED"))
        elif shift_filter == "OFF":
            query = query.filter(DailyAttendance.shift_code == "OFF")
        else:
            query = query.filter(DailyAttendance.shift_code == shift_filter)
    if search:
        query = query.filter(or_(
            Employee.id.ilike(f"%{search}%"),
            Employee.name.ilike(f"%{search}%")
        ))

    total = query.count()
    records = query.order_by(Employee.name.asc()).offset((page - 1) * size).limit(size).all()

    items = []
    for r in records:
        emp = r.employee
        shift = r.shift
        shift_timing = f"{shift.start_time} - {shift.end_time}" if shift else ("Day Off" if r.shift_code == "OFF" else "—")
        shift_display = f"{r.shift_code} - {r.shift_name}" if (r.shift_code and r.shift_name) else (r.shift_name or ("Shift Not Assigned" if r.attendance_status == "UNASSIGNED" else "—"))
        
        items.append({
            "id": r.id,
            "employee_id": r.employee_id,
            "employee_name": emp.name if emp else r.employee_id,
            "department": emp.department if emp else "—",
            "designation": emp.designation if emp else "—",
            "attendance_date": r.attendance_date.strftime("%Y-%m-%d"),
            "shift_id": r.shift_id,
            "shift_code": r.shift_code,
            "shift_name": r.shift_name,
            "shift_display": shift_display,
            "shift_timing": shift_timing,
            "shift_color": shift.color if shift else ("slate" if r.shift_code == "OFF" else "rose"),
            "first_half_status": r.first_half_status or ("Present" if r.attendance_status == "P" else ("Absent" if r.attendance_status == "A" else "—")),
            "second_half_status": r.second_half_status or ("Present" if r.attendance_status == "P" else ("Absent" if r.attendance_status == "A" else "—")),
            "first_valid_in_at": r.first_valid_in_at.strftime("%I:%M:%S %p") if r.first_valid_in_at else "—",
            "last_valid_out_at": r.last_valid_out_at.strftime("%I:%M:%S %p") if r.last_valid_out_at else "—",
            "first_valid_in_raw": r.first_valid_in_at.strftime("%Y-%m-%d %H:%M:%S") if r.first_valid_in_at else None,
            "last_valid_out_raw": r.last_valid_out_at.strftime("%Y-%m-%d %H:%M:%S") if r.last_valid_out_at else None,
            "punch_count": r.punch_count,
            "credited_work_minutes": r.credited_work_minutes,
            "work_hours": round(r.credited_work_minutes / 60.0, 1),
            "attendance_status": r.attendance_status,
            "late_minutes": r.late_minutes,
            "early_departure_minutes": r.early_departure_minutes,
            "missing_punch_flag": r.missing_punch_flag,
            "decision_method": r.decision_method,
            "remarks": r.remarks
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "target_date": target_date.strftime("%Y-%m-%d")
    }


@router.get("/daily/summary")
def get_daily_summary(
    date_filter: Optional[str] = Query(None, alias="date"),
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if not date_filter:
        latest = db.query(DailyAttendance.attendance_date).order_by(DailyAttendance.attendance_date.desc()).first()
        target_date = latest[0].date() if (latest and latest[0]) else date.today()
    else:
        try:
            target_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
        except ValueError:
            target_date = date.today()

    target_dt = datetime.combine(target_date, time.min)

    query = db.query(DailyAttendance).join(Employee).filter(
        DailyAttendance.attendance_date == target_dt
    )
    if department and department != "All":
        query = query.filter(Employee.department == department)

    records = query.all()

    total = len(records)
    present = sum(1 for r in records if r.attendance_status == "P")
    half_day = sum(1 for r in records if r.attendance_status == "HD")
    absent = sum(1 for r in records if r.attendance_status == "A")
    weekly_off = sum(1 for r in records if r.attendance_status == "WO")
    late = sum(1 for r in records if r.late_minutes > 0)
    missing = sum(1 for r in records if r.missing_punch_flag)
    unassigned = sum(1 for r in records if r.attendance_status == "UNASSIGNED" or not r.shift_code)

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "total": total,
        "present": present,
        "half_day": half_day,
        "absent": absent,
        "weekly_off": weekly_off,
        "late": late,
        "missing_punch": missing,
        "unassigned": unassigned
    }



@router.put("/daily/{id}")
def update_daily_attendance(
    id: int,
    payload: DailyAttendanceUpdate,
    db: Session = Depends(get_db)
):
    record = db.query(DailyAttendance).filter(DailyAttendance.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Daily attendance record not found")

    if payload.attendance_status is not None:
        record.attendance_status = payload.attendance_status

    if payload.first_valid_in_at is not None:
        try:
            val = payload.first_valid_in_at.strip()
            if ":" in val and len(val) <= 8 and " " not in val and "-" not in val:
                parts = [int(p) for p in val.split(":")]
                h = parts[0]
                m = parts[1] if len(parts) > 1 else 0
                s = parts[2] if len(parts) > 2 else 0
                record.first_valid_in_at = datetime.combine(
                    record.attendance_date.date(),
                    time(h, m, s)
                )
            else:
                record.first_valid_in_at = pd.to_datetime(val).to_pydatetime()
        except Exception:
            pass

    if payload.last_valid_out_at is not None:
        try:
            val = payload.last_valid_out_at.strip()
            if ":" in val and len(val) <= 8 and " " not in val and "-" not in val:
                parts = [int(p) for p in val.split(":")]
                h = parts[0]
                m = parts[1] if len(parts) > 1 else 0
                s = parts[2] if len(parts) > 2 else 0
                record.last_valid_out_at = datetime.combine(
                    record.attendance_date.date(),
                    time(h, m, s)
                )
            else:
                record.last_valid_out_at = pd.to_datetime(val).to_pydatetime()
        except Exception:
            pass

    if record.first_valid_in_at and record.last_valid_out_at:
        diff_mins = max(0.0, (record.last_valid_out_at - record.first_valid_in_at).total_seconds() / 60.0)
        record.credited_work_minutes = round(diff_mins, 1)
        record.missing_punch_flag = False

    if payload.remarks is not None:
        record.remarks = payload.remarks

    record.decision_method = "MANUAL"
    db.commit()
    db.refresh(record)

    return {"message": "Attendance record successfully updated", "id": record.id}


@router.post("/daily/manual-punch")
def create_manual_punch(
    payload: ManualPunchCreate,
    db: Session = Depends(get_db)
):
    emp = db.query(Employee).filter(Employee.id == payload.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee '{payload.employee_id}' not found")

    try:
        p_dt = pd.to_datetime(payload.timestamp).to_pydatetime()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS")

    punch = AttendancePunchEvent(
        employee_id=emp.id,
        raw_timestamp=payload.timestamp,
        punched_at=p_dt,
        source_direction=payload.direction or "AUTO",
        source_id="MANUAL_HR_PORTAL"
    )
    db.add(punch)
    db.commit()

    # Recalculate that date
    process_punches_for_date(db, p_dt.date())

    return {"message": "Punch recorded and attendance recalculated successfully."}


@router.post("/daily/recalculate")
def recalculate_attendance(
    payload: RecalculateRequest,
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    dates_to_recalc = []

    if payload.date:
        try:
            d = datetime.strptime(payload.date, "%Y-%m-%d").date()
            dates_to_recalc.append(d)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format (expected YYYY-MM-DD)")
    elif payload.start_date and payload.end_date:
        try:
            d1 = datetime.strptime(payload.start_date, "%Y-%m-%d").date()
            d2 = datetime.strptime(payload.end_date, "%Y-%m-%d").date()
            cur = d1
            while cur <= d2:
                dates_to_recalc.append(cur)
                cur += pd.Timedelta(days=1)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid date range: {e}")
    else:
        # Recalculate all dates found in punches
        dates = db.query(AttendancePunchEvent.punched_at).all()
        unique = {p[0].date() for p in dates if p[0]}
        dates_to_recalc = sorted(unique)

    total_processed = 0
    for d in dates_to_recalc:
        total_processed += process_punches_for_date(db, d, settings)

    return {
        "message": f"Successfully recalculated attendance for {len(dates_to_recalc)} dates ({total_processed} employee records updated).",
        "dates_processed": [d.strftime("%Y-%m-%d") for d in dates_to_recalc]
    }
