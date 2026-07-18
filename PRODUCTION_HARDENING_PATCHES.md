# Production Hardening Patches - Execution Plan

## Status: ✅ Phase 1 Complete - Remaining patches for Antigravity execution

### ✅ Completed (by Cline)
1. **services/ai_engine.py** - Fixed fallback chain logic with proper call_order

### 🔄 High Priority - Security & Stability (for Antigravity to execute)

#### 2. Fix call_ai_json Gemini fallback JSON mode
**File**: `services/ai_engine.py`
**Change**: In `call_ai_json()`, replace the Gemini fallback call:
```python
# OLD:
result = _call_gemini(system_prompt, user_message, [], temperature)

# NEW:
result = _call_gemini_json(system_prompt, user_message, temperature)
```

Add new function `_call_gemini_json()`:
```python
def _call_gemini_json(
    system_prompt: str,
    user_message: str,
    temperature: float
) -> tuple:
    """Gọi Gemini với JSON response format"""
    if not GEMINI_API_KEY:
        return None
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    for model_name in GEMINI_MODELS:
        try:
            print(f"[AI] Đang gọi Gemini JSON ({model_name})...")
            response = client.models.generate_content(
                model=model_name,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=temperature
                )
            )
            if response and response.text:
                return response.text.strip(), model_name
        except Exception as e:
            print(f"[AI] Lỗi Gemini JSON ({model_name}): {e}")
    
    return None
```

#### 3. Upgrade Admin Password Hashing to PBKDF2
**Files**: `routers/admin.py`, `scripts/seed_admin.py`
**Add new helper module**: `services/password_hash.py`
```python
import hashlib
import os
import base64

def hash_password_pbkdf2(password: str, salt: bytes = None) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with salt"""
    if salt is None:
        salt = os.urandom(32)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return base64.b64encode(salt + pwd_hash).decode('ascii')

def verify_password(password: str, hash_str: str) -> bool:
    """Verify password against PBKDF2 or legacy SHA-256 hash"""
    # Try PBKDF2 first
    if len(hash_str) > 70:  # PBKDF2 base64 is longer
        try:
            decoded = base64.b64decode(hash_str.encode('ascii'))
            salt = decoded[:32]
            stored_hash = decoded[32:]
            new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            return new_hash == stored_hash
        except:
            pass
    
    # Fallback to legacy SHA-256
    legacy_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return hash_str == legacy_hash
```

Update `routers/admin.py` login to use new verify and auto-upgrade:
```python
from services.password_hash import verify_password, hash_password_pbkdf2

# In login_submit():
if admin and verify_password(password, admin.password_hash) and admin.is_active:
    # Auto-upgrade legacy hash
    if len(admin.password_hash) == 64:  # SHA-256 length
        admin.password_hash = hash_password_pbkdf2(password)
        db.commit()
    # ... rest of login logic
```

#### 4. Sanitize Upload Filenames
**File**: `routers/admin.py` and `routers/webhook.py`
**Add helper**:
```python
import re
import secrets

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md', '.srt'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def sanitize_filename(filename: str) -> str:
    """Sanitize uploaded filename to prevent path traversal"""
    # Get extension
    name, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    # Validate extension
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type {ext} not allowed")
    
    # Remove dangerous characters, keep only alphanumeric, dash, underscore
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)[:100]
    
    # Add random suffix to avoid collisions
    random_suffix = secrets.token_hex(4)
    return f"{safe_name}_{random_suffix}{ext}"
```

Use in upload handlers:
```python
safe_filename = sanitize_filename(file.filename)
temp_path = os.path.join(TEMP_DIR, safe_filename)
```

#### 5. Secure Download Endpoint
**File**: `main.py`
**Replace** the `/download/{file_id}` endpoint:
```python
import uuid
from pathlib import Path

@app.get("/download/{file_id}")
def download_file(file_id: str, db: Session = Depends(get_db)):
    """Tải file Word kết quả thông qua file_id bảo mật UUID"""
    # Validate UUID format
    try:
        uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")
    
    mapping = db.query(models.FileMapping).filter(models.FileMapping.file_id == file_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="File not found or expired")
    
    actual_filename = mapping.filename
    file_path = Path(OUTPUT_DIR) / actual_filename
    
    # Prevent path traversal
    if not file_path.resolve().is_relative_to(Path(OUTPUT_DIR).resolve()):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    print(f"[File Server] Tải file: {file_id} -> {actual_filename}")
    return FileResponse(
        str(file_path), 
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', 
        filename=actual_filename
    )
```

Update `services/document_creator.py` to use UUID:
```python
import uuid
file_id = str(uuid.uuid4())
```

#### 6. Enforce Webhook Security
**File**: `config.py`
Add validation:
```python
if ZALO_MODE == 'webhook' and not ZALO_WEBHOOK_SECRET:
    print("[WARNING] ZALO_WEBHOOK_SECRET not configured in production webhook mode!")
```

