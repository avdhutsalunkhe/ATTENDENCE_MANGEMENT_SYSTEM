from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import Optional, List
from datetime import datetime, date

from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.core.audit import log_audit

router = APIRouter()

@router.get("/")
def get_audit_logs(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    action: Optional[str] = None,
    category: Optional[str] = None,
    username: Optional[str] = None
):
    query = db.query(AuditLog)

    if search:
        query = query.filter(
            or_(
                AuditLog.action.ilike(f"%{search}%"),
                AuditLog.username.ilike(f"%{search}%"),
                AuditLog.details.ilike(f"%{search}%"),
                AuditLog.target_id.ilike(f"%{search}%")
            )
        )
    if action and action != "All":
        query = query.filter(AuditLog.action == action.upper())
    if category and category != "All":
        query = query.filter(AuditLog.category == category.lower())
    if username and username != "All":
        query = query.filter(AuditLog.username == username)

    total = query.count()
    items = query.order_by(desc(AuditLog.timestamp)).offset((page - 1) * size).limit(size).all()

    # Calculate summary metrics
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_total = db.query(AuditLog).filter(AuditLog.timestamp >= today_start).count()
    today_logins = db.query(AuditLog).filter(
        AuditLog.timestamp >= today_start,
        AuditLog.action == "LOGIN",
        AuditLog.status == "SUCCESS"
    ).count()
    failed_attempts = db.query(AuditLog).filter(
        AuditLog.timestamp >= today_start,
        AuditLog.status == "FAILED"
    ).count()

    return {
        "items": [item.to_dict() for item in items],
        "total": total,
        "page": page,
        "size": size,
        "summary": {
            "today_total": today_total,
            "today_logins": today_logins,
            "failed_attempts": failed_attempts
        }
    }

@router.delete("/clear")
def clear_audit_logs(db: Session = Depends(get_db)):
    deleted = db.query(AuditLog).delete()
    db.commit()
    log_audit(
        db,
        action="CLEAR_AUDIT_LOGS",
        category="system",
        username="admin",
        details=f"Cleared {deleted} historical audit log records."
    )
    return {"success": True, "message": f"Cleared {deleted} audit log entries."}
