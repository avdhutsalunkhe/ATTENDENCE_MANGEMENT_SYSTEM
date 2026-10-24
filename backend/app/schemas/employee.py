from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import date, datetime

class EmployeeBase(BaseModel):
    id: str = Field(..., max_length=50, description="Unique employee identifier (string to preserve leading zeros)")
    name: str = Field(..., max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    designation: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    status: str = Field("Active", max_length=20)
    joining_date: Optional[date] = None

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    designation: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field(None, max_length=20)
    joining_date: Optional[date] = None

class EmployeeStatusUpdate(BaseModel):
    status: str = Field(..., max_length=20)

class EmployeeResponse(EmployeeBase):
    created_at: datetime
    updated_at: datetime
    current_shift: Optional[str] = None
    current_shift_code: Optional[str] = None
    current_shift_color: Optional[str] = None

    class Config:
        from_attributes = True


class EmployeePaginatedResponse(BaseModel):
    items: List[EmployeeResponse]
    total: int
    page: int
    size: int
