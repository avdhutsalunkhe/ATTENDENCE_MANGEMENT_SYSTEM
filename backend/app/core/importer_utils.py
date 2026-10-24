import io
import re
import pandas as pd
from typing import List, Optional, Tuple, Any, Dict
from datetime import datetime, date, time

def clean_emp_id(val: Any) -> str:
    """
    Clean employee/user ID from various data types (float 15352.0, int 15352, str ' 15352 ').
    """
    if val is None or pd.isna(val):
        return ""
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
    s = str(val).strip()
    if s.lower() in ("nan", "none", "null", ""):
        return ""
    # Strip trailing .0 if present
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s

def normalize_header(col: Any) -> str:
    """
    Normalize header names by removing non-alphanumeric characters and lowercasing.
    e.g. 'User ID.' -> 'userid', 'Employee_Name' -> 'employeename', 'Punch-Time' -> 'punchtime'.
    """
    if col is None:
        return ""
    s = str(col).strip().lower()
    return re.sub(r'[^a-z0-9]', '', s)

def find_best_column(columns: List[Any], aliases: List[str]) -> Optional[Any]:
    """
    Find original column name that matches any normalized alias.
    """
    norm_map = {normalize_header(c): c for c in columns}
    for alias in aliases:
        norm_alias = normalize_header(alias)
        if norm_alias in norm_map:
            return norm_map[norm_alias]
    return None

def read_tabular_file(content: bytes, filename: str) -> List[Tuple[str, pd.DataFrame]]:
    """
    Reads excel or csv content, checking sheets and detecting actual header row if row 0 is a title banner.
    Returns list of (sheet_name, dataframe).
    """
    results: List[Tuple[str, pd.DataFrame]] = []
    
    if filename.endswith(('.xlsx', '.xls')):
        xl = pd.ExcelFile(io.BytesIO(content))
        for sheet_name in xl.sheet_names:
            # First read first 10 rows without header to inspect
            df_raw = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name, header=None, nrows=10)
            if df_raw.empty:
                continue
            
            # Find candidate header row
            header_row = 0
            best_score = 0
            keywords = {'userid', 'empid', 'employeeid', 'id', 'name', 'time', 'timestamp', 'date', 'status', 'punch'}
            
            for r_idx in range(min(5, len(df_raw))):
                row_vals = [normalize_header(v) for v in df_raw.iloc[r_idx].dropna()]
                score = sum(1 for v in row_vals if any(k in v for k in keywords))
                if score > best_score:
                    best_score = score
                    header_row = r_idx
            
            # Load with the determined header row
            df = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name, header=header_row)
            if not df.empty:
                results.append((sheet_name, df))
    else:
        # CSV
        df = pd.read_csv(io.BytesIO(content))
        results.append(("CSV", df))
        
    return results

def parse_punch_datetime(row: pd.Series, time_col: Optional[Any], date_col: Optional[Any] = None) -> Optional[datetime]:
    """
    Robustly parse datetime from either a single datetime column or separate Date + Time columns.
    """
    t_val = row.get(time_col) if time_col is not None else None
    d_val = row.get(date_col) if date_col is not None else None

    if pd.isna(t_val) and pd.isna(d_val):
        return None

    # Case 1: Separate Date and Time columns
    if d_val is not None and not pd.isna(d_val) and t_val is not None and not pd.isna(t_val):
        d_str = str(d_val).split()[0] if not isinstance(d_val, (date, datetime)) else d_val.strftime("%Y-%m-%d")
        t_str = str(t_val).split()[-1] if not isinstance(t_val, (time, datetime)) else t_val.strftime("%H:%M:%S")
        try:
            p_dt = pd.to_datetime(f"{d_str} {t_str}")
            if hasattr(p_dt, 'to_pydatetime'):
                return p_dt.to_pydatetime()
            return p_dt
        except Exception:
            pass

    # Case 2: Single combined column
    val_to_parse = t_val if (t_val is not None and not pd.isna(t_val)) else d_val
    try:
        p_dt = pd.to_datetime(val_to_parse)
        if hasattr(p_dt, 'to_pydatetime'):
            return p_dt.to_pydatetime()
        return p_dt
    except Exception:
        return None
