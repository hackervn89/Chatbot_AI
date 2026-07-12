"""
Script nạp tri thức mặc định (seeding) từ file SRT có sẵn trong dự án.
Chạy sau khi triển khai: python scripts/seed_knowledge.py
"""
import sys
import os

# Thêm thư mục gốc vào path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_session
from services.knowledge_manager import ingest_document


def seed_kb():
    print("[Seed KB] Bắt đầu nạp tài liệu tri thức nghiệp vụ mặc định...")
    
    # Đường dẫn file SRT nghiệp vụ
    srt_filename = "Hội nghị triển khai phần mềm Điều hành tác nghiệp của các cơ quan đảng_part1.srt"
    srt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), srt_filename)
    
    if not os.path.exists(srt_path):
        print(f"[Seed KB] Lỗi: Không tìm thấy file {srt_path}")
        return
        
    db = get_db_session()
    try:
        result = ingest_document(
            file_path=srt_path,
            title="Hướng dẫn sử dụng phần mềm Điều hành tác nghiệp (ĐHTN) Đảng",
            category="core",
            description="Tài liệu ghi chép nội dung hội nghị tập huấn, hướng dẫn các thao tác tạo dự thảo, xử lý văn bản đi/đến trên hệ thống ĐHTN Đảng.",
            created_by="system",
            db=db
        )
        print(f"[Seed KB] Kết quả: {result}")
    except Exception as e:
        print(f"[Seed KB] Gặp lỗi khi nạp tài liệu: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_kb()
