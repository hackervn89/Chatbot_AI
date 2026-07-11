# 🗺️ MAPCODE - Bản Đồ Mã Nguồn Chi Tiết (Production Version)

> Tệp này lưu trữ kiến thức kỹ thuật chi tiết về toàn bộ codebase mới phục vụ triển khai chính thức. AI và developer có thể nhanh chóng hiểu và làm việc với dự án.

---

## 📐 Tổng Quan Kiến Trúc Hệ Thống

```
[Người dùng Zalo] (Text/Ảnh/File)
      │
      ▼ (HTTP POST Webhook)
  main.py (FastAPI Server) ──→ API Webhook /webhook/zalo
      │
      ├─→ [Lưu vào CSDL] (ChatHistory, FileMapping)
      │
      ├─→ [Q&A Flow - Q&A Nghiệp vụ]
      │         │
      │         ▼
      │   rag_engine.py (Hybrid Search) 
      │         ├─→ Dense: models/gemini-embedding-2 (3072 dims)
      │         ├─→ Sparse: Postgres Full-Text Search (simple)
      │         └─→ Kết hợp: Cosine Similarity + ts_rank
      │         │
      │         ▼ (Prompt + Context + ChatHistory)
      │   DeepSeek-V3 / Gemini Fallback
      │         │
      │         ▼ (Trích xuất ảnh minh họa từ CSDL image_mappings)
      │   Đính kèm link ảnh static / images/ -> Gửi tin Zalo
      │
      └─→ [Luồng Admin nạp tri thức - user_send_file]
                │
                ▼ (Tải file tạm)
          document_uploader.py (Background Task)
                ├─→ Parse PDF (pypdf) / SRT (clean text) / DOCX (python-docx)
                ├─→ Trích xuất ảnh minh họa tự động trong DOCX/PDF
                ├─→ Cắt chunks + Sinh vector embeddings 3072-dim
                └─→ Ghi nhận đồng bộ vào Database (documents, chunks, images)
```

---

## 📝 Chi Tiết Các Tệp Tin nguồn

### 1. `main.py` (FastAPI Server)
*   **Vai trò**: Cổng giao tiếp chính, nhận Webhook Zalo OA, phục vụ ảnh tĩnh minh họa và tải xuống file Word kết quả.
*   **Các Endpoint chính**:
    *   `GET /`: Health check trạng thái hoạt động.
    *   `GET /download/{file_id}`: Tải file Word kết quả. Tra cứu DB bảng `file_mappings` để lấy tên file thực tế (tăng độ bảo mật). Fallback tải trực tiếp.
    *   `POST /webhook/zalo`: Endpoint nhận sự kiện Zalo OA. Trả về `{"status": "received"}` ngay lập tức để tránh lặp tin nhắn và xử lý ngầm qua FastAPI `BackgroundTasks`.
*   **Background Threads**:
    *   `file_cleaner_task()`: Chạy định kỳ mỗi 1 giờ, tự động xóa các file Word cũ quá 24 giờ và dọn sạch DB mappings tương ứng.
    *   `run_zalo_polling()`: Chạy bot ở chế độ Polling (Development) nếu cấu hình `ZALO_MODE=polling`.

### 2. `zalo_bot.py` (Zalo Message Processor)
*   **Vai trò**: Xử lý logic nghiệp vụ tin nhắn Zalo, bóc tách ảnh chụp OCR bằng Gemini để soạn thảo công văn, và tích hợp Q&A RAG.
*   **Các Hàm chính**:
    *   `process_zalo_webhook_payload(payload)`: Parse JSON webhook, xác thực Admin qua Zalo ID để thực hiện nạp tài liệu tự động, hoặc điều phối tin nhắn text/image.
    *   `process_zalo_message(message)`: Xử lý OCR hình ảnh (Gemini Multimodal) để trích xuất 6 trường thông tin, gọi engine sinh Word, hoặc xử lý tin nhắn Q&A RAG.
    *   `ask_dhtn_qa(chat_id, question, db)`: Lấy lịch sử chat từ DB, gọi `hybrid_search`, build prompt RAG và gọi DeepSeek (fallback sang Gemini) để sinh câu trả lời.
    *   `save_file_mapping()`, `get_chat_history()`, `add_chat_message()`: Đọc ghi dữ liệu đồng bộ vào PostgreSQL/SQLite Database.

### 3. `database.py` (Database Connection)
*   **Vai trò**: Quản lý kết nối cơ sở dữ liệu.
*   **Cơ chế hoạt động**:
    *   Đọc `DATABASE_URL` từ tệp `.env`.
    *   **Fallback SQLite local**: Nếu không có cấu hình PostgreSQL, tự động chuyển sang sử dụng SQLite cục bộ tại thư mục tạm (`chatbot_local.db`), giúp lập trình viên chạy test và phát triển offline cực kỳ dễ dàng.

