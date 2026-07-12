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
    db = get_db_session()
    
    # 1. Nạp file MD nghiệp vụ tiếng Việt (Quan trọng nhất)
    md_filename = "taovanban_khoidang/references/kienthuc_dhtn.md"
    md_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), md_filename)
    
    if os.path.exists(md_path):
        try:
            print(f"[Seed KB] Nạp file tri thức tiếng Việt: {md_filename}")
            result = ingest_document(
                file_path=md_path,
                title="Quy trình nghiệp vụ ĐHTN và Soạn thảo văn bản Khối Đảng",
                category="core",
                description="Tài liệu nghiệp vụ chi tiết hướng dẫn soạn thảo công văn, tạo dự thảo văn bản đi trên hệ thống Điều hành tác nghiệp.",
                created_by="system",
                db=db
            )
            print(f"[Seed KB] Kết quả nạp file MD: {result}")
        except Exception as e:
            print(f"[Seed KB] Lỗi nạp file MD: {e}")
    else:
        print(f"[Seed KB] Lỗi: Không tìm thấy file {md_path}")

    # 2. Nạp file SRT nghiệp vụ
    srt_filename = "Hội nghị triển khai phần mềm Điều hành tác nghiệp của các cơ quan đảng_part1.srt"
    srt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), srt_filename)
    
    if os.path.exists(srt_path):
        try:
            print(f"[Seed KB] Nạp file phụ đề SRT: {srt_filename}")
            result = ingest_document(
                file_path=srt_path,
                title="Hướng dẫn sử dụng phần mềm Điều hành tác nghiệp (ĐHTN) Đảng (Sub)",
                category="core",
                description="Tài liệu phụ đề ghi chép hội nghị tập huấn.",
                created_by="system",
                db=db
            )
            print(f"[Seed KB] Kết quả nạp file SRT: {result}")
        except Exception as e:
            print(f"[Seed KB] Lỗi nạp file SRT: {e}")
            
    db.close()


if __name__ == "__main__":
    seed_kb()
