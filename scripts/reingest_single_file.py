import os
import sys
import re

# Reconfigure encoding for console
sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from services.knowledge_manager import ingest_document

def reingest_single():
    db = SessionLocal()
    filename = "10_hdsd_quan_ly_van_ban_di.md"
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "HDSD_dhtn_markdown", filename)
    
    if not os.path.exists(file_path):
        print(f"[Error] File không tồn tại: {file_path}")
        return
        
    title = "HDSD QUAN LY VAN BAN DI"
    print(f"\n[Re-ingest] Chỉ cập nhật một tệp duy nhất để tránh Rate Limit: {filename}")
    try:
        result = ingest_document(
            file_path=file_path,
            title=title,
            category="Hướng dẫn điều hành tác nghiệp",
            description="Tài liệu hướng dẫn chi tiết quy trình quản lý văn bản đi.",
            created_by="system",
            status="active",
            db=db
        )
        print(f"[Re-ingest] Kết quả: {result}")
    except Exception as e:
        print(f"[Re-ingest] Lỗi: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reingest_single()