### 4. `models.py` (ORM Database Schemas)
*   **Vai trò**: Định nghĩa cấu trúc bảng CSDL sử dụng SQLAlchemy ORM.
*   **Các Bảng**:
    *   `Document`: Lưu nguồn tài liệu (ví dụ: `HDSD_Lịch họp_Mobile.docx`).
    *   `KnowledgeChunk`: Lưu các đoạn text tri thức và vector embeddings (`VECTOR(3072)` cho Postgres, fallback `JSON` cho SQLite).
    *   `ImageMapping`: Bản đồ Hình X -> Đường dẫn ảnh tĩnh để bot gửi minh họa.
    *   `ChatHistory`: Lịch sử chat theo Zalo ID.
    *   `FileMapping`: Mapping file Word sinh ra.

### 5. `rag_engine.py` (Hybrid Search Engine)
*   **Vai trò**: Thực hiện tìm kiếm lai giữa vector ngữ nghĩa và từ khóa.
*   **Các Hàm chính**:
    *   `get_embedding(text)`: Sinh vector embeddings 3072 chiều từ mô hình `models/gemini-embedding-2` của Gemini API.
    *   `hybrid_search(db, query, top_n)`:
        *   **PostgreSQL**: Thực hiện truy vấn kết hợp: Dense Score (1 - cosine distance của pgvector) + Sparse Score (`ts_rank_cd` full-text search đơn giản tiếng Việt). Kết hợp tỉ lệ trọng số `0.7 * Dense + 0.3 * Sparse`.
        *   **SQLite local**: Fallback về tìm kiếm từ khóa dùng `LIKE` trên SQL kết hợp tính điểm số trùng khớp trên Python.

### 6. `document_uploader.py` (Ingestion Pipeline)
*   **Vai trò**: Tự động parse và nạp tài liệu tri thức mới.
*   **Các Hàm chính**:
    *   `ingest_document_file(file_path, title)`: Điểm đầu vào chính. Tự động nhận diện định dạng (.pdf, .docx, .srt, .txt).
    *   `parse_docx_and_extract_images()`: Bóc tách text trong file Word, đồng thời giải nén zip, đọc cấu trúc XML để trích xuất ảnh minh họa đính kèm khớp với captions "Hình N", lưu vào đĩa cứng và map vào DB.
    *   `clean_srt()`: Làm sạch file srt của video (tẩy mốc thời gian, số thứ tự) để gộp thành văn bản tri thức.
    *   `chunk_text()`: Cắt text thành các khối nhỏ tối ưu ngữ cảnh.

### 7. `migrate_data.py` (Migration Script)
*   **Vai trò**: Script hỗ trợ di trú dữ liệu chunks từ file JSON cũ vào cơ sở dữ liệu mới (được chạy khi khởi chạy dự án lần đầu).
*   **Cơ chế hoạt động**: Gọi Gemini API theo lô (batch size 50) để sinh vector embeddings và lưu vào DB. Tự động fallback sinh từng phần nếu lô bị lỗi rate limit.

---

## 📊 Cấu Hình Cơ Sở Dữ Liệu PostgreSQL (docker/init.sql)
Bản SQL khởi tạo chứa các cấu hình quan trọng sau để tối ưu hóa RAG:
*   `CREATE EXTENSION IF NOT EXISTS vector;`: Kích hoạt extension pgvector.
*   **Chỉ mục HNSW**:
    ```sql
    CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON knowledge_chunks 
    USING hnsw (embedding vector_cosine_ops);
    ```
*   **Chỉ mục Full-Text Search**:
    ```sql
    CREATE INDEX IF NOT EXISTS idx_chunks_text_fts ON knowledge_chunks 
    USING gin (to_tsvector('simple', text));
    ```

---

## 🔄 Cấu Hình Biến Môi Trường (.env)

| Biến | Ý nghĩa | Mặc định | Ghi chú |
|---|---|---|---|
| `ZALO_API_TOKEN` | Token của Zalo Official Account | Không có | Bắt buộc |
| `GEMINI_API_KEY` | Google Gemini API Key | Không có | Bắt buộc (Embeddings & OCR) |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | Không có | Khuyên dùng (Mô hình Q&A chính) |
| `SERVER_DOMAIN` | Domain HTTPS của server | Không có | Khuyên dùng (Để tạo link tải ảnh/file) |
| `ADMIN_ZALO_IDS` | Danh sách Zalo ID của admin | Không có | Dùng để phân quyền nạp tri thức |
| `ZALO_MODE` | Chế độ chạy Zalo bot | `webhook` | `webhook` (Prod) hoặc `polling` (Dev) |
| `DATABASE_URL` | URL kết nối Database | SQLite local | Cấu hình trong docker-compose.yml |
