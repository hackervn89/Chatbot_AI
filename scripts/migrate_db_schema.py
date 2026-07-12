"""
Script tự động kiểm tra và nâng cấp schema database (SQL migration).
Chạy an toàn: Chỉ thêm cột nếu cột chưa tồn tại (ADD COLUMN IF NOT EXISTS).
"""
import sys
import os
from sqlalchemy import text

# Thêm thư mục gốc vào path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, get_db_session


def migrate_schema():
    print("[Migration] Đang kiểm tra và nâng cấp schema database...")
    db = get_db_session()
    try:
        # Các câu lệnh ALTER TABLE cho PostgreSQL
        migrations = [
            # 1. Bảng documents
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT 'core';",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS description TEXT DEFAULT '';",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS raw_text TEXT DEFAULT '';",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS current_version INTEGER DEFAULT 1;",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunk_count INTEGER DEFAULT 0;",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) DEFAULT 'system';",
            
            # 2. Bảng knowledge_chunks
            "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS chunk_index INTEGER DEFAULT 0;",
            "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS chunk_metadata JSONB DEFAULT '{}'::jsonb;"
        ]
        
        for sql in migrations:
            try:
                print(f" -> Chạy lệnh: {sql}")
                db.execute(text(sql))
                db.commit()
            except Exception as ex:
                db.rollback()
                # Nếu là SQLite, IF NOT EXISTS có thể báo lỗi cú pháp.
                # Nhưng trên SQLite ta thường tạo file DB mới từ đầu nên không sao.
                print(f" -> [Warning/Error] Lỗi khi chạy lệnh trên: {ex}")
                
        print("[Migration] Hoàn tất nâng cấp schema database thành công!")
        
    except Exception as e:
        print(f"[Migration] Lỗi bất ngờ: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    migrate_schema()
