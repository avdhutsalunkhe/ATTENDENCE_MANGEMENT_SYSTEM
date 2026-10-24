from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.employees import router as employees_router
from app.api.attendance import router as attendance_router
from app.api.dashboard import router as dashboard_router
from app.api.reports import router as reports_router
from app.api.settings import router as settings_router
from app.api.shifts import router as shifts_router
from app.api.auth import router as auth_router
from app.api.leaves import router as leaves_router
from app.api.audit_logs import router as audit_logs_router
from app.core.database import engine
from app.core.init_shifts import init_all_shifts
from app.core.init_users import init_default_users
from app.models.base import Base

# Ensure all tables and default shift configurations exist
init_all_shifts()
# Ensure User and Leave tables exist and Admin/Clerk credentials are ready
init_default_users()

app = FastAPI(
    title="Intelligent Attendance & HR Analytics Engine",
    description="Enterprise Biometric Attendance Processing, Shift Rules, Analytics & Reporting Engine",
    version="2.0.0"
)

# Robust CORS Configuration supporting 182.66.233.66, localhost, LAN IPs, and desktop app origins (file://, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Route Registrations
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication & Users"])
app.include_router(audit_logs_router, prefix="/api/audit-logs", tags=["Audit & Activity Logs"])
app.include_router(leaves_router, prefix="/api/leaves", tags=["Leave Management"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(employees_router, prefix="/api/employees", tags=["Employees"])
app.include_router(attendance_router, prefix="/api/attendance", tags=["Attendance & Biometrics"])
app.include_router(reports_router, prefix="/api/reports", tags=["Reports & Analytics"])
app.include_router(settings_router, prefix="/api/settings", tags=["Settings & Configuration"])
app.include_router(shifts_router, prefix="/api/shifts", tags=["Shift Management"])
app.include_router(shifts_router, prefix="/api/settings/shifts", tags=["Shift Settings"])



@app.get("/")
def read_root():
    return {
        "system": "Intelligent Attendance Engine API",
        "status": "operational",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/api/health")
def api_health():
    return {
        "system": "Intelligent Attendance Engine API",
        "status": "operational",
        "version": "2.0.0"
    }
