from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta, time
import random
from app.models.employee import Employee
from app.models.attendance import AttendancePunchEvent, DailyAttendance
from app.services.attendance_service import process_punches_for_date, get_settings

DEMO_EMPLOYEES = [
    {"id": "EMP101", "name": "Aarav Sharma", "department": "Engineering", "designation": "Lead Architect", "email": "aarav.sharma@company.com", "phone": "+91 98765 43210"},
    {"id": "EMP102", "name": "Priya Nair", "department": "Engineering", "designation": "Senior Full-Stack Dev", "email": "priya.nair@company.com", "phone": "+91 98765 43211"},
    {"id": "EMP103", "name": "Rohan Mehta", "department": "Engineering", "designation": "Backend Engineer", "email": "rohan.mehta@company.com", "phone": "+91 98765 43212"},
    {"id": "EMP104", "name": "Sneha Patel", "department": "Design", "designation": "Product Designer", "email": "sneha.patel@company.com", "phone": "+91 98765 43213"},
    {"id": "EMP105", "name": "Vikram Singh", "department": "Design", "designation": "UI/UX Specialist", "email": "vikram.singh@company.com", "phone": "+91 98765 43214"},
    {"id": "EMP106", "name": "Ananya Roy", "department": "Human Resources", "designation": "HR Manager", "email": "ananya.roy@company.com", "phone": "+91 98765 43215"},
    {"id": "EMP107", "name": "Kabir Das", "department": "Human Resources", "designation": "Talent Acquisition", "email": "kabir.das@company.com", "phone": "+91 98765 43216"},
    {"id": "EMP108", "name": "Neha Kulkarni", "department": "Finance", "designation": "Financial Controller", "email": "neha.k@company.com", "phone": "+91 98765 43217"},
    {"id": "EMP109", "name": "Arjun Verma", "department": "Finance", "designation": "Accountant", "email": "arjun.verma@company.com", "phone": "+91 98765 43218"},
    {"id": "EMP110", "name": "Devika Pillai", "department": "Operations", "designation": "Operations Lead", "email": "devika.p@company.com", "phone": "+91 98765 43219"},
    {"id": "EMP111", "name": "Tanmay Joshi", "department": "Operations", "designation": "Facility Coordinator", "email": "tanmay.j@company.com", "phone": "+91 98765 43220"},
    {"id": "EMP112", "name": "Isha Kapoor", "department": "Marketing", "designation": "Growth Specialist", "email": "isha.k@company.com", "phone": "+91 98765 43221"},
]

