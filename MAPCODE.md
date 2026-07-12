# 🗺️ MAPCODE - Bản Đồ Mã Nguồn Chi Tiết (Production Release 2026)

> Tệp này lưu trữ cấu trúc thư mục chi tiết, thiết kế API, sơ đồ cơ sở dữ liệu và các module chức năng của dự án Chuyên Viên Ảo. Dành cho các kỹ sư phát triển và hệ thống để bảo trì, tối ưu hóa hoặc mở rộng dự án.

---

## 📐 1. Tổng Quan Kiến Trúc Hệ Thống

```
                    [Người dùng Zalo OA]
                              │
                              ▼ (HTTP POST Webhook)
            FastAPI Server (main.py + routers/webhook.py)
                              │
       ┌──────────────────────┴──────────────────────┐
       ▼ (BackgroundTasks)                           ▼ (BackgroundTasks)
[Luồng Q&A Nghiệp vụ & ĐHTN]               [Luồng Nạp Tri Thức & Soạn Thảo]
       │                                             │
       ▼                                             ▼
services/rag_pipeline.py                     services/knowledge_manager.py
  ├─ Dense: pgvector (Gemini 768-dim)          ├─ Parser: pypdf, python-docx, srt
  ├─ Sparse: Postgres FTS (Simple parser)      ├─ Bóc tách ảnh minh họa thao tác
  └─ Merge: RRF (scale 1200)                   └─ Batch Embedding (gemini-embed)
       │                                             │
       ▼ (Prompt + Context)                          ▼
services/ai_engine.py                        services/document_creator.py
  ├─ Primary: DeepSeek-Chat                    ├─ Điền template cong_van_mau.docx
  └─ Fallback: Gemini (2.5/2.0/1.5)            ├─ Áp dụng quy tắc gộp/recipient
       │                                       └─ Lưu file output & FileMapping DB
       ▼                                             │
Gửi Zalo text kèm link ảnh minh họa                 Gửi link tải /download/{file_id}
```

---

## 📁 2. Chi Tiết Các Tệp Tin Trong Codebase

