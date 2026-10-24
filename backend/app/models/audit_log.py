from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from .base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    username = Column(String(64), nullable=True, index=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(64), nullable=False, index=True)  # LOGIN, CREATE_USER, DELETE_USER, UPDATE_EMPLOYEE, etc.
    category = Column(String(32), default="system", index=True)  # auth, employee, shift, attendance, system
    target_type = Column(String(64), nullable=True)  # user, employee, shift, attendance, system
    target_id = Column(String(128), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    status = Column(String(32), default="SUCCESS")  # SUCCESS, FAILED, WARNING

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "username": self.username or "system",
            "user_id": self.user_id,
            "action": self.action,
            "category": self.category,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "status": self.status
        }
