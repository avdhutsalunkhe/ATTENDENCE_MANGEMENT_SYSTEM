from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
import pandas as pd
import io

from datetime import date
from app.core.database import get_db
from app.models.employee import Employee
from app.models.attendance import DailyAttendance
from app.models.shift import EmployeeShiftAssignment
from app.core.audit import log_audit
from app.schemas.employee import (
    EmployeeCreate, EmployeeUpdate, EmployeeStatusUpdate, 
    EmployeeResponse, EmployeePaginatedResponse
)


router = APIRouter()

@router.get("/", response_model=EmployeePaginatedResponse)
def get_employees(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
    search: Optional[str] = None,
    department: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status")
):
    query = db.query(Employee)
    
    if search:
        query = query.filter(or_(
            Employee.id.ilike(f"%{search}%"),
            Employee.name.ilike(f"%{search}%"),
            Employee.department.ilike(f"%{search}%"),
            Employee.designation.ilike(f"%{search}%")
        ))
    if department and department != "All":
        query = query.filter(Employee.department == department)
    if status_filter and status_filter != "All":
        query = query.filter(Employee.status == status_filter)
        
    total = query.count()
    items = query.order_by(Employee.name).offset((page - 1) * size).limit(size).all()
    
    today_d = date.today()
    emp_ids = [e.id for e in items]
    assignments = db.query(EmployeeShiftAssignment).filter(
        EmployeeShiftAssignment.employee_id.in_(emp_ids),
        EmployeeShiftAssignment.assignment_date == today_d
    ).all()
    assign_map = {a.employee_id: a for a in assignments}

    res_items = []
    for emp in items:
        assign = assign_map.get(emp.id)
        shift_code = None
        shift_label = None
        shift_color = None
        if assign:
            if assign.is_off:
                shift_code = "OFF"
                shift_label = "Day Off"
                shift_color = "slate"
            elif assign.shift:
                shift_code = assign.shift.code
                shift_label = f"{assign.shift.code} - {assign.shift.name}"
                shift_color = assign.shift.color
        
        emp_dict = {
            "id": emp.id,
            "name": emp.name,
            "department": emp.department,
            "designation": emp.designation,
            "email": emp.email,
            "phone": emp.phone,
            "status": emp.status,
            "joining_date": emp.joining_date,
            "created_at": emp.created_at,
            "updated_at": emp.updated_at,
            "current_shift": shift_label,
            "current_shift_code": shift_code,
            "current_shift_color": shift_color
        }
        res_items.append(emp_dict)

    return {
        "items": res_items,
        "total": total,
        "page": page,
        "size": size
    }


@router.get("/departments")
def get_departments(db: Session = Depends(get_db)):
    depts = db.query(Employee.department).distinct().filter(
        Employee.department != None,
        Employee.department != ""
    ).all()
    return sorted([d[0] for d in depts if d[0]])

@router.get("/summary")
def get_employee_summary(db: Session = Depends(get_db)):
    total = db.query(Employee).count()
    active = db.query(Employee).filter(Employee.status == "Active").count()
    inactive = db.query(Employee).filter(Employee.status == "Inactive").count()
    missing_info = db.query(Employee).filter(or_(
        Employee.department == None,
        Employee.department == "",
        Employee.designation == None,
        Employee.designation == ""
    )).count()
    
    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "missing_info": missing_info
    }

@router.post("/", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db)):
    existing = db.query(Employee).filter(Employee.id == employee.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee with this ID already exists")
        
    db_employee = Employee(**employee.model_dump())
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)

    log_audit(
        db,
        action="CREATE_EMPLOYEE",
        category="employee",
        username="admin",
        target_type="employee",
        target_id=db_employee.id,
        details=f"Created employee profile: {db_employee.name} ({db_employee.department or 'No Dept'})."
    )

    return db_employee

@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: str, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: str, employee_update: EmployeeUpdate, db: Session = Depends(get_db)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    update_data = employee_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_employee, key, value)
        
    db.commit()
    db.refresh(db_employee)

    log_audit(
        db,
        action="UPDATE_EMPLOYEE",
        category="employee",
        username="admin",
        target_type="employee",
        target_id=employee_id,
        details=f"Updated employee profile: {db_employee.name}."
    )

    return db_employee

