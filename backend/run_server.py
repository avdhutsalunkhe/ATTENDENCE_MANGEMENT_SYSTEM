import uvicorn
import sys

if __name__ == "__main__":
    port = 8073
    host = "0.0.0.0"
    print(f"Starting Report Attendance Backend on {host}:{port} ...")
    print(f"Accessible via: http://182.66.233.66:{port} (if routed/forwarded)")
    print(f"Accessible locally via: http://127.0.0.1:{port} or http://192.168.1.93:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
