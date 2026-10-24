from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
from datetime import datetime
import io

router = APIRouter()

@router.post("/imports")
async def upload_attendance_file(file: UploadFile = File(...)):
    """
    Handle .xlsx or .dat uploads for attendance events.
    """
    filename = file.filename
    content = await file.read()
    
    records = []
    
    try:
        if filename.endswith(".xlsx"):
            # Excel files
            df = pd.read_excel(io.BytesIO(content))
            
            for index, row in df.iterrows():
                # Extract employee ID - convert to string to preserve leading zeros
                emp_id = str(row.get('Employee ID', ''))
                
                # Precise timestamp parsing preserving all available parts
                raw_time = str(row.get('Timestamp', ''))
                
                # Try to parse ISO format or pandas datetime
                try:
                    parsed_time = pd.to_datetime(raw_time)
                except Exception:
                    parsed_time = None
                    
                records.append({
                    "employee_id": emp_id,
                    "raw_timestamp": raw_time,
                    "parsed_time": parsed_time.isoformat() if parsed_time else None
                })
                
        elif filename.endswith(".dat"):
            # DAT files are typically tab-delimited
            decoded = content.decode('utf-8')
            for line in decoded.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Expected: 101041    2026-09-01 03:46:05    1    0    1    0
                parts = line.split('\t')
                if len(parts) >= 2:
                    emp_id = parts[0].strip()
                    raw_time = parts[1].strip()
                    
                    try:
                        parsed_time = datetime.strptime(raw_time, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        parsed_time = None
                    
                    records.append({
                        "employee_id": emp_id,
                        "raw_timestamp": raw_time,
                        "parsed_time": parsed_time.isoformat() if parsed_time else None
                    })
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return {
        "status": "success",
        "message": f"Successfully parsed {len(records)} records",
        "sample": records[:5]
    }
