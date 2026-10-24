from sqlalchemy.orm import Session
from datetime import datetime
from app.models.audit_log import AuditLog

def log_audit(
    db: Session,
    action: str,
    category: str = "system",
    username: str = None,
    user_id: int = None,
    target_type: str = None,
    target_id: str = None,
    details: str = None,
    ip_address: str = None,
    status: str = "SUCCESS"
):
    """
    Safely create an audit log entry without interrupting main flow.
    """
    try:
        entry = AuditLog(
            timestamp=datetime.utcnow(),
            action=action.upper(),
            category=category.lower(),
            username=username or "system",
            user_id=user_id,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details,
            ip_address=ip_address,
            status=status.upper()
        )
        db.add(entry)
        db.commit()
        return entry
    except Exception as e:
        db.rollback()
        print(f"Failed to record audit log: {e}")
        return None
