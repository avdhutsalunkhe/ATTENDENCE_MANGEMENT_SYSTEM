from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db
from app.models.user import User, hash_password, verify_password
from app.core.audit import log_audit

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "clerk"  # "admin" or "clerk"

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class AdminResetPasswordRequest(BaseModel):
    new_password: str

class PasswordChangeRequest(BaseModel):
    username: str
    old_password: str
    new_password: str

@router.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None
    cleaned_username = req.username.strip()

    user = db.query(User).filter(User.username == cleaned_username).first()
    if not user:
        log_audit(
            db,
            action="LOGIN_FAILED",
            category="auth",
            username=cleaned_username,
            details=f"Login attempt failed: user '{cleaned_username}' does not exist.",
            ip_address=client_ip,
            status="FAILED"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    if not user.is_active:
        log_audit(
            db,
            action="LOGIN_BLOCKED",
            category="auth",
            username=user.username,
            user_id=user.id,
            details="Login blocked: account is deactivated.",
            ip_address=client_ip,
            status="FAILED"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Please contact an administrator."
        )

    if not user.check_password(req.password):
        log_audit(
            db,
            action="LOGIN_FAILED",
            category="auth",
            username=user.username,
            user_id=user.id,
            details="Login attempt failed: invalid password entered.",
            ip_address=client_ip,
            status="FAILED"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Success: log success
    log_audit(
        db,
        action="LOGIN",
        category="auth",
        username=user.username,
        user_id=user.id,
        details=f"User '{user.username}' logged in successfully ({user.role}).",
        ip_address=client_ip,
        status="SUCCESS"
    )

    is_expired = user.is_password_expired()
    days_left = user.days_until_expiration()

    return {
        "success": True,
        "token": f"auth_tok_{user.username}_{int(datetime.utcnow().timestamp())}",
        "user": user.to_dict(),
        "password_expired": is_expired,
        "days_until_expiration": days_left,
        "must_reset_password": bool(user.must_reset_password)
    }

@router.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id).all()
    return [u.to_dict() for u in users]

@router.post("/users")
def create_user(req: UserCreate, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None
    existing = db.query(User).filter(User.username == req.username.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    if len(req.password.strip()) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    now = datetime.utcnow()
    new_user = User(
        username=req.username.strip(),
        password_hash=hash_password(req.password),
        full_name=req.full_name.strip(),
        role=req.role.strip().lower(),
        is_active=True,
        password_updated_at=now,
        must_reset_password=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit(
        db,
        action="CREATE_USER",
        category="auth",
        username="admin",
        target_type="user",
        target_id=new_user.username,
        details=f"Created user '{new_user.username}' with role '{new_user.role}'.",
        ip_address=client_ip,
        status="SUCCESS"
    )

    return new_user.to_dict()

@router.post("/users/batch")
def create_users_batch(users_list: List[UserCreate], request: Request, db: Session = Depends(get_db)):
    """Add multiple users in a single request (Batch user creation)."""
    client_ip = request.client.host if request.client else None
    created = []
    skipped = []

    now = datetime.utcnow()
    for item in users_list:
        uname = item.username.strip()
        if not uname:
            continue
        existing = db.query(User).filter(User.username == uname).first()
        if existing:
            skipped.append(f"{uname} (already exists)")
            continue
        
        user = User(
            username=uname,
            password_hash=hash_password(item.password or "Welcome@123"),
            full_name=item.full_name.strip() or uname,
            role=item.role.strip().lower() if item.role in ["admin", "clerk"] else "clerk",
            is_active=True,
            password_updated_at=now,
            must_reset_password=False
        )
        db.add(user)
        created.append(uname)

    db.commit()

    log_audit(
        db,
        action="BATCH_CREATE_USERS",
        category="auth",
        username="admin",
        details=f"Batch created {len(created)} users: {', '.join(created)}. Skipped: {len(skipped)}.",
        ip_address=client_ip,
        status="SUCCESS"
    )

    return {
        "success": True,
        "created_count": len(created),
        "created_users": created,
        "skipped": skipped
    }

@router.put("/users/{user_id}")
def update_user(user_id: int, req: UserUpdate, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.full_name is not None:
        user.full_name = req.full_name.strip()
    if req.role is not None and req.role in ["admin", "clerk"]:
        user.role = req.role
    if req.is_active is not None:
        user.is_active = req.is_active

    db.commit()
    db.refresh(user)

    log_audit(
        db,
        action="UPDATE_USER",
        category="auth",
        username="admin",
        target_type="user",
        target_id=user.username,
        details=f"Updated user '{user.username}' (Active: {user.is_active}, Role: {user.role}).",
        ip_address=client_ip,
        status="SUCCESS"
    )

    return user.to_dict()

@router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Safety guard: ensure at least one active admin remains
    if user.role == "admin":
        admin_count = db.query(User).filter(User.role == "admin", User.is_active == True, User.id != user_id).count()
        if admin_count == 0:
            raise HTTPException(status_code=400, detail="Cannot delete the only remaining active admin account")

    deleted_username = user.username
    db.delete(user)
    db.commit()

    log_audit(
        db,
        action="DELETE_USER",
        category="auth",
        username="admin",
        target_type="user",
        target_id=deleted_username,
        details=f"Deleted user account '{deleted_username}'.",
        ip_address=client_ip,
        status="SUCCESS"
    )

    return {"success": True, "message": f"User {deleted_username} deleted successfully"}

@router.post("/users/{user_id}/reset-password")
def admin_reset_password(user_id: int, req: AdminResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Admin manually resets password for a user and renews the 15-day period."""
    client_ip = request.client.host if request.client else None
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if len(req.new_password.strip()) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    user.password_hash = hash_password(req.new_password.strip())
    user.password_updated_at = datetime.utcnow()
    user.must_reset_password = False
    db.commit()

    log_audit(
        db,
        action="ADMIN_RESET_PASSWORD",
        category="auth",
        username="admin",
        target_type="user",
        target_id=user.username,
        details=f"Admin reset password for user '{user.username}'. 15-day reset timer renewed.",
        ip_address=client_ip,
        status="SUCCESS"
    )

    return {
        "success": True, 
        "message": f"Password reset successfully for {user.username}. 15-day reset timer renewed.",
        "user": user.to_dict()
    }

@router.post("/users/{user_id}/force-reset")
def force_password_reset(user_id: int, request: Request, db: Session = Depends(get_db)):
    """Force a user to reset their password on next login."""
    client_ip = request.client.host if request.client else None
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.must_reset_password = True
    db.commit()

    log_audit(
        db,
        action="FORCE_PASSWORD_RESET",
        category="auth",
        username="admin",
        target_type="user",
        target_id=user.username,
        details=f"Forced password reset required for user '{user.username}'.",
        ip_address=client_ip,
        status="SUCCESS"
    )

    return {"success": True, "message": f"User {user.username} will be required to reset password on login."}

@router.post("/change-password")
def change_password(req: PasswordChangeRequest, request: Request, db: Session = Depends(get_db)):
    """User changes their own password, renewing the 15-day reset period."""
    client_ip = request.client.host if request.client else None
    user = db.query(User).filter(User.username == req.username.strip()).first()
    if not user:
        log_audit(
            db,
            action="PASSWORD_CHANGE_FAILED",
            category="auth",
            username=req.username,
            details="Password change failed: user not found.",
            ip_address=client_ip,
            status="FAILED"
        )
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.check_password(req.old_password):
        log_audit(
            db,
            action="PASSWORD_CHANGE_FAILED",
            category="auth",
            username=user.username,
            user_id=user.id,
            details="Password change failed: current password incorrect.",
            ip_address=client_ip,
            status="FAILED"
        )
        raise HTTPException(status_code=400, detail="Current password incorrect")

    if len(req.new_password.strip()) < 4:
        raise HTTPException(status_code=400, detail="New password must be at least 4 characters")

    user.password_hash = hash_password(req.new_password.strip())
    user.password_updated_at = datetime.utcnow()
    user.must_reset_password = False
    db.commit()

    log_audit(
        db,
        action="PASSWORD_CHANGE",
        category="auth",
        username=user.username,
        user_id=user.id,
        target_type="user",
        target_id=user.username,
        details=f"User '{user.username}' successfully changed password. 15-day reset timer renewed.",
        ip_address=client_ip,
        status="SUCCESS"
    )

    return {
        "success": True, 
        "message": "Password updated successfully. 15-day reset timer renewed.",
        "days_until_expiration": 15
    }
