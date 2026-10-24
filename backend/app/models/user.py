from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
import hashlib
from .base import Base

def hash_password(password: str) -> str:
    salt = "hrreport_salt_2026"
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()

def verify_password(plain_password: str, hashed: str) -> bool:
    return hash_password(plain_password) == hashed

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    full_name = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="clerk")  # 'admin' or 'clerk'
    is_active = Column(Boolean, default=True)
    password_updated_at = Column(DateTime, default=datetime.utcnow)
    must_reset_password = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def check_password(self, password: str) -> bool:
        return verify_password(password, self.password_hash)

    def days_until_expiration(self) -> int:
        if not self.password_updated_at:
            return 0
        elapsed_days = (datetime.utcnow() - self.password_updated_at).days
        return max(0, 15 - elapsed_days)

    def is_password_expired(self) -> bool:
        if self.must_reset_password:
            return True
        if not self.password_updated_at:
            return True
        return (datetime.utcnow() - self.password_updated_at).days >= 15

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "password_updated_at": self.password_updated_at.isoformat() if self.password_updated_at else None,
            "must_reset_password": bool(self.must_reset_password),
            "days_until_expiration": self.days_until_expiration(),
            "is_password_expired": self.is_password_expired(),
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