def seed_demo_data(db: Session, days: int = 30) -> dict:
    """
    Clears existing attendance data and seeds realistic employees and punch events.
    """
    # 1. Ensure demo employees exist
    created_emps = 0
    for e in DEMO_EMPLOYEES:
        emp = db.query(Employee).filter(Employee.id == e["id"]).first()
        if not emp:
            emp = Employee(
                id=e["id"],
                name=e["name"],
                department=e["department"],
                designation=e["designation"],
                email=e["email"],
                phone=e["phone"],
                status="Active"
            )
            db.add(emp)
            created_emps += 1
        else:
            emp.name = e["name"]
            emp.department = e["department"]
            emp.designation = e["designation"]
            emp.status = "Active"
    db.commit()

    active_emps = db.query(Employee).filter(Employee.status == "Active").all()
    today = date.today()
    settings = get_settings(db)
    weekend_days = [w.strip().lower() for w in settings.get("weekend_days", "Saturday,Sunday").split(",") if w.strip()]

    # Clear punches and daily attendance for clean slate
    db.query(DailyAttendance).delete()
    db.query(AttendancePunchEvent).delete()
    db.commit()

    total_punches = 0
    processed_dates = []

    # Loop past 30 days
    random.seed(42) # Consistent realistic sample data
    for i in range(days, -1, -1):
        cur_date = today - timedelta(days=i)
        processed_dates.append(cur_date)
        day_name = cur_date.strftime("%A").lower()
        is_weekend = day_name in weekend_days

        if is_weekend:
            # On weekends, 95% do not punch, 5% may punch overtime
            continue

        for emp in active_emps:
            roll = random.random()
            if roll < 0.05:
                # Absent - 0 punches
                continue
            elif roll < 0.10:
                # Missing punch - 1 punch only
                in_time = datetime.combine(cur_date, time(9, random.randint(0, 15), random.randint(0, 59)))
                p_in = AttendancePunchEvent(
                    employee_id=emp.id,
                    raw_timestamp=in_time.strftime("%Y-%m-%d %H:%M:%S"),
                    punched_at=in_time,
                    source_direction="IN",
                    source_id="DEMO_BIOMETRIC_DEV_01"
                )
                db.add(p_in)
                total_punches += 1
            elif roll < 0.18:
                # Half Day
                in_time = datetime.combine(cur_date, time(9, random.randint(0, 10), random.randint(0, 59)))
                out_time = datetime.combine(cur_date, time(13, random.randint(15, 30), random.randint(0, 59)))
                db.add(AttendancePunchEvent(
                    employee_id=emp.id,
                    raw_timestamp=in_time.strftime("%Y-%m-%d %H:%M:%S"),
                    punched_at=in_time,
                    source_direction="IN",
                    source_id="DEMO_BIOMETRIC_DEV_01"
                ))
                db.add(AttendancePunchEvent(
                    employee_id=emp.id,
                    raw_timestamp=out_time.strftime("%Y-%m-%d %H:%M:%S"),
                    punched_at=out_time,
                    source_direction="OUT",
                    source_id="DEMO_BIOMETRIC_DEV_01"
                ))
                total_punches += 2
            elif roll < 0.35:
                # Late arrival full day
                in_time = datetime.combine(cur_date, time(9, random.randint(20, 48), random.randint(0, 59)))
                out_time = datetime.combine(cur_date, time(18, random.randint(20, 55), random.randint(0, 59)))
                db.add(AttendancePunchEvent(
                    employee_id=emp.id,
                    raw_timestamp=in_time.strftime("%Y-%m-%d %H:%M:%S"),
                    punched_at=in_time,
                    source_direction="IN",
                    source_id="DEMO_BIOMETRIC_DEV_01"
                ))
                db.add(AttendancePunchEvent(
                    employee_id=emp.id,
                    raw_timestamp=out_time.strftime("%Y-%m-%d %H:%M:%S"),
                    punched_at=out_time,
                    source_direction="OUT",
                    source_id="DEMO_BIOMETRIC_DEV_01"
                ))
                total_punches += 2
            else:
                # On-time full day
                in_time = datetime.combine(cur_date, time(8, random.randint(45, 59), random.randint(0, 59)))
                out_time = datetime.combine(cur_date, time(18, random.randint(5, 35), random.randint(0, 59)))
                db.add(AttendancePunchEvent(
                    employee_id=emp.id,
                    raw_timestamp=in_time.strftime("%Y-%m-%d %H:%M:%S"),
                    punched_at=in_time,
                    source_direction="IN",
                    source_id="DEMO_BIOMETRIC_DEV_01"
                ))
                db.add(AttendancePunchEvent(
                    employee_id=emp.id,
                    raw_timestamp=out_time.strftime("%Y-%m-%d %H:%M:%S"),
                    punched_at=out_time,
                    source_direction="OUT",
                    source_id="DEMO_BIOMETRIC_DEV_01"
                ))
                total_punches += 2

    db.commit()

    # Now calculate daily attendance for all dates
    for d in processed_dates:
        process_punches_for_date(db, d, settings)

    return {
        "status": "success",
        "employees_count": len(active_emps),
        "days_seeded": len(processed_dates),
        "total_punches_created": total_punches,
        "message": f"Successfully initialized demo dataset: {len(active_emps)} employees, {total_punches} biometric punches across {len(processed_dates)} days."
    }
