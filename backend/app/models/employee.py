from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Date
from datetime import datetime, timezone
from typing import List, Optional
from .base import Base

class Employee(Base):
    __tablename__ = "employees"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Active")
    joining_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships with cascade delete
    punches: Mapped[List["AttendancePunchEvent"]] = relationship(
        back_populates="employee", 
        cascade="all, delete-orphan", 
        passive_deletes=True
    )
    daily_attendance: Mapped[List["DailyAttendance"]] = relationship(
        back_populates="employee", 
        cascade="all, delete-orphan", 
        passive_deletes=True
    )
    shift_assignments: Mapped[List["EmployeeShiftAssignment"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

