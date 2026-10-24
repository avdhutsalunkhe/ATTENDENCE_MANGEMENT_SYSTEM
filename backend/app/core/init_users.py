from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.user import User, hash_password
from app.models.leave import Leave
from app.models.audit_log import AuditLog
from sqlalchemy import text
from datetime import datetime

def init_default_users():
    """Ensure User, Leave, and AuditLog tables exist, migrate columns, and default Admin/Clerk users are seeded."""
    Base.metadata.create_all(bind=engine)
    
    # Check and add new columns to users table if they don't exist in existing SQLite DB
    with engine.connect() as conn:
        try:
            columns_info = conn.execute(text("PRAGMA table_info(users)")).fetchall()
            existing_col_names = [col[1] for col in columns_info]
            if "password_updated_at" not in existing_col_names:
                conn.execute(text("ALTER TABLE users ADD COLUMN password_updated_at DATETIME"))
                conn.commit()
            if "must_reset_password" not in existing_col_names:
                conn.execute(text("ALTER TABLE users ADD COLUMN must_reset_password BOOLEAN DEFAULT 0"))
                conn.commit()
        except Exception as e:
            print(f"Migration check notice: {e}")

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # Check Admin
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="System Administrator",
                role="admin",
                is_active=True,
                password_updated_at=now,
                must_reset_password=False
            )
            db.add(admin)
        elif not admin.password_updated_at:
            admin.password_updated_at = now

        # Check Clerk
        clerk = db.query(User).filter(User.username == "clerk").first()
        if not clerk:
            clerk = User(
                username="clerk",
                password_hash=hash_password("clerk123"),
                full_name="Attendance Clerk",
                role="clerk",
                is_active=True,
                password_updated_at=now,
                must_reset_password=False
            )
            db.add(clerk)
        elif not clerk.password_updated_at:
            clerk.password_updated_at = now

        # Ensure all existing users have password_updated_at set
        db.query(User).filter(User.password_updated_at == None).update({"password_updated_at": now})

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error seeding default users: {e}")
    finally:
        db.close()