@router.patch("/{employee_id}/status", response_model=EmployeeResponse)
def update_employee_status(employee_id: str, status_update: EmployeeStatusUpdate, db: Session = Depends(get_db)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    db_employee.status = status_update.status
    db.commit()
    db.refresh(db_employee)

    log_audit(
        db,
        action="UPDATE_EMPLOYEE_STATUS",
        category="employee",
        username="admin",
        target_type="employee",
        target_id=employee_id,
        details=f"Changed status of {db_employee.name} to {status_update.status}."
    )

    return db_employee

@router.delete("/{employee_id}")
def delete_employee(employee_id: str, db: Session = Depends(get_db)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    emp_name = db_employee.name
    try:
        from app.models.attendance import AttendancePunchEvent
        db.query(DailyAttendance).filter(DailyAttendance.employee_id == employee_id).delete(synchronize_session=False)
        db.query(AttendancePunchEvent).filter(AttendancePunchEvent.employee_id == employee_id).delete(synchronize_session=False)
        db.delete(db_employee)
        db.commit()

        log_audit(
            db,
            action="DELETE_EMPLOYEE",
            category="employee",
            username="admin",
            target_type="employee",
            target_id=employee_id,
            details=f"Deleted employee {emp_name} (ID: {employee_id}) and corresponding attendance history."
        )

        return {"message": f"Employee {employee_id} deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete employee: {str(e)}")


@router.get("/{employee_id}/attendance")
def get_employee_attendance_history(employee_id: str, limit: int = 30, db: Session = Depends(get_db)):
    records = db.query(DailyAttendance).filter(
        DailyAttendance.employee_id == employee_id
    ).order_by(DailyAttendance.attendance_date.desc()).limit(limit).all()

    return [{
        "date": r.attendance_date.strftime("%Y-%m-%d"),
        "in_time": r.first_valid_in_at.strftime("%I:%M %p") if r.first_valid_in_at else "—",
        "out_time": r.last_valid_out_at.strftime("%I:%M %p") if r.last_valid_out_at else "—",
        "work_hours": round(r.credited_work_minutes / 60.0, 1),
        "status": r.attendance_status,
        "late_minutes": r.late_minutes,
        "missing_punch": r.missing_punch_flag
    } for r in records]

from app.core.importer_utils import (
    clean_emp_id, normalize_header, find_best_column, read_tabular_file
)

@router.post("/import")
async def import_employees(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls or .csv files are supported")
        
    content = await file.read()
    try:
        tables = read_tabular_file(content, file.filename)
        if not tables:
            raise HTTPException(status_code=400, detail="The uploaded file appears to be empty.")

        id_aliases = ['userid', 'user_id', 'user id', 'user id.', 'empid', 'emp_id', 'emp id', 'employeeid', 'employee_id', 'employee id', 'empcode', 'emp code', 'code', 'id', 'badge', 'badgenumber', 'acno', 'ac-no', 'ac-no.', 'enrollid', 'enroll id']
        name_aliases = ['employeename', 'employee_name', 'employee name', 'name', 'fullname', 'full name', 'empname', 'emp_name', 'emp name', 'staffname', 'workername']
        dept_aliases = ['department', 'dept', 'departmentname', 'department_name', 'division', 'unit', 'team']
        desig_aliases = ['designation', 'role', 'title', 'position', 'job title', 'jobtitle']
        email_aliases = ['email', 'email address', 'email_address', 'mail', 'e-mail']
        phone_aliases = ['phone', 'mobile', 'contact', 'cell', 'phone number', 'phonenumber', 'contact number']

        new_count = 0
        updated_count = 0
        all_cols_seen = []

        for sheet_name, df in tables:
            cols = list(df.columns)
            all_cols_seen.extend([str(c) for c in cols])

            id_col = find_best_column(cols, id_aliases)
            name_col = find_best_column(cols, name_aliases)
            dept_col = find_best_column(cols, dept_aliases)
            desig_col = find_best_column(cols, desig_aliases)
            email_col = find_best_column(cols, email_aliases)
            phone_col = find_best_column(cols, phone_aliases)

            if not id_col:
                continue

            for _, row in df.iterrows():
                emp_id = clean_emp_id(row.get(id_col))
                if not emp_id:
                    continue

                raw_name = str(row.get(name_col)).strip() if (name_col and not pd.isna(row.get(name_col))) else ""
                name = raw_name if (raw_name and raw_name.lower() != 'nan') else f"Employee {emp_id}"

                department = str(row.get(dept_col)).strip() if (dept_col and not pd.isna(row.get(dept_col))) else None
                if department and department.lower() == 'nan': department = None

                designation = str(row.get(desig_col)).strip() if (desig_col and not pd.isna(row.get(desig_col))) else None
                if designation and designation.lower() == 'nan': designation = None

                email = str(row.get(email_col)).strip() if (email_col and not pd.isna(row.get(email_col))) else None
                if email and email.lower() == 'nan': email = None

                phone = str(row.get(phone_col)).strip() if (phone_col and not pd.isna(row.get(phone_col))) else None
                if phone and phone.lower() == 'nan': phone = None

                existing = db.query(Employee).filter(Employee.id == emp_id).first()
                if existing:
                    # Update info, especially if placeholder name was used
                    if name and (existing.name.startswith("Employee ") or name != f"Employee {emp_id}"):
                        existing.name = name
                    if department: existing.department = department
                    if designation: existing.designation = designation
                    if email: existing.email = email
                    if phone: existing.phone = phone
                    updated_count += 1
                else:
                    new_emp = Employee(
                        id=emp_id,
                        name=name,
                        department=department,
                        designation=designation,
                        email=email,
                        phone=phone,
                        status="Active"
                    )
                    db.add(new_emp)
                    new_count += 1

        total_processed = new_count + updated_count
        if total_processed == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Could not find valid employee records. Columns identified: {', '.join(set(all_cols_seen))}. Please ensure an ID column ('UserId', 'Employee ID', 'EmpID') is present."
            )

        db.commit()
        return {
            "status": "success",
            "message": f"Successfully processed {total_processed} employees ({new_count} added, {updated_count} updated).",
            "added": new_count,
            "updated": updated_count
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
