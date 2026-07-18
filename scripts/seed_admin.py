"""
Tạo tài khoản admin mặc định và HNSW index cho pgvector.
Chạy một lần sau khi deploy: python scripts/seed_admin.py
"""
import sys
import os

# Thêm thư mục gốc vào path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.password_hash import hash_password_pbkdf2

from config import ADMIN_DEFAULT_USERNAME, ADMIN_DEFAULT_PASSWORD, IS_POSTGRES
from database import engine, get_db_session
from models import Base, AdminUser
from sqlalchemy import text


def seed_admin():
    """Tạo tài khoản admin mặc định nếu chưa có"""
    # Tạo tất cả bảng
    Base.metadata.create_all(bind=engine)
    print("[Seed] Đã tạo/xác nhận tất cả bảng database.")

    db = get_db_session()
    try:
        # Kiểm tra admin đã tồn tại chưa
        existing = db.query(AdminUser).filter(AdminUser.username == ADMIN_DEFAULT_USERNAME).first()
        if existing:
            print(f"[Seed] Admin '{ADMIN_DEFAULT_USERNAME}' đã tồn tại. Bỏ qua.")
        else:
            admin = AdminUser(
                username=ADMIN_DEFAULT_USERNAME,
                password_hash=hash_password_pbkdf2(ADMIN_DEFAULT_PASSWORD),
                display_name="Quản trị viên",
                is_active=True
            )
            db.add(admin)
            db.commit()
            print(f"[Seed] Đã tạo tài khoản admin: {ADMIN_DEFAULT_USERNAME} / {ADMIN_DEFAULT_PASSWORD}")

        # Tạo HNSW index cho pgvector (nếu PostgreSQL)
        if IS_POSTGRES:
            try:
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
                    ON knowledge_chunks
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                """))
                db.commit()
                print("[Seed] Đã tạo HNSW index trên knowledge_chunks.embedding.")
            except Exception as e:
                db.rollback()
                print(f"[Seed] Warning: Không thể tạo HNSW index: {e}")

    except Exception as e:
        db.rollback()
        print(f"[Seed] Lỗi: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
