import os
import sys
import json
import time
from sqlalchemy.orm import Session
from google import genai
from database import engine, SessionLocal, IS_POSTGRES
import models

sys.stdout.reconfigure(encoding='utf-8')

# Define custom dotenv loader to read .env file safely
def load_dotenv():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(script_dir, '.env')
    if os.path.exists(dotenv_path):
        with open(dotenv_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    os.environ[key] = val

load_dotenv()

# Đọc API Key từ môi trường
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("[!] ERROR: Vui lòng cấu hình GEMINI_API_KEY trong môi trường hoặc file .env trước khi chạy di trú.")
    sys.exit(1)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(PROJECT_ROOT, "taovanban_khoidang", "references", "hdsd_chunks.json")
IMAGE_MAP_PATH = os.path.join(PROJECT_ROOT, "taovanban_khoidang", "output", "images", "image_map.json")

def create_tables_if_not_exists():
    print("[*] Đang khởi tạo các bảng cơ sở dữ liệu...")
    models.Base.metadata.create_all(bind=engine)
    print("[+] Khởi tạo bảng thành công.")

def embed_batch(client, texts):
    """Tạo vector embeddings theo lô (batch) 768 chiều (tương thích pgvector index)"""
    try:
        response = client.models.embed_content(
            model="models/gemini-embedding-2",
            contents=texts,
            config={"output_dimensionality": 768}
        )
        return [e.values for e in response.embeddings]
    except Exception as e:
        print(f"[!] Lỗi gọi Gemini Embed API: {e}")
        # Fallback từng phần
        vectors = []
        for t in texts:
            try:
                res = client.models.embed_content(
                    model="models/gemini-embedding-2", 
                    contents=t,
                    config={"output_dimensionality": 768}
                )
                vectors.append(res.embeddings[0].values)
                time.sleep(0.1)
            except Exception as ex:
                print(f"[!] Lỗi embedding chunk đơn lẻ: {ex}")
                vectors.append([0.0] * 768)
        return vectors

def migrate():
    create_tables_if_not_exists()
    
    db: Session = SessionLocal()
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 1. Đọc dữ liệu chunks hiện tại
    if not os.path.exists(CHUNKS_PATH):
        print(f"[!] ERROR: Không tìm thấy file {CHUNKS_PATH}")
        db.close()
        return
        
    with open(CHUNKS_PATH, 'r', encoding='utf-8') as f:
        chunks_data = json.load(f)
        
    print(f"[*] Đang xử lý di trú {len(chunks_data)} chunks...")
    
    # Xóa sạch các chunks cũ trong database để nạp lại chuẩn 768 chiều
    print("[*] Đang dọn sạch bảng chunks cũ...")
    db.query(models.KnowledgeChunk).delete()
    db.commit()
    
    # Gom nhóm chunks theo source để tạo Document + raw_text gộp
    source_to_doc_id = {}
    source_texts = {}
    
    for c in chunks_data:
        src = c['source']
        if src not in source_texts:
            source_texts[src] = []
        source_texts[src].append(c['text'])
        
    print(f"[*] Tổng cộng có {len(source_texts)} tài liệu độc bản cần xử lý.")
    
    for src, text_list in source_texts.items():
        raw_text = "\n\n".join(text_list)
        title = os.path.basename(src).replace('.docx', '').replace('_', ' ')
        
        doc = db.query(models.Document).filter(models.Document.source == src).first()
        if not doc:
            doc = models.Document(
                title=title,
                source=src,
                category="core",
                file_type="docx",
                raw_text=raw_text,
                status="active"
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
        else:
            doc.raw_text = raw_text
            doc.file_type = "docx"
            doc.status = "active"
            db.commit()
            
        source_to_doc_id[src] = doc.id

    # Tiến hành embed và lưu chunk vào database theo lô (50 chunks mỗi lô)
    batch_size = 50
    inserted_chunks = 0
    
    for i in range(0, len(chunks_data), batch_size):
        batch = chunks_data[i:i+batch_size]
        texts = [c['text'] for c in batch]
        
        print(f"  -> Đang sinh vector 768-dim cho chunks {i+1} đến {i+len(batch)}...")
        vectors = embed_batch(client, texts)
        
        # Nếu số lượng vector trả về không khớp, thực hiện sinh đơn lẻ từng phần
        if len(vectors) != len(texts):
            print(f"  [!] Phát hiện số lượng vector ({len(vectors)}) không khớp với chunks ({len(texts)}). Chuyển sang sinh đơn lẻ...")
            vectors = []
            for t in texts:
                try:
                    res = client.models.embed_content(
                        model="models/gemini-embedding-2", 
                        contents=t,
                        config={"output_dimensionality": 768}
                    )
                    vectors.append(res.embeddings[0].values)
                except Exception as ex:
                    print(f"    [!] Lỗi embedding chunk đơn lẻ: {ex}")
                    vectors.append([0.0] * 768)
                time.sleep(0.1)
        
        for idx, c in enumerate(batch):
            doc_id = source_to_doc_id[c['source']]
            vector = vectors[idx]
            
            chunk_obj = models.KnowledgeChunk(
                document_id=doc_id,
                chunk_index=idx,
                text=c['text'],
                embedding=vector
            )
            db.add(chunk_obj)
            inserted_chunks += 1
            
        db.commit()
        
        # Cập nhật số chunk tương ứng cho Document
        for src in unique_sources_in_batch(batch):
            doc_id = source_to_doc_id[src]
            cnt = db.query(models.KnowledgeChunk).filter(models.KnowledgeChunk.document_id == doc_id).count()
            doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
            if doc:
                doc.chunk_count = cnt
        db.commit()
        
        time.sleep(1.0) # Tránh rate limit của Gemini API
        
    print(f"[+] Hoàn thành lưu {inserted_chunks} chunks tri thức vào DB.")
    
    # 2. Đọc và di trú image_map.json
    if os.path.exists(IMAGE_MAP_PATH):
        print("[*] Đang di trú bản đồ hình ảnh...")
        with open(IMAGE_MAP_PATH, 'r', encoding='utf-8') as f:
            image_map_data = json.load(f)
            
        inserted_images = 0
        for src, mappings in image_map_data.items():
            if src not in source_to_doc_id:
                doc = db.query(models.Document).filter(models.Document.source == src).first()
                if not doc:
                    title = os.path.basename(src).replace('.docx', '').replace('_', ' ')
                    doc = models.Document(title=title, source=src, status="active")
                    db.add(doc)
                    db.commit()
                    db.refresh(doc)
                source_to_doc_id[src] = doc.id
                
            doc_id = source_to_doc_id[src]
            
            for hinh_key, img_rel_path in mappings.items():
                img_map = db.query(models.ImageMapping).filter(
                    models.ImageMapping.document_id == doc_id,
                    models.ImageMapping.hinh_key == hinh_key
                ).first()
                
                if not img_map:
                    img_map = models.ImageMapping(
                        document_id=doc_id,
                        hinh_key=hinh_key,
                        img_rel_path=img_rel_path
                    )
                    db.add(img_map)
                    inserted_images += 1
                    
        db.commit()
        print(f"[+] Hoàn thành di trú {inserted_images} mappings hình ảnh.")
    else:
        print("[!] Không tìm thấy file image_map.json để di trú.")
        
    db.close()
    print("[+] QUÁ TRÌNH DI TRÚ HOÀN TẤT THÀNH CÔNG!")

def unique_sources_in_batch(batch):
    return set(c['source'] for c in batch)

if __name__ == "__main__":
    migrate()
