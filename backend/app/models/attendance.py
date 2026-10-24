from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, Float, Index
from datetime import datetime
from typing import Optional
from .base import Base

class AttendancePunchEvent(Base):
    __tablename__ = "attendance_punch_events"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("employees.id", ondelete="CASCADE"), nullable=True, index=True)
    raw_timestamp: Mapped[str] = mapped_column(String(50))
    punched_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    source_direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True) # IN, OUT, AUTO
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    
    employee: Mapped[Optional["Employee"]] = relationship(back_populates="punches")

    __table_args__ = (
        Index("idx_emp_punch", "employee_id", "punched_at"),
    )


class DailyAttendance(Base):
    __tablename__ = "daily_attendance"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(String(50), ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    attendance_date: Mapped[datetime] = mapped_column(DateTime, index=True) # Store date part
    
    first_valid_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_valid_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Assigned Shift details
    shift_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True)
    shift_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    shift_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Half-day evaluation statuses
    first_half_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True) # Present, Missing, Absent
    second_half_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True) # Present, Missing, Absent
    
    punch_count: Mapped[int] = mapped_column(Integer, default=0)
    credited_work_minutes: Mapped[float] = mapped_column(Float, default=0)
    
    attendance_status: Mapped[str] = mapped_column(String(20)) # P, HD, A, L, WO, UNASSIGNED
    
    late_minutes: Mapped[int] = mapped_column(Integer, default=0)
    early_departure_minutes: Mapped[int] = mapped_column(Integer, default=0)
    missing_punch_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    decision_method: Mapped[str] = mapped_column(String(50), default="ENGINE") # ENGINE, ML, MANUAL
    remarks: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    employee: Mapped["Employee"] = relationship(back_populates="daily_attendance")
    shift: Mapped[Optional["Shift"]] = relationship()


    __table_args__ = (
        Index("idx_emp_date", "employee_id", "attendance_date", unique=True),
    )
