from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional, Set
from app.models.employee import Employee
from app.models.attendance import AttendancePunchEvent, DailyAttendance
from app.models.settings import Setting
from app.models.shift import Shift, EmployeeShiftAssignment
from app.models.leave import Leave
from app.schemas.settings import SystemSettings


DEFAULT_SETTINGS = {
    # Four Configurable Punch Windows
    "first_half_start_cutoff": "08:14:59",      # Timestamp through 08:14:59 (15-min arrival margin of error)
    "first_half_end_start": "11:59:59",         # Timestamp from 11:59:59 through 12:30:00, inclusive
    "first_half_end_end": "12:30:00",
    "second_half_start_start": "12:30:01",       # Timestamp from 12:30:01 through 13:00:00, inclusive
    "second_half_start_end": "13:00:00",
    "second_half_end_cutoff": "17:00:00",       # Timestamp strictly after 17:00:00

    # General metadata
    "shift_start_time": "08:00:00",
    "shift_end_time": "17:00:00",
    "grace_period_mins": "15",
    "half_day_min_hours": "4.0",
    "full_day_min_hours": "8.0",
    "weekend_days": "Saturday,Sunday",
    "company_name": "Acme Global Solutions"
}

def get_settings(db: Session) -> Dict[str, str]:
    db_settings = db.query(Setting).all()
    res = dict(DEFAULT_SETTINGS)
    for s in db_settings:
        res[s.key] = s.value
    return res

def save_settings(db: Session, new_settings: Dict[str, Any]) -> Dict[str, str]:
    for k, v in new_settings.items():
        if k in DEFAULT_SETTINGS:
            s = db.query(Setting).filter(Setting.key == k).first()
            if not s:
                s = Setting(key=k, value=str(v))
                db.add(s)
            else:
                s.value = str(v)
    db.commit()
    return get_settings(db)

def parse_time_with_seconds(time_str: str, default: time) -> time:
    if not time_str:
        return default
    try:
        parts = [int(p) for p in str(time_str).strip().split(":")]
        if len(parts) == 1:
            return time(parts[0], 0, 0)
        elif len(parts) == 2:
            return time(parts[0], parts[1], 0)
        else:
            return time(parts[0], parts[1], parts[2])
    except Exception:
        return default

def check_first_half_start_window(t: time, cutoff: time) -> bool:
    """1. FIRST_HALF_START: timestamp through cutoff, inclusive of 08:14:59 margin of error."""
    return t <= cutoff

def check_first_half_end_window(t: time, start: time, end: time) -> bool:
    """2. FIRST_HALF_END: timestamp from start through end, inclusive (11:59:59 through 12:30:00)."""
    return start <= t <= end

def check_second_half_start_window(t: time, start: time, end: time) -> bool:
    """3. SECOND_HALF_START: timestamp from start through end, inclusive (12:30:01 through 13:00:00)."""
    return start <= t <= end

def check_second_half_end_window(t: time, cutoff: time) -> bool:
    """4. SECOND_HALF_END: timestamp strictly after cutoff (strictly after 17:00:00)."""
    return t > cutoff

