"""
Database engine và session management.
Hỗ trợ PostgreSQL (production) và SQLite (development).
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DATABASE_URL, IS_POSTGRES

# Cấu hình engine kết nối
if IS_POSTGRES:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True
    )
else:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency cung cấp DB session cho FastAPI endpoints"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    """Tạo DB session thủ công cho services (không phải FastAPI dependency)"""
    return SessionLocal()
