from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, Float, Index, Date, UniqueConstraint
from datetime import datetime, timezone, date
from typing import Optional, List
from .base import Base

class Shift(Base):
    __tablename__ = "shifts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True) # e.g. "S1", "S2"
    name: Mapped[str] = mapped_column(String(100)) # e.g. "Morning Shift"
    start_time: Mapped[str] = mapped_column(String(10)) # "06:00" or "06:00:00"
    end_time: Mapped[str] = mapped_column(String(10)) # "14:00" or "14:00:00"
    break_start_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True) # "13:00"
    break_end_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True) # "13:30"
    
    # Four Configurable Punch Windows for this specific shift
    first_half_start_cutoff: Mapped[str] = mapped_column(String(10), default="05:45:00")
    first_half_end_start: Mapped[str] = mapped_column(String(10), default="06:00:00")
    first_half_end_end: Mapped[str] = mapped_column(String(10), default="11:30:00")
    second_half_start_start: Mapped[str] = mapped_column(String(10), default="12:30:00")
    second_half_start_end: Mapped[str] = mapped_column(String(10), default="14:00:00")
    second_half_end_cutoff: Mapped[str] = mapped_column(String(10), default="14:00:00")
    
    grace_period_mins: Mapped[int] = mapped_column(Integer, default=15)
    half_day_min_hours: Mapped[float] = mapped_column(Float, default=4.0)
    full_day_min_hours: Mapped[float] = mapped_column(Float, default=8.0)
    
    is_overnight: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    color: Mapped[Optional[str]] = mapped_column(String(30), default="emerald") # emerald, blue, amber, purple, rose, indigo
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

    assignments: Mapped[List["EmployeeShiftAssignment"]] = relationship(
        back_populates="shift",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class EmployeeShiftAssignment(Base):
    __tablename__ = "employee_shift_assignments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(String(50), ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    shift_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True)
    assignment_date: Mapped[date] = mapped_column(Date, index=True)
    is_off: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED") # SCHEDULED, PUBLISHED, DRAFT
    assigned_by: Mapped[Optional[str]] = mapped_column(String(100), default="ADMIN")
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

    employee: Mapped["Employee"] = relationship(back_populates="shift_assignments")
    shift: Mapped[Optional["Shift"]] = relationship(back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("employee_id", "assignment_date", name="uq_emp_date_shift"),
        Index("idx_emp_shift_date", "employee_id", "assignment_date"),
    )
