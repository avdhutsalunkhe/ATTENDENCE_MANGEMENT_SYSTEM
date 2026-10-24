import sys
import os
from pathlib import Path
from datetime import datetime, date, timedelta
import pandas as pd

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.employee import Employee
from app.models.attendance import AttendancePunchEvent, DailyAttendance
from app.models.settings import Setting
from app.services.attendance_service import (
    import_punch_records, process_punches_for_date, get_settings, DEFAULT_SETTINGS
)
from app.core.importer_utils import (
    clean_emp_id, read_tabular_file, parse_punch_datetime
)

def run():
    print("=" * 60)
    print("Starting Report Data Reset and Import")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Step 1: Clear old data
        print("\n[Step 1] Clearing old data from database...")
        deleted_punches = db.query(AttendancePunchEvent).delete()
        deleted_daily = db.query(DailyAttendance).delete()
        deleted_employees = db.query(Employee).delete()
        db.commit()
        print(f"  - Deleted {deleted_punches} punch events")
        print(f"  - Deleted {deleted_daily} daily attendance rows")
        print(f"  - Deleted {deleted_employees} employees")

        # Ensure all default settings exist in DB
        for k, v in DEFAULT_SETTINGS.items():
            existing = db.query(Setting).filter(Setting.key == k).first()
            if not existing:
                db.add(Setting(key=k, value=str(v)))
        db.commit()
        print("  - System shift & 4-window settings verified in database.")

        # Step 2: Import Prumatech Employee Master Data
        emp_file = Path(r"D:\HRReport\Prumatech_Employee_Data.xlsx")
        print(f"\n[Step 2] Importing Employee Data from {emp_file.name}...")
        if emp_file.exists():
            df_emp = pd.read_excel(emp_file)
            added_emp = 0
            for _, row in df_emp.iterrows():
                uid = clean_emp_id(row.get("UserId"))
                name = str(row.get("Employee_Name", "")).strip()
                if not uid:
                    continue
                if not name or name.lower() == "nan":
                    name = f"Employee {uid}"
                
                emp = Employee(
                    id=uid,
                    name=name,
                    department="Operations",
                    designation="Staff",
                    status="Active"
                )
                db.add(emp)
                added_emp += 1
            db.commit()
            print(f"  - Added {added_emp} employees from {emp_file.name}")
        else:
            print(f"  - Warning: {emp_file} not found!")

        # Step 3: Import 6426160301474_attlog.dat
        dat_file = Path(r"D:\HRReport\6426160301474_attlog.dat")
        print(f"\n[Step 3] Importing Punch Logs from {dat_file.name}...")
        if dat_file.exists():
            with open(dat_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            records_dat = []
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t") if "\t" in line else line.split()
                if len(parts) >= 2:
                    emp_id = clean_emp_id(parts[0])
                    if not emp_id:
                        continue
                    ts_str = parts[1].strip()
                    try:
                        p_dt = pd.to_datetime(ts_str)
                        if hasattr(p_dt, "to_pydatetime"):
                            p_dt = p_dt.to_pydatetime()
                    except Exception:
                        continue

                    # Strictly extract employee ID and datetime only, ignoring extra biometric codes (1 0 1 0)
                    records_dat.append({
                        "employee_id": emp_id,
                        "employee_name": None,
                        "raw_timestamp": p_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "punched_at": p_dt,
                        "source_direction": "AUTO"
                    })

            res_dat = import_punch_records(db, records_dat, source_id=dat_file.name)
            print(f"  - Total records parsed: {res_dat['total_records']}")
            print(f"  - New punches stored:   {res_dat['new_punches']}")
            print(f"  - Duplicates skipped:   {res_dat['duplicates']}")
            print(f"  - Dates covered:        {len(res_dat['dates_processed'])}")
        else:
            print(f"  - Warning: {dat_file} not found!")

        # Step 4: Import Bio_Lab_Punch_02-10-2026.xlsx
        biolab_file = Path(r"D:\HRReport\Bio_Lab_Punch_02-10-2026.xlsx")
        print(f"\n[Step 4] Importing Punch Logs from {biolab_file.name}...")
        if biolab_file.exists():
            with open(biolab_file, "rb") as f:
                tables = read_tabular_file(f.read(), biolab_file.name)
            
            records_biolab = []
            for sheet_name, df in tables:
                id_col = "User ID." if "User ID." in df.columns else None
                time_col = "Time" if "Time" in df.columns else None
                name_col = "Name" if "Name" in df.columns else None
                mode_col = "Mode" if "Mode" in df.columns else None

                for _, row in df.iterrows():
                    emp_id = clean_emp_id(row.get(id_col)) if id_col else ""
                    if not emp_id or "count" in emp_id.lower():
                        continue
                    p_dt = parse_punch_datetime(row, time_col=time_col)
                    if not p_dt or not isinstance(p_dt, datetime):
                        continue
                    
                    emp_name = str(row.get(name_col)).strip() if (name_col and not pd.isna(row.get(name_col))) else None
                    if emp_name and emp_name.lower() in ("nan", "none", ""):
                        emp_name = None

                    records_biolab.append({
                        "employee_id": emp_id,
                        "employee_name": emp_name,
                        "raw_timestamp": p_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "punched_at": p_dt,
                        "source_direction": "AUTO"
                    })

            res_biolab = import_punch_records(db, records_biolab, source_id=biolab_file.name)
            print(f"  - Total records parsed: {res_biolab['total_records']}")
            print(f"  - New punches stored:   {res_biolab['new_punches']}")
            print(f"  - Duplicates skipped:   {res_biolab['duplicates']}")
            print(f"  - Dates covered:        {len(res_biolab['dates_processed'])}")
        else:
            print(f"  - Warning: {biolab_file} not found!")

        # Step 5: Import Book1.xlsx
        book1_file = Path(r"D:\HRReport\Book1.xlsx")
        print(f"\n[Step 5] Importing Punch Logs from {book1_file.name}...")
        if book1_file.exists():
            with open(book1_file, "rb") as f:
                tables = read_tabular_file(f.read(), book1_file.name)
            
            records_book1 = []
            for sheet_name, df in tables:
                id_col = "User ID." if "User ID." in df.columns else None
                time_col = "Date&Time" if "Date&Time" in df.columns else None
                name_col = "Name" if "Name" in df.columns else None

                for _, row in df.iterrows():
                    emp_id = clean_emp_id(row.get(id_col)) if id_col else ""
                    if not emp_id or "count" in emp_id.lower():
                        continue
                    p_dt = parse_punch_datetime(row, time_col=time_col)
                    if not p_dt or not isinstance(p_dt, datetime):
                        continue
                    
                    emp_name = str(row.get(name_col)).strip() if (name_col and not pd.isna(row.get(name_col))) else None
                    if emp_name and emp_name.lower() in ("nan", "none", ""):
                        emp_name = None

                    records_book1.append({
                        "employee_id": emp_id,
                        "employee_name": emp_name,
                        "raw_timestamp": p_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "punched_at": p_dt,
                        "source_direction": "AUTO"
                    })

            res_book1 = import_punch_records(db, records_book1, source_id=book1_file.name)
            print(f"  - Total records parsed: {res_book1['total_records']}")
            print(f"  - New punches stored:   {res_book1['new_punches']}")
            print(f"  - Duplicates skipped:   {res_book1['duplicates']}")
            print(f"  - Dates covered:        {len(res_book1['dates_processed'])}")
        else:
            print(f"  - Warning: {book1_file} not found!")

        # Step 6: Full month reconciliation for September 2026
        # Ensure every active employee has a daily attendance row for each calendar day
        print("\n[Step 6] Running complete daily attendance reconciliation for September 2026...")
        settings = get_settings(db)
        d_start = date(2026, 9, 1)
        d_end = date(2026, 9, 30)
        curr = d_start
        total_days = 0
        while curr <= d_end:
            process_punches_for_date(db, curr, settings)
            curr += timedelta(days=1)
            total_days += 1
        print(f"  - Reconciled all {total_days} days for all employees.")

        # Summary counts
        print("\n" + "=" * 60)
        print("IMPORT COMPLETED SUCCESSFULLY - SUMMARY")
        print("=" * 60)
        total_emps = db.query(Employee).count()
        total_punches = db.query(AttendancePunchEvent).count()
        total_daily = db.query(DailyAttendance).count()
        print(f"Total Active Employees:  {total_emps}")
        print(f"Total Valid Punches:     {total_punches}")
        print(f"Total Daily Attendance:  {total_daily}")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Migration/Import failed: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    run()
