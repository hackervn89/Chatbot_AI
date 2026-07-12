import os
import sys
import time
import threading
import subprocess
from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from config import (
    OUTPUT_DIR, TEMP_DIR, IMAGES_DIR, STATIC_DIR, SERVER_PORT, ZALO_MODE
)
from database import engine, get_db, SessionLocal
import models
from routers import webhook, admin

# Cấu hình encoding UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

app = FastAPI(title="Chuyên Viên Ảo FastAPI Server", version="3.0.0")

# Khởi tạo các bảng database nếu chưa tồn tại
models.Base.metadata.create_all(bind=engine)

# Phục vụ file tĩnh
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# Đăng ký các routers mới
app.include_router(webhook.router)
app.include_router(admin.router)

@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Chuyên Viên Ảo Server is running on FastAPI! Zalo Bot & Admin Dashboard đang hoạt động.",
        "version": "3.0.0"
    }

@app.get("/download/{file_id}")
def download_file(file_id: str, db: Session = Depends(get_db)):
    """Tải file Word kết quả thông qua file_id bảo mật lưu trong DB"""
    mapping = db.query(models.FileMapping).filter(models.FileMapping.file_id == file_id).first()
    if mapping:
        actual_filename = mapping.filename
        file_path = os.path.join(OUTPUT_DIR, actual_filename)
        if os.path.exists(file_path):
            print(f"[File Server] Đang tải file (DB Mapping): {file_id} -> {actual_filename}")
            return FileResponse(
                file_path, 
                media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', 
                filename=actual_filename
            )
            
    # Fallback: Thử tìm trực tiếp tên file trong thư mục output (tương thích ngược)
    file_path = os.path.join(OUTPUT_DIR, file_id)
    if os.path.exists(file_path):
        print(f"[File Server] Đang tải file trực tiếp: {file_id}")
        return FileResponse(file_path)
        
    raise HTTPException(status_code=404, detail="File không tồn tại hoặc đã hết hạn tải xuống.")

def file_cleaner_task():
    """Background Daemon Thread dọn dẹp các tệp cũ > 24h và DB mapping hết hạn"""
    print("[Cleaner] File Cleaner daemon started...")
    while True:
        try:
            db: Session = SessionLocal()
            now = time.time()
            cutoff = now - 24 * 3600 # 24 giờ trước
            
            deleted_files = []
            
            # 1. Dọn dẹp các tệp Word vật lý quá 24h
            if os.path.exists(OUTPUT_DIR):
                for filename in os.listdir(OUTPUT_DIR):
                    if filename == "images":
                        continue
                    file_path = os.path.join(OUTPUT_DIR, filename)
                    if os.path.isfile(file_path):
                        mtime = os.path.getmtime(file_path)
                        if mtime < cutoff:
                            os.remove(file_path)
                            deleted_files.append(filename)
                            print(f"[Cleaner] Đã xóa file cũ: {filename}")
            
            # 2. Xóa các bản ghi FileMapping trong DB tương ứng với các file đã bị xóa
            if deleted_files:
                db.query(models.FileMapping).filter(models.FileMapping.filename.in_(deleted_files)).delete(synchronize_session=False)
                db.commit()
                print(f"[Cleaner] Đã dọn dẹp các mapping DB hết hạn.")
                
            db.close()
        except Exception as e:
            print(f"[Cleaner Error] Lỗi dọn dẹp định kỳ: {e}")
            
        # Chạy dọn dẹp mỗi 1 giờ
        time.sleep(3600)

def run_zalo_polling():
    """Chạy Zalo Bot ở chế độ Polling (chỉ dùng khi test cục bộ/development)"""
    if ZALO_MODE == 'polling':
        print("[Zalo Polling] Đang khởi chạy Zalo Bot ở chế độ Polling (Development)...")
        # Chạy zalo_bot.py dưới dạng tiến trình độc lập
        subprocess.run([sys.executable, "zalo_bot.py"])
    else:
        print("[Zalo Webhook] Đang sử dụng chế độ Webhook (Production). Không chạy polling.")

if __name__ == "__main__":
    import uvicorn
    
    # 1. Khởi chạy Thread dọn dẹp file cũ
    t_cleaner = threading.Thread(target=file_cleaner_task, name="CleanerThread", daemon=True)
    t_cleaner.start()
    
    # 2. Khởi chạy Thread Zalo Polling nếu cần thiết (chỉ phục vụ test local)
    t_zalo = threading.Thread(target=run_zalo_polling, name="ZaloPollingThread", daemon=True)
    t_zalo.start()
    
    # 3. Chạy web server FastAPI
    print(f"[Server] FastAPI Server đang khởi chạy trên port {SERVER_PORT}...")
    uvicorn.run("main:app", host="0.0.0.0", port=SERVER_PORT, reload=False)
