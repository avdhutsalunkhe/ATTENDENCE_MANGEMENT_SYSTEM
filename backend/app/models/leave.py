from sqlalchemy import Column, Integer, String, Boolean, Date, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Leave(Base):
    __tablename__ = "leaves"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type = Column(String(64), nullable=False)  # Casual Leave (CL), Sick Leave (SL), Paid Leave (PL), Unpaid Leave (LWP), etc.
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    days_count = Column(Float, default=1.0)
    is_half_day = Column(Boolean, default=False)
    half_day_session = Column(String(32), nullable=True)  # 'first_half' or 'second_half'
    reason = Column(Text, nullable=True)
    status = Column(String(32), default="APPROVED")  # 'APPROVED', 'PENDING', 'REJECTED'
    applied_by = Column(String(64), default="clerk")
    approved_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", backref="leaves")

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.name if self.employee else None,
            "employee_code": self.employee.id if self.employee else None,
            "department": self.employee.department if self.employee else None,
            "leave_type": self.leave_type,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "days_count": self.days_count,
            "is_half_day": self.is_half_day,
            "half_day_session": self.half_day_session,
            "reason": self.reason,
            "status": self.status,
            "applied_by": self.applied_by,
            "approved_by": self.approved_by,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
