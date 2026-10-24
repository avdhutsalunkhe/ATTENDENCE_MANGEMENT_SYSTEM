from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date

class ShiftBase(BaseModel):
    code: str = Field(..., max_length=20, description="Unique shift code (e.g. S1, S2, GEN)")
    name: str = Field(..., max_length=100, description="Shift display name")
    start_time: str = Field(..., description="Start time (HH:MM or HH:MM:SS)")
    end_time: str = Field(..., description="End time (HH:MM or HH:MM:SS)")
    break_start_time: Optional[str] = Field(None, description="Break start (HH:MM)")
    break_end_time: Optional[str] = Field(None, description="Break end (HH:MM)")
    
    # Four Configurable Punch Windows
    first_half_start_cutoff: str = Field("05:45:00", description="Through check-in cutoff")
    first_half_end_start: str = Field("06:00:00", description="1st half end start")
    first_half_end_end: str = Field("11:30:00", description="1st half end cutoff")
    second_half_start_start: str = Field("12:30:00", description="2nd half start start")
    second_half_start_end: str = Field("14:00:00", description="2nd half start cutoff")
    second_half_end_cutoff: str = Field("14:00:00", description="Strictly after checkout cutoff")
    
    grace_period_mins: int = Field(15, ge=0)
    half_day_min_hours: float = Field(4.0, ge=0)
    full_day_min_hours: float = Field(8.0, ge=0)
    
    is_overnight: bool = False
    is_active: bool = True
    color: str = Field("emerald", description="emerald, blue, amber, purple, rose, indigo")

class ShiftCreate(ShiftBase):
    pass

class ShiftUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    break_start_time: Optional[str] = None
    break_end_time: Optional[str] = None
    
    first_half_start_cutoff: Optional[str] = None
    first_half_end_start: Optional[str] = None
    first_half_end_end: Optional[str] = None
    second_half_start_start: Optional[str] = None
    second_half_start_end: Optional[str] = None
    second_half_end_cutoff: Optional[str] = None
    
    grace_period_mins: Optional[int] = None
    half_day_min_hours: Optional[float] = None
    full_day_min_hours: Optional[float] = None
    
    is_overnight: Optional[bool] = None
    is_active: Optional[bool] = None
    color: Optional[str] = None

class ShiftStatusToggle(BaseModel):
    is_active: bool

class ShiftRulesUpdate(BaseModel):
    first_half_start_cutoff: str
    first_half_end_start: str
    first_half_end_end: str
    second_half_start_start: str
    second_half_start_end: str
    second_half_end_cutoff: str

class ShiftResponse(ShiftBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Monthly Shift Assignment Schemas
class DailyAssignmentItem(BaseModel):
    date: str # YYYY-MM-DD
    shift_id: Optional[int] = None
    shift_code: Optional[str] = None
    is_off: bool = False
    notes: Optional[str] = None

class MonthlyScheduleSaveRequest(BaseModel):
    year: int
    month: int
    assignments: List[DailyAssignmentItem]

class PatternSequenceStep(BaseModel):
    shift_id: Optional[int] = None
    is_off: bool = False
    days_count: int = 1

class AutoFillPatternRequest(BaseModel):
    year: int
    month: int
    start_date: Optional[str] = None # defaults to 1st of month
    pattern_mode: str # 'weekly_standard' (Mon-Fri Shift, Sat-Sun Off), 'work6_off1', 'custom_rotation'
    primary_shift_id: Optional[int] = None
    custom_sequence: Optional[List[PatternSequenceStep]] = None
