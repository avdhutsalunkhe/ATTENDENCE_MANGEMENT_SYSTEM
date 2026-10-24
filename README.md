# Attendance Management System (HRReport)

> **Enterprise Biometric Attendance Processing, Shift Intelligence, Leave Management & HR Analytics Engine**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-2.0.0-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-19.2-61DAFB?logo=react)
![Vite](https://img.shields.io/badge/Vite-8.3-646CFF?logo=vite)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-v4.3-38B2AC?logo=tailwindcss)
![Electron](https://img.shields.io/badge/Electron-41.2-47848F?logo=electron)
![Database](https://img.shields.io/badge/Database-SQLite%20%2F%20MySQL-orange?logo=sqlite)

---

## 📋 Overview

The **Attendance Management System (HRReport)** is a production-grade, enterprise attendance automation and workforce analytics platform. Designed to bridge hardware biometric devices (punch machines) with modern web and desktop analytics, it processes raw punch logs, applies complex multi-shift rules, calculates overtime/grace periods/deductions, tracks leaves, and generates export-ready reports for HR payroll.

Available as both a **FastAPI-powered Web Application** and a **Standalone Windows Desktop Application** packaged with Electron.

---

## 🚀 Key Features

### 🕒 1. Biometric & Punch Log Ingestion
- Ingest raw biometric punch logs from devices (e.g., `attlog.dat` format) and Excel punch logs (`.xlsx`).
- Intelligent punch deduplication, pair matching (First-In, Last-Out, intermediate punches), and biometric ID mapping.
- Automated batch reprocessing via CLI scripts (`scripts/reimport_clean_data.py`).

### ⚙️ 2. Intelligent Shift Engine
- Pre-configured standard enterprise shifts:
  - **S1 (Morning Shift):** 06:00 – 14:00
  - **S2 (General Shift):** 09:00 – 17:00
  - **S3 (Evening Shift):** 14:00 – 22:00
  - **S4 (Night Shift - Overnight):** 22:00 – 06:00
- Dynamic shift assignment with tolerance windows, grace periods, and lunch break deductions.
- Automatic computation of **First Half**, **Second Half**, **Present**, **Late**, **Half-Day**, **Absent**, and **Overtime**.

### 👥 3. Employee Master Directory
- Complete employee profile management: ID, biometric device ID, name, designation, department, contact, and employment status.
- Direct Excel import (`Prumatech_Employee_Data.xlsx`) for bulk employee onboarding.

### 📊 4. Real-time Dashboard & HR Analytics
- Live KPIs: Present Today, Absent, Late Arrivals, On Leave, Overtime Hours.
- Department-wise attendance breakdowns and daily attendance trends.
- Activity audit logs tracking every change and login event.

### 📅 5. Daily & Monthly Attendance Registers
- Interactive monthly matrix view showing daily statuses for every employee across the month.
- Color-coded badges for Present, Absent, Half-Day, Week Off, and Leave.
- One-click export to **Microsoft Excel** and styled **PDF reports** generated with ReportLab.

### 🌴 6. Leave Management
- Built-in leave types (Casual Leave, Sick Leave, Earned Leave).
- Application, review, approval/rejection workflows with automatic leave balance tracking.

### 🔐 7. Role-Based Access Control (RBAC) & Audit Logs
- Pre-configured roles: **Admin** and **Clerk**.
- Password hashing with PBKDF2/cryptography and forced password updates on first login.
- Audit trail logging user actions, report exports, and data modifications.

---

## 🏗️ System Architecture & Folder Structure

```
d:/HRReport/
├── backend/                  # Python FastAPI REST API Backend
│   ├── app/
│   │   ├── api/              # API Route Controllers (auth, attendance, employees, leaves, reports, etc.)
│   │   ├── core/             # Database connection, security, default users & shifts seeding
│   │   ├── models/           # SQLAlchemy Database Models (Employee, Attendance, Shift, Leave, User, Audit)
│   │   ├── repositories/     # Data access layer
│   │   ├── schemas/          # Pydantic validation schemas
│   │   ├── services/         # Business logic & attendance calculation engine
│   │   └── main.py           # FastAPI Application Entrypoint
│   ├── migrations/           # Alembic database migrations
│   ├── tests/                # Pytest unit & integration test suite
│   ├── hrreport.db           # SQLite database (pre-initialized)
│   ├── requirements.txt      # Python dependencies
│   ├── run_server.py         # Uvicorn launcher script
│   └── start_backend.bat     # Backend startup script
├── frontend/                 # React 19 + Vite 8 + Tailwind CSS Desktop/Web Frontend
│   ├── electron/             # Electron desktop wrapper entrypoint (main.cjs)
│   ├── public/               # Static assets, branding logos, icons (.ico, .svg)
│   ├── src/
│   │   ├── api/              # Axios client and backend service integrations
│   │   ├── components/       # UI Components (Sidebar, Navbar, Tables, Modals, Badges)
│   │   ├── context/          # React Context (AuthContext, ThemeContext)
│   │   ├── pages/            # View pages (Dashboard, DailyAttendance, MonthlyReports, Employees, Leaves, etc.)
│   │   ├── App.jsx           # Routing & application shell
│   │   └── main.jsx          # React DOM entry
│   ├── package.json          # Node dependencies and build scripts
│   └── vite.config.js        # Vite build configuration
├── reports/                  # Generated PDF and Excel reports output directory
├── scripts/                  # Data maintenance scripts (reimport_clean_data.py)
├── test_data/                # Storage for test imports and sample logs
├── setup.bat                 # All-in-one automated installer & environment setup
├── start-all.bat             # Master launcher (Backend :8073 + Desktop / Web UI)
├── start-backend.bat         # Standalone backend launcher
├── start-frontend.bat        # Standalone frontend dev launcher
├── launch-window-app.bat     # Launches compiled desktop application
├── .gitignore                # Git exclusions (venv, node_modules, >100MB builds)
└── README.md                 # Project documentation
```

---

## ⚡ Quick Start Guide

### Option 1: Automated Setup (Recommended)
Double-click or run the master setup script:
```powershell
.\setup.bat
```
This script will:
1. Verify Python (3.10+) and Node.js (18+) installations.
2. Create `backend/venv` and install all Python requirements.
3. Initialize the database, shift tables, and default credentials.
4. Install npm packages in `frontend` and compile the frontend bundle.
5. Generate a desktop shortcut `Report Attendance.lnk` on your Desktop.

---

### Option 2: Run the System
After setup, run:
```powershell
.\start-all.bat
```
This starts:
- **Backend API**: `http://127.0.0.1:8073`
- **Interactive Swagger Docs**: `http://127.0.0.1:8073/docs`
- **Desktop Window / Frontend**: Automatically launches native desktop window or opens browser fallback.

---

### Option 3: Manual Execution

#### Backend:
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python run_server.py
```

#### Frontend:
```powershell
cd frontend
npm install
npm run dev
```

---

## 🔑 Default Credentials

| Username | Password | Role | Permissions |
| :--- | :--- | :--- | :--- |
| `admin` | `admin123` | **Administrator** | Full Access: System Settings, User Management, Shift Config, Reports |
| `clerk` | `clerk123` | **Attendance Clerk** | Standard Access: Attendance View, Daily Punch Import, Leave Requests |

*(Credentials can be modified in Settings or initialized in `backend/app/core/init_users.py`)*

---

## 📡 API Endpoints Summary

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `GET /` | `GET` | Health check & system status |
| `POST /api/auth/login` | `POST` | Authenticate user & issue session token |
| `GET /api/dashboard/stats` | `GET` | Today's attendance KPIs & summary statistics |
| `GET /api/employees` | `GET` | List all employees with department filters |
| `POST /api/employees` | `POST` | Create or onboard an employee |
| `GET /api/attendance/daily` | `GET` | Daily attendance log with shift evaluations |
| `POST /api/attendance/import` | `POST` | Upload biometric logs (`.dat` or `.xlsx`) |
| `GET /api/reports/monthly` | `GET` | Retrieve monthly aggregated attendance register |
| `POST /api/reports/export/excel` | `POST` | Export formatted attendance matrix to Excel |
| `POST /api/reports/export/pdf` | `POST` | Export high-resolution printable PDF report |
| `GET /api/shifts` | `GET` | Retrieve shift configurations (S1, S2, S3, S4) |
| `GET /api/leaves` | `GET` | Fetch leave requests and approval records |
| `GET /api/audit-logs` | `GET` | Retrieve audit and system security logs |

Interactive documentation is available at:
- **Swagger UI:** [http://127.0.0.1:8073/docs](http://127.0.0.1:8073/docs)
- **ReDoc:** [http://127.0.0.1:8073/redoc](http://127.0.0.1:8073/redoc)

---

## 📦 Desktop Packaging (.exe)

To build standalone Windows executables with Electron Builder:

```powershell
cd frontend

# Build Portable Windows Executable (.exe)
npm run build:exe

# Build Full Windows NSIS Setup Installer (.exe)
npm run build:setup

# Build All Variants
npm run build:all
```
Output binaries will be generated inside `frontend/dist_electron/`.

---

## 🛠️ Data Maintenance & Scripts

- **`scripts/reimport_clean_data.py`**:
  Cleans and recalculates punch logs against active shift definitions.
  ```powershell
  python scripts/reimport_clean_data.py
  ```
- **Included Sample Data Files**:
  - `6426160301474_attlog.dat`: Biometric punch data from hardware device.
  - `Bio_Lab_Punch_02-10-2026.xlsx`: Sample daily punch punch-in/out records.
  - `Prumatech_Employee_Data.xlsx`: Employee master dataset for bulk onboarding.

---

## 📄 License
This software is developed for internal enterprise attendance management and workforce intelligence. All rights reserved.
