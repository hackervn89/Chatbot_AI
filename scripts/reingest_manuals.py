import os
import sys
import time

# Reconfigure encoding for console
sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from services.knowledge_manager import ingest_document

def reingest_all():
    print("[Re-ingest] Bắt đầu đồng bộ hóa tài liệu từ thư mục HDSD_dhtn_markdown...")
    db = SessionLocal()
    
    hdsd_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "HDSD_dhtn_markdown")
    if not os.path.exists(hdsd_dir):
        print(f"[Error] Thư mục không tồn tại: {hdsd_dir}")
        return
        
    files = [f for f in os.listdir(hdsd_dir) if f.endswith('.md') and f != 'hdsd-tichhop-tri-thuc-rag.md']
    files.sort()
    
    for filename in files:
        file_path = os.path.join(hdsd_dir, filename)
        title = filename.replace('_', ' ').replace('.md', '')
        # Loại bỏ tiền tố số (ví dụ: '10 hdsd quan ly van ban di' -> 'hdsd quan ly van ban di')
        title = re.sub(r'^\d+\s+', '', title).upper()
        
        print(f"\n[Re-ingest] Đang cập nhật tệp: {filename} (Tiêu đề: {title})")
        try:
            result = ingest_document(
                file_path=file_path,
                title=title,
                category="Hướng dẫn điều hành tác nghiệp",
                description=f"Tài liệu hướng dẫn chi tiết quy trình {title.lower()}.",
                created_by="system",
                status="active",
                db=db
            )
            print(f"[Re-ingest] Kết quả: {result}")
        except Exception as e:
            print(f"[Re-ingest] Lỗi khi nạp file {filename}: {e}")
        
        # Thêm khoảng nghỉ 35 giây giữa các tệp để đảm bảo không bị dính rate limit RPM
        print("[Re-ingest] Nghỉ 35 giây để reset hoàn toàn cửa sổ giới hạn cuộc gọi API...")
        time.sleep(35.0)
            
    db.close()
    print("\n[Re-ingest] Đồng bộ hóa hoàn tất!")

if __name__ == "__main__":
    import re
    reingest_all()