### 🌐 Cổng Giao Tiếp API & Máy Chủ
*   **[main.py](file:///g:/My%20Drive/Chuyên%20viên%20ảo/main.py)**:
    *   Khởi tạo ứng dụng FastAPI và tự động gọi `models.Base.metadata.create_all` để khởi tạo cấu trúc CSDL PostgreSQL/SQLite.
    *   Phục vụ tệp tĩnh (`/static` cho CSS/JS giao diện và `/images` cho ảnh minh họa nghiệp vụ trích xuất từ tài liệu).
    *   Endpoint `GET /download/{file_id}`: Tra cứu bảng `file_mappings` để lấy tên file thực tế và gửi về cho người dùng tải xuống một cách bảo mật.
    *   Background Daemon Thread `file_cleaner_task()`: Chạy định kỳ mỗi 1 giờ để quét và xóa sạch các file Word kết quả cũ hơn 24 giờ trên ổ cứng, đồng thời giải phóng mapping trong DB.
*   **[routers/webhook.py](file:///g:/My%20Drive/Chuyên%20viên%20ảo/routers/webhook.py)**:
    *   Endpoint Webhook Zalo OA (`POST /webhook/zalo`) nhận sự kiện từ Zalo Server. Trả về status `200 OK` ngay lập tức để tránh Zalo gửi lặp tin nhắn khi chờ AI phản hồi.
    *   Sử dụng FastAPI `BackgroundTasks` để chuyển tiếp payload xử lý bất đồng bộ ngầm:
        *   `user_send_file`: Admin gửi file mới (`.pdf`, `.docx`, `.srt`) để nạp tri thức.
        *   `user_send_image`: Gửi ảnh văn bản chỉ đạo cấp trên để chạy OCR sinh công văn giao việc.
        *   `user_send_text`: Hỏi đáp nghiệp vụ (Q&A RAG).
*   **[routers/admin.py](file:///g:/My%20Drive/Chuyên%20viên%20ảo/routers/admin.py)**:
    *   Chứa toàn bộ logic render HTML của **Admin Dashboard** sử dụng `Jinja2Templates` (tương thích hoàn toàn với Starlette 0.28+ bằng cách sử dụng tham số tường minh `request`, `name`, `context`).
    *   Trang Dashboard (`/admin/dashboard`): Thống kê hệ thống, danh sách phiên chat và log hoạt động gần đây.
    *   Quản lý tài liệu (`/admin/documents`): CRUD tài liệu, upload tệp trực tiếp, xem chi tiết và lịch sử các phiên bản sửa đổi.
    *   Nhật ký giám sát (`/admin/audit`): Truy vết chi tiết các thao tác của quản trị viên và phiên chat.

### 🛠️ Lõi Dịch Vụ Hệ Thống (services/)
*   **[services/rag_pipeline.py](file:///g:/My%20Drive/Chuyên%20viên%20ảo/services/rag_pipeline.py)**:
    *   `get_embedding(text)`: Sinh vector embeddings cho một đoạn văn bản.
    *   `get_embeddings_batch(texts)`: Sinh vector cho danh sách văn bản theo lô (tối đa 50 phần tử) để chống rate limit 429 và tăng tốc nạp tri thức lên 50x.
    *   `semantic_chunk(text)`: Phân đoạn văn bản ngữ nghĩa dựa vào heading Markdown (`#`, `##`, `###`) và dòng trống, cấu hình overlap 150 ký tự giữ ngữ cảnh.
    *   `_prepare_tsquery(query)`: Tiền xử lý tiếng Việt cho Postgres FTS, tự động loại bỏ stop-words nghiệp vụ và nối bằng toán tử `OR` (`|`).
    *   `_postgres_hybrid_search(db, query)`: Tìm kiếm lai pgvector + FTS. Sắp xếp và xếp hạng kết quả bằng **Reciprocal Rank Fusion (RRF)**. Điểm số RRF được nhân với **1200** để đồng bộ với thang điểm cũ.
*   **[services/ai_engine.py](file:///g:/My%20Drive/Chuyên%20viên%20ảo/services/ai_engine.py)**:
    *   `call_ai(system_prompt, user_message, history)`: Định tuyến cuộc gọi AI.
    *   **Fallback Chain**: Thử gọi DeepSeek API (`deepseek-chat`) trước với timeout cấu hình 30s. Nếu DeepSeek quá tải/lỗi kết nối, hệ thống tự động chuyển sang gọi Gemini API (`gemini-2.5-flash` -> `gemini-2.0-flash` -> `gemini-1.5-pro`) làm dự phòng.
    *   `call_gemini_with_grounding()`: Gọi Gemini tích hợp Google Search Grounding cho các thông tin thời gian thực.
*   **[services/knowledge_manager.py](file:///g:/My%20Drive/Chuyên%20viên%20ảo/services/knowledge_manager.py)**:
    *   Bộ lọc định dạng file: `parse_pdf` sử dụng `pypdf`, `parse_docx` sử dụng `docx`, `parse_srt` tẩy mốc thời gian phụ đề.
    *   `_extract_docx_images()`: Giải nén tệp DOCX, phân tích file quan hệ XML `document.xml.rels` để bóc tách ảnh chụp màn hình gốc và lưu lại dưới dạng bản đồ hình ảnh `ImageMapping`.
    *   `ingest_document()`: Nhận diện file, cắt chunks ngữ nghĩa, tạo batch embedding (768 chiều) và lưu đồng bộ vào database.
*   **[services/document_creator.py](file:///g:/My%20Drive/Chuyên%20viên%20ảo/services/document_creator.py)**:
    *   Tiến hành phân vai giao việc cho 5 cơ quan cấp xã dựa trên từ khóa nhận diện trong `taovanban_khoidang/SKILL.md`.
    *   Áp dụng các quy tắc hành chính Đảng: Quy tắc gộp nhiệm vụ đặc thù (Ban Xây dựng Đảng) và Quy tắc kính gửi tối giản (chỉ hiển thị các ban ngành thực sự được giao nhiệm vụ).
    *   Mở tệp mẫu `cong_van_giao_viec_mau.docx` và điền dữ liệu vào các thẻ biến `{{...}}` thông qua thư viện `python-docx`.
*   **[services/zalo_api.py](file:///g:/My%20Drive/Chuyên%20viên%20ảo/services/zalo_api.py)**:
    *   `clean_markdown_for_zalo(text)`: Zalo OA không hỗ trợ cú pháp Markdown thô. Hàm này loại bỏ dấu in đậm `**` và chuyển Markdown links `[Hình 1](url)` thành văn bản thuần kèm link thô để Zalo tự tạo liên kết click được (`Hình 1: url`).
    *   `send_zalo_message(user_id, text)`: Tự động chia nhỏ tin nhắn và gửi làm nhiều phần nếu độ dài câu trả lời của AI vượt quá giới hạn **2000 ký tự** của Zalo.

---

## 🗄️ 3. Mô Hình Dữ Liệu Chi Tiết (models.py)

Bảng chi tiết các SQLAlchemy ORM Models và mối liên kết quan hệ:

| Tên Bảng | Class Name | Vai trò | Các trường chính |
|---|---|---|---|
| `documents` | `Document` | Lưu trữ tài liệu tri thức nguồn | `id`, `title`, `source`, `category`, `raw_text`, `is_active`, `current_version` |
| `document_versions` | `DocumentVersion` | Lịch sử phiên bản của từng tài liệu | `id`, `document_id`, `version`, `raw_text`, `change_summary`, `changed_by` |
| `knowledge_chunks` | `KnowledgeChunk` | Lưu các đoạn văn và vector tương ứng | `id`, `document_id`, `chunk_index`, `text`, `embedding` (768 dims), `chunk_metadata` |
| `image_mappings` | `ImageMapping` | Bản đồ khớp hình ảnh minh họa | `id`, `document_id`, `hinh_key` (Hình N), `img_rel_path` |
| `chat_sessions` | `ChatSession` | Quản lý phiên hội thoại của người dùng | `id`, `platform` (zalo, telegram), `external_chat_id`, `user_display_name` |
| `chat_messages` | `ChatMessage` | Lưu chi tiết từng tin nhắn chat | `id`, `session_id`, `role`, `content`, `ai_model_used`, `rag_score`, `response_time_ms` |
| `audit_logs` | `AuditLog` | Nhật ký giám sát thay đổi hệ thống | `id`, `entity_type`, `action`, `actor`, `details` (JSON), `ip_address` |
| `file_mappings` | `FileMapping` | Bản đồ tải xuống file Word bảo mật | `id`, `file_id` (UUID), `filename` |

---

## ⚙️ 4. Cấu Hình Biến Môi Trường (.env)

| Biến môi trường | Vai trò | Giá trị mặc định / Khuyên dùng |
|---|---|---|
| `DATABASE_URL` | Đường dẫn kết nối CSDL PostgreSQL hoặc SQLite local | `postgresql://chatbot_user:chatbot_password_secure_2026@db:5432/chatbot_db` |
| `GEMINI_API_KEY` | Google AI Studio Key dùng cho Embeddings & OCR | *Bắt buộc* |
| `DEEPSEEK_API_KEY` | DeepSeek Key dùng làm AI phản hồi chính | *Bắt buộc* |
| `AI_PRIMARY_ENGINE`| Động cơ AI chính được ưu tiên | `deepseek` |
| `DEEPSEEK_TIMEOUT` | Thời gian ngắt kết nối DeepSeek chờ phản hồi | `30` (giây) |
| `ZALO_API_TOKEN` | Token kết nối Zalo Official Account | *Bắt buộc* |
| `ZALO_MODE` | Chế độ lắng nghe Zalo Bot | `webhook` (chạy Production) |
| `SERVER_DOMAIN` | Tên miền HTTPS của hệ thống | `https://bot.conghaiso.vn` |
| `ADMIN_ZALO_IDS` | Danh sách Zalo ID của admin được phép nạp tri thức | Ngăn cách bằng dấu phẩy |
