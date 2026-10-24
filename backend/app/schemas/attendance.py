from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class PunchEventResponse(BaseModel):
    id: int
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    department: Optional[str] = None
    raw_timestamp: str
    punched_at: datetime
    source_direction: Optional[str] = None
    source_id: Optional[str] = None
    is_duplicate: bool

    class Config:
        from_attributes = True

class DailyAttendanceResponse(BaseModel):
    id: int
    employee_id: str
    employee_name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    attendance_date: datetime
    first_valid_in_at: Optional[datetime] = None
    last_valid_out_at: Optional[datetime] = None
    punch_count: int
    credited_work_minutes: float
    work_hours: float = 0.0
    attendance_status: str
    late_minutes: int
    early_departure_minutes: int
    missing_punch_flag: bool
    decision_method: str
    remarks: Optional[str] = None

    class Config:
        from_attributes = True

class DailyAttendanceUpdate(BaseModel):
    attendance_status: Optional[str] = None
    first_valid_in_at: Optional[str] = None # HH:MM or ISO
    last_valid_out_at: Optional[str] = None # HH:MM or ISO
    remarks: Optional[str] = None

class ManualPunchCreate(BaseModel):
    employee_id: str
    timestamp: str # YYYY-MM-DD HH:MM[:SS]
    direction: Optional[str] = "AUTO"
    note: Optional[str] = None

class RecalculateRequest(BaseModel):
    date: Optional[str] = None # YYYY-MM-DD
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    employee_id: Optional[str] = None
