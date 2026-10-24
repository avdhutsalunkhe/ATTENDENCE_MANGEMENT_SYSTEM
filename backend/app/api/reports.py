from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional

from app.core.database import get_db
from app.services.report_service import generate_monthly_matrix, generate_excel_report, generate_pdf_report

router = APIRouter()

@router.get("/monthly")
def get_monthly_matrix(
    year: Optional[int] = None,
    month: Optional[int] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    today = date.today()
    y = year or today.year
    m = month or today.month

    if m < 1 or m > 12:
        raise HTTPException(status_code=400, detail="Invalid month (1-12)")

    data = generate_monthly_matrix(db, y, m, department)
    return data


@router.get("/export/excel")
def export_excel(
    year: Optional[int] = None,
    month: Optional[int] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    today = date.today()
    y = year or today.year
    m = month or today.month

    excel_stream = generate_excel_report(db, y, m, department)
    filename = f"Attendance_Report_{y}_{m:02d}.xlsx"

    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/pdf")
def export_pdf(
    year: Optional[int] = None,
    month: Optional[int] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    today = date.today()
    y = year or today.year
    m = month or today.month

    pdf_stream = generate_pdf_report(db, y, m, department)
    filename = f"Attendance_Report_{y}_{m:02d}.pdf"

    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
