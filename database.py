import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Lấy DATABASE_URL từ môi trường, mặc định sử dụng SQLite cục bộ làm fallback
DATABASE_URL = os.environ.get(
    'DATABASE_URL', 
    'sqlite:///g:/My Drive/Chuyên viên ảo/taovanban_khoidang/scripts/temp/chatbot_local.db'
)

# Kiểm tra xem có đang sử dụng PostgreSQL hay không
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

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
    # Cấu hình riêng cho SQLite (yêu cầu thread-safe)
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency cung cấp DB session cho FastAPI và các bot"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
