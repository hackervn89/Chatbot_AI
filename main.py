import os
import sys
import time
import json
import threading
import subprocess
from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from database import engine, get_db, SessionLocal
import models

# Cấu hình encoding UTF-8
sys.stdout.reconfigure(encoding='utf-8')

app = FastAPI(title="Chuyên Viên Ảo FastAPI Server", version="2.0.0")

# Đường dẫn thư mục dự án
script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(script_dir) == "scripts":
    PROJECT_ROOT = os.path.dirname(script_dir)
else:
    PROJECT_ROOT = os.path.join(script_dir, "taovanban_khoidang")
    
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
TEMP_DIR = os.path.join(PROJECT_ROOT, "scripts", "temp")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")

# Tạo thư mục nếu chưa có
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# Khởi tạo các bảng database nếu chưa tồn tại
models.Base.metadata.create_all(bind=engine)

# Phục vụ file tĩnh (ảnh screenshot hướng dẫn)
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Chuyên Viên Ảo Server is running on FastAPI! Zalo Bot đang hoạt động.",
        "version": "2.0.0"
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

@app.post("/webhook/zalo")
async def zalo_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook tiếp nhận tin nhắn từ Zalo Official Account.
    Trả về HTTP 200 ngay lập tức trong vòng 2 giây và xử lý ngầm (background task) để tránh lặp tin nhắn.
    """
    try:
        payload = await request.json()
        
        # Nhập import động để tránh lỗi vòng lặp import (circular import)
        from zalo_bot import process_zalo_webhook_payload
        
        # Đẩy luồng xử lý tin nhắn vào Background Tasks của FastAPI
        background_tasks.add_task(process_zalo_webhook_payload, payload)
        
        return {"status": "received"}
    except Exception as e:
        print(f"[Webhook Error] Lỗi tiếp nhận Zalo Webhook: {e}")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

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
    zalo_mode = os.environ.get('ZALO_MODE', 'polling').lower()
    if zalo_mode == 'polling':
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
    port = int(os.environ.get("PORT", 8080))
    print(f"[Server] FastAPI Server đang khởi chạy trên port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