**File**: `routers/webhook.py`
Make secret check mandatory in production:
```python
# Remove the "if ZALO_WEBHOOK_SECRET:" check, make it required
if not ZALO_WEBHOOK_SECRET:
    print("[Webhook Security] ZALO_WEBHOOK_SECRET not configured - rejecting webhook")
    return JSONResponse(status_code=500, content={"status": "misconfigured"})

received_token = request.headers.get("X-Bot-Api-Secret-Token", "")
if received_token != ZALO_WEBHOOK_SECRET:
    print("[Webhook Security] Invalid Secret Token")
    return JSONResponse(status_code=403, content={"status": "forbidden"})
```

#### 7. Fix parse_docx to Extract Images
**File**: `services/knowledge_manager.py`
Replace `parse_docx()`:
```python
def parse_docx(file_path: str) -> tuple:
    """Trích xuất văn bản và ảnh từ DOCX"""
    from docx import Document as DocxDocument
    doc = DocxDocument(file_path)
    
    full_text = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
    raw_text = "\n".join(full_text)
    
    # Extract images
    image_mappings = _extract_docx_images(file_path)
    
    return raw_text, image_mappings
```

#### 8. Create Comprehensive Migration Script
**File**: `scripts/prod_migration.py` (new)
```python
"""Production migration: indexes, constraints, defaults"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import get_db_session, IS_POSTGRES
from config import EMBEDDING_DIMENSION

def run_production_migration():
    print("[Prod Migration] Starting production database migration...")
    db = get_db_session()
    
    try:
        if IS_POSTGRES:
            # GIN index for FTS
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chunks_text_fts 
                ON knowledge_chunks USING gin (to_tsvector('simple', text));
            """))
            print("[Prod Migration] ✓ GIN FTS index created")
            
            # B-tree indexes
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON knowledge_chunks (document_id);"))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_is_active ON documents (is_active);"))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs (created_at DESC);"))
            print("[Prod Migration] ✓ B-tree indexes created")
            
            # HNSW vector index (if dimension <= 2000)
            if EMBEDDING_DIMENSION <= 2000:
                db.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
                    ON knowledge_chunks
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                """))
                print(f"[Prod Migration] ✓ HNSW index created ({EMBEDDING_DIMENSION}D)")
            else:
                print(f"[Prod Migration] ⚠ Skipping HNSW (dimension {EMBEDDING_DIMENSION} > 2000)")
            
            db.commit()
            print("[Prod Migration] ✅ All migrations completed successfully")
        else:
            print("[Prod Migration] SQLite detected - skipping PostgreSQL-specific indexes")
    
    except Exception as e:
        print(f"[Prod Migration] ❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_production_migration()
```

#### 9. Add Concurrency Limits
**File**: `main.py`
Add at top after imports:
```python
import asyncio
from asyncio import Semaphore

# Semaphores to limit concurrent heavy operations
OCR_SEMAPHORE = Semaphore(2)  # Max 2 concurrent OCR
INGEST_SEMAPHORE = Semaphore(3)  # Max 3 concurrent ingestions
CHAT_SEMAPHORE = Semaphore(10)  # Max 10 concurrent chats
```

**File**: `routers/webhook.py`
Wrap heavy operations:
```python
from main import OCR_SEMAPHORE, INGEST_SEMAPHORE, CHAT_SEMAPHORE

async def _process_zalo_payload_async(payload: dict):
    # For OCR image processing
    async with OCR_SEMAPHORE:
        # ... OCR logic
    
    # For file ingestion
    async with INGEST_SEMAPHORE:
        # ... ingest logic
    
    # For chat Q&A
    async with CHAT_SEMAPHORE:
        # ... chat logic
```

#### 10. Update Admin Session Security
**File**: `routers/admin.py`
Update cookie settings:
```python
response.set_cookie(
    "admin_session", 
    session_id, 
    httponly=True, 
    secure=True,  # HTTPS only
    samesite='lax',  # CSRF protection
    max_age=28800  # 8 hours
)
```

### 📋 Deployment Checklist

1. ✅ Code changes applied
2. Update `.env` on VPS with strong secrets
3. Run `python scripts/prod_migration.py` after deploy
4. Verify HNSW index: `SELECT COUNT(*) FROM pg_indexes WHERE indexname = 'idx_chunks_embedding_hnsw';`
5. Test endpoints: `/health`, `/admin/login`, `/webhook/zalo`
6. Monitor logs for first 10 minutes

### 🚀 Deploy Command (for Antigravity)
```bash
# On VPS 45.119.82.227 as root
cd /root/Chatbot_AI
git stash --include-untracked
git pull --ff-only origin main
docker compose up --build -d
docker compose ps
docker compose logs --tail=50 web
docker exec chatbot-web python scripts/prod_migration.py
```