def evaluate_daily_attendance_rules(
    emp_punches: List[AttendancePunchEvent],
    settings: Dict[str, str],
    is_weekend: bool = False
) -> Dict[str, Any]:
    fh_start_cutoff = parse_time_with_seconds(settings.get("first_half_start_cutoff", "08:14:59"), time(8, 14, 59))
    fh_end_start = parse_time_with_seconds(settings.get("first_half_end_start", "11:59:59"), time(11, 59, 59))
    fh_end_end = parse_time_with_seconds(settings.get("first_half_end_end", "12:30:00"), time(12, 30, 0))
    sh_start_start = parse_time_with_seconds(settings.get("second_half_start_start", "12:30:01"), time(12, 30, 1))
    sh_start_end = parse_time_with_seconds(settings.get("second_half_start_end", "13:00:00"), time(13, 0, 0))
    sh_end_cutoff = parse_time_with_seconds(settings.get("second_half_end_cutoff", "17:00:00"), time(17, 0, 0))

    half_day_hrs = float(settings.get("half_day_min_hours", "4.0"))
    full_day_hrs = float(settings.get("full_day_min_hours", "8.0"))

    punch_count = len(emp_punches)
    if punch_count == 0:
        if is_weekend:
            return {
                "status": "WO",
                "first_in": None,
                "last_out": None,
                "work_minutes": 0.0,
                "late_minutes": 0,
                "early_departure_minutes": 0,
                "missing_punch_flag": False,
                "remarks": "Weekly Off",
                "first_half_present": False,
                "second_half_present": False,
                "slot_matches": {}
            }
        else:
            return {
                "status": "A",
                "first_in": None,
                "last_out": None,
                "work_minutes": 0.0,
                "late_minutes": 0,
                "early_departure_minutes": 0,
                "missing_punch_flag": False,
                "remarks": "Absent: No biometric punches recorded on scheduled workday",
                "first_half_present": False,
                "second_half_present": False,
                "slot_matches": {}
            }

    sorted_punches = sorted(emp_punches, key=lambda p: p.punched_at)
    first_in = sorted_punches[0].punched_at
    last_out = sorted_punches[-1].punched_at if punch_count > 1 else None

    # Enforce distinct successful biometric event records for each required slot
    used_indices = set()
    slot_matches = {
        "FIRST_HALF_START": None,
        "FIRST_HALF_END": None,
        "SECOND_HALF_START": None,
        "SECOND_HALF_END": None
    }

    # Slot 1: FIRST_HALF_START (strictly before 08:00:00)
    for idx, p in enumerate(sorted_punches):
        if idx not in used_indices and check_first_half_start_window(p.punched_at.time(), fh_start_cutoff):
            used_indices.add(idx)
            slot_matches["FIRST_HALF_START"] = p
            break

    # Slot 2: FIRST_HALF_END (11:59:59 through 12:30:00, inclusive)
    for idx, p in enumerate(sorted_punches):
        if idx not in used_indices and check_first_half_end_window(p.punched_at.time(), fh_end_start, fh_end_end):
            used_indices.add(idx)
            slot_matches["FIRST_HALF_END"] = p
            break

    # Slot 3: SECOND_HALF_START (12:30:01 through 13:00:00, inclusive)
    for idx, p in enumerate(sorted_punches):
        if idx not in used_indices and check_second_half_start_window(p.punched_at.time(), sh_start_start, sh_start_end):
            used_indices.add(idx)
            slot_matches["SECOND_HALF_START"] = p
            break

    # Slot 4: SECOND_HALF_END (strictly after 17:00:00)
    for idx, p in enumerate(sorted_punches):
        if idx not in used_indices and check_second_half_end_window(p.punched_at.time(), sh_end_cutoff):
            used_indices.add(idx)
            slot_matches["SECOND_HALF_END"] = p
            break

    # Both first-half slots satisfied = First Half Present
    first_half_present = (slot_matches["FIRST_HALF_START"] is not None) and (slot_matches["FIRST_HALF_END"] is not None)
    # Both second-half slots satisfied = Second Half Present
    second_half_present = (slot_matches["SECOND_HALF_START"] is not None) and (slot_matches["SECOND_HALF_END"] is not None)

    # Actual elapsed work minutes
    actual_work_mins = 0.0
    if first_in and last_out:
        actual_work_mins = max(0.0, round((last_out - first_in).total_seconds() / 60.0, 1))

    # Late arrival calculation if first in is after first-half cutoff
    late_minutes = 0
    if first_in.time() > fh_start_cutoff:
        diff_s = (first_in.hour * 3600 + first_in.minute * 60 + first_in.second) - (fh_start_cutoff.hour * 3600 + fh_start_cutoff.minute * 60 + fh_start_cutoff.second)
        late_minutes = max(0, diff_s // 60)

    # Attendance classification:
    # - Both halves satisfied = Full Day Present
    # - Only one half satisfied = Half Day
    # - Neither half satisfied = Absent, only after scheduled workday and attendance data are validated and finalized.
    if first_half_present and second_half_present:
        status = "P" # Full Day Present
        credited_work_minutes = max(full_day_hrs * 60.0, actual_work_mins)
        missing_punch_flag = False
        p1 = slot_matches["FIRST_HALF_START"].punched_at.strftime("%H:%M:%S")
        p2 = slot_matches["FIRST_HALF_END"].punched_at.strftime("%H:%M:%S")
        p3 = slot_matches["SECOND_HALF_START"].punched_at.strftime("%H:%M:%S")
        p4 = slot_matches["SECOND_HALF_END"].punched_at.strftime("%H:%M:%S")
        remarks = f"Full Day Present (1st Half: {p1} & {p2}; 2nd Half: {p3} & {p4})"

    elif first_half_present and not second_half_present:
        status = "HD" # Half Day (First Half Present)
        credited_work_minutes = half_day_hrs * 60.0
        missing_punch_flag = True
        p1 = slot_matches["FIRST_HALF_START"].punched_at.strftime("%H:%M:%S")
        p2 = slot_matches["FIRST_HALF_END"].punched_at.strftime("%H:%M:%S")
        missing_slots = []
        if not slot_matches["SECOND_HALF_START"]:
            missing_slots.append("2nd Start [12:30:01-13:00:00]")
        if not slot_matches["SECOND_HALF_END"]:
            missing_slots.append("2nd End [>17:00:00]")
        remarks = f"Half Day: First Half Present ({p1} & {p2}); Second Half missing ({', '.join(missing_slots)})"

    elif not first_half_present and second_half_present:
        status = "HD" # Half Day (Second Half Present)
        credited_work_minutes = half_day_hrs * 60.0
        missing_punch_flag = True
        p3 = slot_matches["SECOND_HALF_START"].punched_at.strftime("%H:%M:%S")
        p4 = slot_matches["SECOND_HALF_END"].punched_at.strftime("%H:%M:%S")
        missing_slots = []
        if not slot_matches["FIRST_HALF_START"]:
            missing_slots.append("1st Start [<=08:14:59]")
        if not slot_matches["FIRST_HALF_END"]:
            missing_slots.append("1st End [11:59:59-12:30:00]")
        remarks = f"Half Day: Second Half Present ({p3} & {p4}); First Half missing ({', '.join(missing_slots)})"

    else:
        # Neither half satisfied
        status = "A" # Absent
        credited_work_minutes = 0.0
        missing_punch_flag = True
        recorded = [p.punched_at.strftime("%H:%M:%S") for p in sorted_punches]
        times_preview = ", ".join(recorded[:4]) + ("..." if len(recorded) > 4 else "")
        remarks = f"Absent: Neither half satisfied ({punch_count} punches: [{times_preview}]; required 1st Half [<=08:14:59, 11:59:59-12:30:00] & 2nd Half [12:30:01-13:00:00, >17:00:00])"

    return {
        "status": status,
        "first_in": first_in,
        "last_out": last_out,
        "work_minutes": credited_work_minutes,
        "late_minutes": late_minutes,
        "early_departure_minutes": 0,
        "missing_punch_flag": missing_punch_flag,
        "remarks": remarks,
        "first_half_present": first_half_present,
        "second_half_present": second_half_present,
        "slot_matches": {
            k: v.punched_at.strftime("%Y-%m-%d %H:%M:%S") if v else None
            for k, v in slot_matches.items()
        }
    }

def build_shift_datetimes(shift: Shift, target_date: date) -> Dict[str, datetime]:
    """Calculate exact datetime windows for daytime or overnight shifts."""
    is_overnight = shift.is_overnight
    
    start_t = parse_time_with_seconds(shift.start_time, time(9, 0, 0))
    end_t = parse_time_with_seconds(shift.end_time, time(17, 0, 0))
    
    shift_start_dt = datetime.combine(target_date, start_t)
    shift_end_dt = datetime.combine(target_date + timedelta(days=1) if is_overnight else target_date, end_t)
    
    # 1. First Half Start Cutoff (through check-in)
    fh_sc_t = parse_time_with_seconds(shift.first_half_start_cutoff, start_t)
    fh_sc_dt = datetime.combine(target_date, fh_sc_t)
    
    # 2. First Half End (Start through End, inclusive)
    fh_es_t = parse_time_with_seconds(shift.first_half_end_start, time(12, 0, 0))
    fh_ee_t = parse_time_with_seconds(shift.first_half_end_end, time(12, 30, 0))
    day_offset_fh_es = 1 if (is_overnight and fh_es_t < start_t) else 0
    day_offset_fh_ee = 1 if (is_overnight and fh_ee_t < start_t) else 0
    fh_es_dt = datetime.combine(target_date + timedelta(days=day_offset_fh_es), fh_es_t)
    fh_ee_dt = datetime.combine(target_date + timedelta(days=day_offset_fh_ee), fh_ee_t)
    
    # 3. Second Half Start (Start through End, inclusive)
    sh_ss_t = parse_time_with_seconds(shift.second_half_start_start, time(12, 30, 1))
    sh_se_t = parse_time_with_seconds(shift.second_half_start_end, time(13, 0, 0))
    day_offset_sh_ss = 1 if (is_overnight and sh_ss_t < start_t) else 0
    day_offset_sh_se = 1 if (is_overnight and sh_se_t < start_t) else 0
    sh_ss_dt = datetime.combine(target_date + timedelta(days=day_offset_sh_ss), sh_ss_t)
    sh_se_dt = datetime.combine(target_date + timedelta(days=day_offset_sh_se), sh_se_t)
    
    # 4. Second Half End Cutoff (strictly after checkout)
    sh_ec_t = parse_time_with_seconds(shift.second_half_end_cutoff, end_t)
    day_offset_sh_ec = 1 if (is_overnight and sh_ec_t < start_t) else 0
    sh_ec_dt = datetime.combine(target_date + timedelta(days=day_offset_sh_ec), sh_ec_t)
    
    return {
        "shift_start_dt": shift_start_dt,
        "shift_end_dt": shift_end_dt,
        "fh_start_cutoff_dt": fh_sc_dt,
        "fh_end_start_dt": fh_es_dt,
        "fh_end_end_dt": fh_ee_dt,
        "sh_start_start_dt": sh_ss_dt,
        "sh_start_end_dt": sh_se_dt,
        "sh_end_cutoff_dt": sh_ec_dt,
    }

def evaluate_shift_attendance_rules(
    emp_punches: List[AttendancePunchEvent],
    shift: Shift,
    target_date: date
) -> Dict[str, Any]:
    """Evaluate punches against the specific assigned Shift configuration and punch windows."""
    dt_windows = build_shift_datetimes(shift, target_date)
    
    fh_sc_dt = dt_windows["fh_start_cutoff_dt"]
    fh_es_dt = dt_windows["fh_end_start_dt"]
    fh_ee_dt = dt_windows["fh_end_end_dt"]
    sh_ss_dt = dt_windows["sh_start_start_dt"]
    sh_se_dt = dt_windows["sh_start_end_dt"]
    sh_ec_dt = dt_windows["sh_end_cutoff_dt"]
    
    shift_start_dt = dt_windows["shift_start_dt"]
    shift_end_dt = dt_windows["shift_end_dt"]
    
    half_day_hrs = float(shift.half_day_min_hours or 4.0)
    full_day_hrs = float(shift.full_day_min_hours or 8.0)
    
    punch_count = len(emp_punches)
    if punch_count == 0:
        return {
            "status": "A",
            "first_in": None,
            "last_out": None,
            "work_minutes": 0.0,
            "late_minutes": 0,
            "early_departure_minutes": 0,
            "missing_punch_flag": False,
            "first_half_status": "Absent",
            "second_half_status": "Absent",
            "remarks": f"Absent: No biometric punches recorded on scheduled workday ({shift.code} - {shift.name})"
        }
        
    sorted_punches = sorted(emp_punches, key=lambda p: p.punched_at)
    first_in = sorted_punches[0].punched_at
    last_out = sorted_punches[-1].punched_at if punch_count > 1 else None
    
    used_indices = set()
    slot_matches = {
        "FIRST_HALF_START": None,
        "FIRST_HALF_END": None,
        "SECOND_HALF_START": None,
        "SECOND_HALF_END": None
    }
    
    # Slot 1: FIRST_HALF_START (punched_at <= fh_sc_dt)
    for idx, p in enumerate(sorted_punches):
        if idx not in used_indices and p.punched_at <= fh_sc_dt:
            used_indices.add(idx)
            slot_matches["FIRST_HALF_START"] = p
            break
            
    # Slot 2: FIRST_HALF_END (fh_es_dt <= punched_at <= fh_ee_dt)
    for idx, p in enumerate(sorted_punches):
        if idx not in used_indices and fh_es_dt <= p.punched_at <= fh_ee_dt:
            used_indices.add(idx)
            slot_matches["FIRST_HALF_END"] = p
            break
            
    # Slot 3: SECOND_HALF_START (sh_ss_dt <= punched_at <= sh_se_dt)
    for idx, p in enumerate(sorted_punches):
        if idx not in used_indices and sh_ss_dt <= p.punched_at <= sh_se_dt:
            used_indices.add(idx)
            slot_matches["SECOND_HALF_START"] = p
            break
            
    # Slot 4: SECOND_HALF_END (punched_at > sh_ec_dt)
    for idx, p in enumerate(sorted_punches):
        if idx not in used_indices and p.punched_at > sh_ec_dt:
            used_indices.add(idx)
            slot_matches["SECOND_HALF_END"] = p
            break
            
    first_half_present = (slot_matches["FIRST_HALF_START"] is not None) and (slot_matches["FIRST_HALF_END"] is not None)
    second_half_present = (slot_matches["SECOND_HALF_START"] is not None) and (slot_matches["SECOND_HALF_END"] is not None)
    
    first_half_status = "Present" if first_half_present else ("Missing" if punch_count > 0 else "Absent")
    second_half_status = "Present" if second_half_present else ("Missing" if punch_count > 0 else "Absent")
    
    actual_work_mins = 0.0
    if first_in and last_out:
        actual_work_mins = max(0.0, round((last_out - first_in).total_seconds() / 60.0, 1))
        
    # Late arrival
    late_minutes = 0
    grace_cutoff = shift_start_dt + timedelta(minutes=shift.grace_period_mins)
    if first_in > grace_cutoff:
        late_minutes = max(0, int((first_in - shift_start_dt).total_seconds() // 60))
        
    # Early departure
    early_departure_minutes = 0
    if last_out and last_out < (shift_end_dt - timedelta(minutes=shift.grace_period_mins)):
        early_departure_minutes = max(0, int((shift_end_dt - last_out).total_seconds() // 60))
        
    if first_half_present and second_half_present:
        status = "P"
        credited_work_minutes = max(full_day_hrs * 60.0, actual_work_mins)
        missing_punch_flag = False
        p1 = slot_matches["FIRST_HALF_START"].punched_at.strftime("%H:%M:%S")
        p2 = slot_matches["FIRST_HALF_END"].punched_at.strftime("%H:%M:%S")
        p3 = slot_matches["SECOND_HALF_START"].punched_at.strftime("%H:%M:%S")
        p4 = slot_matches["SECOND_HALF_END"].punched_at.strftime("%H:%M:%S")
        remarks = f"Full Day Present (1st Half: {p1} & {p2}; 2nd Half: {p3} & {p4})"
    elif first_half_present and not second_half_present:
        status = "HD"
        credited_work_minutes = half_day_hrs * 60.0
        missing_punch_flag = True
        remarks = f"Half Day: First Half Present; Second Half punches missing/incomplete ({shift.code})"
    elif not first_half_present and second_half_present:
        status = "HD"
        credited_work_minutes = half_day_hrs * 60.0
        missing_punch_flag = True
        remarks = f"Half Day: Second Half Present; First Half punches missing/incomplete ({shift.code})"
    else:
        status = "A"
        credited_work_minutes = 0.0
        missing_punch_flag = True
        recorded = [p.punched_at.strftime("%H:%M:%S") for p in sorted_punches]
        times_preview = ", ".join(recorded[:4]) + ("..." if len(recorded) > 4 else "")
        remarks = f"Absent: Neither half satisfied ({punch_count} punches: [{times_preview}]; Shift: {shift.code} - {shift.name})"
        
    return {
        "status": status,
        "first_in": first_in,
        "last_out": last_out,
        "work_minutes": credited_work_minutes,
        "late_minutes": late_minutes,
        "early_departure_minutes": early_departure_minutes,
        "missing_punch_flag": missing_punch_flag,
        "first_half_status": first_half_status,
        "second_half_status": second_half_status,
        "remarks": remarks
    }

def evaluate_and_save_employee_daily_attendance(
    db: Session,
    employee_id: str,
    target_date: date,
    force_override: bool = False
) -> Optional[DailyAttendance]:
    """
    Resolve assigned shift for (employee_id, target_date), load punch events,
    evaluate attendance rules against shift windows, and persist DailyAttendance record.
    """
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        return None

    assignment = db.query(EmployeeShiftAssignment).filter(
        EmployeeShiftAssignment.employee_id == employee_id,
        EmployeeShiftAssignment.assignment_date == target_date
    ).first()

    attendance_date_dt = datetime.combine(target_date, time.min)

    daily = db.query(DailyAttendance).filter(
        DailyAttendance.employee_id == employee_id,
        DailyAttendance.attendance_date == attendance_date_dt
    ).first()

    if daily and daily.decision_method == "MANUAL" and not force_override:
        return daily

    # Check for approved Leave covering target_date
    approved_leave = db.query(Leave).filter(
        Leave.employee_id == employee_id,
        Leave.status == "APPROVED",
        Leave.start_date <= target_date,
        Leave.end_date >= target_date
    ).first()

    if approved_leave:
        if not daily:
            daily = DailyAttendance(
                employee_id=employee_id,
                attendance_date=attendance_date_dt
            )
            db.add(daily)

        daily.first_valid_in_at = None
        daily.last_valid_out_at = None
        daily.shift_id = assignment.shift_id if (assignment and assignment.shift_id) else None
        daily.shift_code = assignment.shift.code if (assignment and assignment.shift) else "LEAVE"
        daily.shift_name = f"Leave: {approved_leave.leave_type}"
        daily.first_half_status = "LEAVE"
        daily.second_half_status = "LEAVE"
        daily.punch_count = 0
        daily.credited_work_minutes = 480.0 if not approved_leave.is_half_day else 240.0
        daily.attendance_status = "LEAVE"
        daily.late_minutes = 0
        daily.early_departure_minutes = 0
        daily.missing_punch_flag = False
        daily.decision_method = "LEAVE"
        daily.remarks = f"Approved Leave ({approved_leave.leave_type})" + (f": {approved_leave.reason}" if approved_leave.reason else "")
        db.commit()
        return daily

    # Case 1: Assigned as OFF / Weekly Off
    if assignment and assignment.is_off:
        start_dt = datetime.combine(target_date, time.min)
        end_dt = datetime.combine(target_date, time.max)
        punches = db.query(AttendancePunchEvent).filter(
            AttendancePunchEvent.employee_id == employee_id,
            AttendancePunchEvent.punched_at >= start_dt,
            AttendancePunchEvent.punched_at <= end_dt
        ).order_by(AttendancePunchEvent.punched_at.asc()).all()

        first_in = punches[0].punched_at if punches else None
        last_out = punches[-1].punched_at if len(punches) > 1 else None
        work_mins = max(0.0, round((last_out - first_in).total_seconds() / 60.0, 1)) if (first_in and last_out) else 0.0

        if not daily:
            daily = DailyAttendance(
                employee_id=employee_id,
                attendance_date=attendance_date_dt
            )
            db.add(daily)

        daily.first_valid_in_at = first_in
        daily.last_valid_out_at = last_out
        daily.shift_id = None
        daily.shift_code = "OFF"
        daily.shift_name = "Day Off"
        daily.first_half_status = "WO"
        daily.second_half_status = "WO"
        daily.punch_count = len(punches)
        daily.credited_work_minutes = work_mins
        daily.attendance_status = "WO"
        daily.late_minutes = 0
        daily.early_departure_minutes = 0
        daily.missing_punch_flag = False
        daily.decision_method = "ENGINE"
        daily.remarks = "Scheduled Weekly Off" + (f" ({len(punches)} punches recorded)" if punches else "")
        db.commit()
        return daily

    # Case 2: Configured Shift is assigned
    if assignment and assignment.shift_id and assignment.shift:
        shift = assignment.shift
        if shift.is_overnight:
            start_dt = datetime.combine(target_date, time(18, 0, 0))
            end_dt = datetime.combine(target_date + timedelta(days=1), time(12, 0, 0))
        else:
            start_dt = datetime.combine(target_date, time.min)
            end_dt = datetime.combine(target_date, time.max)

        punches = db.query(AttendancePunchEvent).filter(
            AttendancePunchEvent.employee_id == employee_id,
            AttendancePunchEvent.punched_at >= start_dt,
            AttendancePunchEvent.punched_at <= end_dt
        ).order_by(AttendancePunchEvent.punched_at.asc()).all()

        eval_res = evaluate_shift_attendance_rules(punches, shift, target_date)

        if not daily:
            daily = DailyAttendance(
                employee_id=employee_id,
                attendance_date=attendance_date_dt
            )
            db.add(daily)

        daily.first_valid_in_at = eval_res["first_in"]
        daily.last_valid_out_at = eval_res["last_out"]
        daily.shift_id = shift.id
        daily.shift_code = shift.code
        daily.shift_name = shift.name
        daily.first_half_status = eval_res["first_half_status"]
        daily.second_half_status = eval_res["second_half_status"]
        daily.punch_count = len(punches)
        daily.credited_work_minutes = eval_res["work_minutes"]
        daily.attendance_status = eval_res["status"]
        daily.late_minutes = eval_res["late_minutes"]
        daily.early_departure_minutes = eval_res["early_departure_minutes"]
        daily.missing_punch_flag = eval_res["missing_punch_flag"]
        daily.decision_method = "ENGINE"
        daily.remarks = eval_res["remarks"]
        db.commit()
        return daily

    # Case 3: Missing shift assignment (No random assignment)
    start_dt = datetime.combine(target_date, time.min)
    end_dt = datetime.combine(target_date, time.max)
    punches = db.query(AttendancePunchEvent).filter(
        AttendancePunchEvent.employee_id == employee_id,
        AttendancePunchEvent.punched_at >= start_dt,
        AttendancePunchEvent.punched_at <= end_dt
    ).order_by(AttendancePunchEvent.punched_at.asc()).all()

    first_in = punches[0].punched_at if punches else None
    last_out = punches[-1].punched_at if len(punches) > 1 else None
    work_mins = max(0.0, round((last_out - first_in).total_seconds() / 60.0, 1)) if (first_in and last_out) else 0.0

    if not daily:
        daily = DailyAttendance(
            employee_id=employee_id,
            attendance_date=attendance_date_dt
        )
        db.add(daily)

    daily.first_valid_in_at = first_in
    daily.last_valid_out_at = last_out
    daily.shift_id = None
    daily.shift_code = None
    daily.shift_name = "Shift Not Assigned"
    daily.first_half_status = "Unassigned"
    daily.second_half_status = "Unassigned"
    daily.punch_count = len(punches)
    daily.credited_work_minutes = work_mins
    daily.attendance_status = "UNASSIGNED"
    daily.late_minutes = 0
    daily.early_departure_minutes = 0
    daily.missing_punch_flag = True
    daily.decision_method = "ENGINE"
    daily.remarks = "Shift Not Assigned for this date" + (f" ({len(punches)} punches recorded)" if punches else "")
    db.commit()
    return daily

def process_punches_for_date(db: Session, target_date: date, settings: Optional[Dict[str, str]] = None) -> int:
    """
    Process daily attendance for all active employees on target_date,
    evaluating each employee against their resolved shift assignment.
    """
    employees = db.query(Employee).filter(Employee.status == "Active").all()
    if not employees:
        return 0

    processed_count = 0
    for emp in employees:
        rec = evaluate_and_save_employee_daily_attendance(db, emp.id, target_date)
        if rec:
            processed_count += 1

    return processed_count



def import_punch_records(db: Session, records: List[Dict[str, Any]], source_id: str = "upload") -> Dict[str, Any]:
    """
    Deduplicate and insert punch records, then trigger daily attendance calculations.
    """
    if not records:
        return {
            "total_records": 0,
            "new_punches": 0,
            "duplicates": 0,
            "dates_processed": [],
            "employees_affected": 0
        }

    # Map employee names if present in records
    names_by_id = {}
    for r in records:
        eid = r.get("employee_id")
        ename = r.get("employee_name")
        if eid and ename and str(ename).strip() and not str(ename).startswith("Employee "):
            names_by_id[eid] = str(ename).strip()

    # Extract unique employee IDs and ensure they exist in DB
    raw_emp_ids = {r["employee_id"] for r in records if r.get("employee_id")}
    existing_emps_objs = db.query(Employee).filter(Employee.id.in_(raw_emp_ids)).all()
    existing_emps = {e.id for e in existing_emps_objs}

    # If existing employees have placeholder names, update them if real name is found
    for e in existing_emps_objs:
        if e.name.startswith("Employee ") and e.id in names_by_id:
            e.name = names_by_id[e.id]
    
    # Auto-create missing employees so attendance is not dropped
    missing_emps = raw_emp_ids - existing_emps
    for m_id in missing_emps:
        display_name = names_by_id.get(m_id, f"Employee {m_id}")
        new_emp = Employee(
            id=m_id,
            name=display_name,
            department="Operations",
            designation="Staff",
            status="Active"
        )
        db.add(new_emp)
    if missing_emps or names_by_id:
        db.commit()

    # Fetch existing punches for these employees
    # We will build a set of (employee_id, punched_at_str)
    min_date = None
    max_date = None
    for r in records:
        dt = r.get("punched_at")
        if isinstance(dt, datetime):
            if min_date is None or dt < min_date: min_date = dt
            if max_date is None or dt > max_date: max_date = dt

    existing_punches_set: Set[str] = set()
    if min_date and max_date:
        existing_punches = db.query(AttendancePunchEvent.employee_id, AttendancePunchEvent.punched_at).filter(
            AttendancePunchEvent.punched_at >= min_date - timedelta(days=1),
            AttendancePunchEvent.punched_at <= max_date + timedelta(days=1)
        ).all()
        for emp_id, p_at in existing_punches:
            existing_punches_set.add(f"{emp_id}_{p_at.strftime('%Y-%m-%d %H:%M:%S')}")

    new_punches = 0
    duplicate_count = 0
    unique_dates: Set[date] = set()
    affected_employees: Set[str] = set()

    for r in records:
        emp_id = r.get("employee_id")
        p_dt = r.get("punched_at")
        if not emp_id or not isinstance(p_dt, datetime):
            continue

        key = f"{emp_id}_{p_dt.strftime('%Y-%m-%d %H:%M:%S')}"
        if key in existing_punches_set:
            duplicate_count += 1
            continue

        existing_punches_set.add(key)
        new_punch = AttendancePunchEvent(
            employee_id=emp_id,
            raw_timestamp=r.get("raw_timestamp", p_dt.isoformat()),
            punched_at=p_dt,
            source_direction=r.get("source_direction", "AUTO"),
            source_id=source_id,
            is_duplicate=False
        )
        db.add(new_punch)
        new_punches += 1
        unique_dates.add(p_dt.date())
        affected_employees.add(emp_id)

    db.commit()

    # Now calculate daily attendance for all touched dates
    settings = get_settings(db)
    for d in sorted(unique_dates):
        process_punches_for_date(db, d, settings)

    return {
        "total_records": len(records),
        "new_punches": new_punches,
        "duplicates": duplicate_count,
        "dates_processed": [d.strftime("%Y-%m-%d") for d in sorted(unique_dates)],
        "employees_affected": len(affected_employees)
    }
