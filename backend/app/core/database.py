from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# For SQLite during dev. In production, load from env var like os.getenv("DATABASE_URL")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hrreport.db")

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
