from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database import engine, SessionLocal
from app.models.base import Base
from app.models.shift import Shift, EmployeeShiftAssignment
from app.models.attendance import DailyAttendance

DEFAULT_INITIAL_SHIFTS = [
    {
        "code": "S1",
        "name": "Morning Shift",
        "start_time": "06:00",
        "end_time": "14:00",
        "break_start_time": "13:00",
        "break_end_time": "13:30",
        "first_half_start_cutoff": "05:45:00",
        "first_half_end_start": "06:00:00",
        "first_half_end_end": "11:30:00",
        "second_half_start_start": "12:30:00",
        "second_half_start_end": "14:00:00",
        "second_half_end_cutoff": "14:00:00",
        "is_overnight": False,
        "is_active": True,
        "color": "emerald"
    },
    {
        "code": "S2",
        "name": "General Shift",
        "start_time": "09:00",
        "end_time": "17:00",
        "break_start_time": "13:00",
        "break_end_time": "13:30",
        "first_half_start_cutoff": "08:45:00",
        "first_half_end_start": "09:00:00",
        "first_half_end_end": "13:00:00",
        "second_half_start_start": "13:30:00",
        "second_half_start_end": "15:00:00",
        "second_half_end_cutoff": "17:00:00",
        "is_overnight": False,
        "is_active": True,
        "color": "blue"
    },
    {
        "code": "S3",
        "name": "Evening Shift",
        "start_time": "14:00",
        "end_time": "22:00",
        "break_start_time": "18:00",
        "break_end_time": "18:30",
        "first_half_start_cutoff": "13:45:00",
        "first_half_end_start": "14:00:00",
        "first_half_end_end": "18:00:00",
        "second_half_start_start": "18:30:00",
        "second_half_start_end": "20:00:00",
        "second_half_end_cutoff": "22:00:00",
        "is_overnight": False,
        "is_active": True,
        "color": "amber"
    },
    {
        "code": "S4",
        "name": "Night Shift",
        "start_time": "22:00",
        "end_time": "06:00",
        "break_start_time": "02:00",
        "break_end_time": "02:30",
        "first_half_start_cutoff": "21:45:00",
        "first_half_end_start": "22:00:00",
        "first_half_end_end": "02:00:00",
        "second_half_start_start": "02:30:00",
        "second_half_start_end": "04:00:00",
        "second_half_end_cutoff": "06:00:00",
        "is_overnight": True,
        "is_active": True,
        "color": "purple"
    }
]

def ensure_tables_and_columns():
    """Create new tables if missing and add new columns to existing SQLite tables."""
    Base.metadata.create_all(bind=engine)
    
    with engine.connect() as conn:
        # Check columns of daily_attendance
        res = conn.execute(text("PRAGMA table_info(daily_attendance)")).fetchall()
        col_names = {r[1] for r in res}
        
        columns_to_add = [
            ("shift_id", "INTEGER"),
            ("shift_code", "VARCHAR(20)"),
            ("shift_name", "VARCHAR(100)"),
            ("first_half_status", "VARCHAR(20)"),
            ("second_half_status", "VARCHAR(20)"),
        ]
        
        for col, col_type in columns_to_add:
            if col not in col_names:
                conn.execute(text(f"ALTER TABLE daily_attendance ADD COLUMN {col} {col_type}"))
        conn.commit()

def seed_default_shifts_if_needed():
    """Ensure standard initial shifts (S1, S2, S3, S4) exist."""
    db: Session = SessionLocal()
    try:
        count = db.query(Shift).count()
        if count == 0:
            for s_data in DEFAULT_INITIAL_SHIFTS:
                shift = Shift(**s_data)
                db.add(shift)
            db.commit()
            print("Successfully initialized default shifts: S1, S2, S3, S4")
    finally:
        db.close()

def init_all_shifts(seed_defaults: bool = False):
    ensure_tables_and_columns()
    if seed_defaults:
        seed_default_shifts_if_needed()

if __name__ == "__main__":
    init_all_shifts(seed_defaults=True)

