from pydantic import BaseModel
from typing import Optional

class SystemSettings(BaseModel):
    # Four Configurable Punch Windows
    first_half_start_cutoff: str = "08:14:59"      # Through 08:14:59 (15-min arrival margin of error)
    first_half_end_start: str = "11:59:59"         # From 11:59:59 through 12:30:00, inclusive
    first_half_end_end: str = "12:30:00"
    second_half_start_start: str = "12:30:01"       # From 12:30:01 through 13:00:00, inclusive
    second_half_start_end: str = "13:00:00"
    second_half_end_cutoff: str = "17:00:00"       # Strictly after 17:00:00

    shift_start_time: str = "08:00:00"
    shift_end_time: str = "17:00:00"
    grace_period_mins: int = 15
    half_day_min_hours: float = 4.0
    full_day_min_hours: float = 8.0
    weekend_days: str = "Saturday,Sunday"
    company_name: str = "Acme Global Solutions"
