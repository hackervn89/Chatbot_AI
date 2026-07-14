# 🤖 Hệ Thống Chuyên Viên Ảo - Khối Đảng (Production Release)

Hệ thống tự động hóa phân tích văn bản chỉ đạo của Đảng ủy cấp trên (dạng PDF/Ảnh chụp) để soạn thảo **Công văn giao việc** (dạng Word `.docx`) tuân thủ nghiêm ngặt các quy chế hành chính, quy chuẩn chính tả Khối Đảng và tự động hóa phân vai tham mưu.

Hệ thống tích hợp **Chuyên viên ảo hỏi đáp nghiệp vụ (Q&A)** ứng dụng mô hình RAG tiên tiến trên nền cơ sở dữ liệu SQL để giải đáp các thắc mắc về thao tác phần mềm Hệ thống Điều hành tác nghiệp (ĐHTN), Thủ tục hành chính Đảng (TTHC) và quy trình nghiệp vụ.

Dự án triển khai chính thức trên kênh **Zalo Official Account (Zalo OA)** bằng giao thức Webhook bất đồng bộ, sử dụng cơ sở dữ liệu **PostgreSQL + pgvector** và đóng gói trọn gói bằng **Docker**.

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
Chuyên viên ảo/
│
├── taovanban_khoidang/              # Thư mục lõi chứa mã nguồn sinh văn bản
│   ├── references/                  # Thư mục chứa tài liệu mẫu và tri thức
│   │   ├── cong_van_giao_viec_mau.docx  # Mẫu công văn chuẩn Khối Đảng (chứa các thẻ biến {{...}})
│   │   ├── kienthuc_dhtn.md         # Bộ kiến thức nghiệp vụ ĐHTN (tri thức nền cứng)
│   │   ├── hdsd_chunks.json         # Dữ liệu tri thức mẫu dạng JSON (dùng khi di trú)
│   │   ├── HDSD/                    # Thư mục chứa tài liệu HDSD gốc
│   │   └── TTHC/                    # Thư mục chứa tài liệu TTHC Đảng gốc
│   │
│   ├── output/                      # Thư mục lưu trữ công văn Word sinh ra & Ảnh minh họa trích xuất
│   │   └── images/                  # Nơi lưu trữ ảnh chụp màn hình trích xuất từ tài liệu hướng dẫn
│   │
│   └── SKILL.md                     # Tài liệu mô tả kỹ năng và các quy tắc nghiệp vụ chi tiết
│
├── services/                        # Thư mục lõi chứa các mô-đun dịch vụ (RAG, AI, Knowledge, Document Creator, Zalo)
├── routers/                         # FastAPI Router (Webhook Zalo OA, Admin Dashboard Web)
├── templates/                       # Giao diện Jinja2 cho Admin Dashboard
├── static/                          # CSS/JS phục vụ giao diện Admin
├── scripts/                         # Các tập tin kịch bản và tiện ích hệ thống
│   ├── migrate_data.py              # Script di trú dữ liệu cũ từ JSON vào CSDL khi khởi động
│   ├── migrate_db_schema.py         # Script kiểm tra và cập nhật cấu trúc bảng CSDL
│   ├── reindex_embeddings.py        # Script re-index lại vector embedding
│   ├── seed_admin.py                # Script khởi tạo tài khoản quản trị ban đầu
│   ├── seed_knowledge.py            # Script nạp tri thức mặc định ban đầu từ SRT/MD
│   ├── reingest_manuals.py          # Script nạp lại toàn bộ file hướng dẫn markdown
│   ├── reingest_single_file.py      # Script nạp lại một file hướng dẫn markdown cụ thể
│   └── test_zalo_bot_qa.py          # Script kiểm thử chất lượng Q&A RAG cục bộ
│
├── docker/
│   └── init.sql                     # Script khởi tạo cơ sở dữ liệu PostgreSQL (pgvector, chỉ mục HNSW, GIN)
│
├── database.py                      # Module kết nối cơ sở dữ liệu (PostgreSQL / SQLite local fallback)
├── models.py                        # Định nghĩa ORM Models (Documents, Chunks, Image Mappings, Chat History)
├── zalo_bot.py                      # Bot Zalo ở chế độ Polling (Development)
├── main.py                          # Ứng dụng FastAPI chính (Webhook Zalo OA, Static Image Server, Secure Downloader)
├── requirements.txt                 # Danh sách thư viện Python cần thiết
├── Dockerfile                       # Tệp đóng gói ứng dụng chính
├── docker-compose.yml               # Định nghĩa Docker Compose (App FastAPI + PostgreSQL pgvector)
├── .env                             # Tệp ẩn lưu trữ mã bảo mật Token & API Key (không commit Git)
├── .gitignore                       # Cấu hình bỏ qua tệp tạm, DB SQLite và tệp cấu hình bảo mật
└── README.md                        # Tệp hướng dẫn này
```

---

## 🛠️ Yêu Cầu Hệ Thống & Triển Khai Nhanh (Docker)

Hệ thống được đóng gói hoàn chỉnh bằng Docker giúp triển khai lên Cloud Server (Ubuntu, CentOS...) nhanh chóng chỉ với 1 câu lệnh.

### Bước 1: Chuẩn bị tệp cấu hình bảo mật `.env`
Tạo file `.env` ở thư mục gốc của dự án với nội dung:
```env
# Zalo OA Bot API Token
ZALO_API_TOKEN=your_zalo_oa_token_here

# Google Gemini API Key (Dùng để sinh vector embeddings, OCR ảnh và fallback)
GEMINI_API_KEY=AIzaSy...

# DeepSeek API Key (Mô hình AI chính cho Q&A và phân tích PDF)
DEEPSEEK_API_KEY=sk-...

# Domain của Cloud Server phục vụ tải file và ảnh (bắt buộc phải có HTTPS Let's Encrypt)
SERVER_DOMAIN=https://your-domain.com

# Danh sách Zalo ID của Quản trị viên được quyền gửi file nạp tri thức (ngăn cách bằng dấu phẩy)
ADMIN_ZALO_IDS=12345678901234,98765432109876

# Chế độ chạy Zalo: 'webhook' (Production) hoặc 'polling' (Development)
ZALO_MODE=webhook
```

### Bước 2: Khởi chạy bằng Docker Compose
Chạy câu lệnh sau để build và khởi chạy ứng dụng cùng database PostgreSQL:
```bash
docker compose up --build -d
```
Docker sẽ tự động:
1. Tạo container cơ sở dữ liệu PostgreSQL 16 tích hợp extension `pgvector`.
2. Tạo các bảng cơ sở dữ liệu tối ưu qua file `init.sql` (bao gồm index HNSW cho vector và GIN cho full-text search).
3. Build container ứng dụng FastAPI chính chạy trên port `8080`.
4. Kích hoạt Webhook Zalo OA nhận tin nhắn trực tiếp.

---

## ⚡ Kiến Trúc RAG Tiên Tiến (Hybrid Search & Database-Driven)

Khác với các hệ thống RAG thô sơ chạy in-memory, hệ thống của chúng ta sử dụng kiến trúc RAG cấp độ Production:

### 1. Cơ sở dữ liệu: PostgreSQL + `pgvector`
*   Lưu trữ tri thức văn bản kết hợp vector embeddings **768 chiều** (tối ưu hóa hiệu năng và dung lượng trên VPS) tạo sinh từ mô hình thế hệ mới **`gemini-embedding-2`** thông qua cấu hình `output_dimensionality=768`.
*   **Metadata Filtering**: Cho phép lọc chính xác nguồn tài liệu, phân loại văn bản trước khi thực hiện so khớp vector để loại bỏ nhiễu ngữ nghĩa.
*   **Chỉ mục HNSW (Hierarchical Navigable Small World)**: Cấu hình với độ đo Cosine cho phép tìm kiếm tương đồng vector với độ trễ dưới 10ms trên hàng triệu bản ghi.

### 2. Tìm kiếm lai (Hybrid Search) & Bộ phân loại câu hỏi (LLM Classifier)
*   **Bộ phân loại ý định (Gemini Classifier)**: Trước khi tìm kiếm RAG, hệ thống chạy phân loại nhanh câu hỏi bằng Gemini 2.5 Flash để tách biệt câu hỏi **nội bộ nghiệp vụ** và **ngoài lề/xã giao**. Các câu xã giao/ngoài lề sẽ bỏ qua hoàn toàn RAG search để tránh sinh kết quả nhiễu, tăng tốc độ phản hồi và phản xạ tự do tốt hơn.
*   **Dense Search (So khớp vector ngữ nghĩa)**: Khớp các câu hỏi đồng nghĩa, diễn đạt khác nhau nhưng cùng bản chất thao tác phần mềm.
*   **Sparse Search (PostgreSQL Full-Text Search)**: Khớp chính xác các ký hiệu kỹ thuật, tên nút bấm cụ thể trên giao diện (ví dụ: "Phê duyệt phiếu trình", "Giao việc").
*   Công thức xếp hạng lai: `Combined Score = 0.7 * Cosine_Similarity + 0.3 * ts_rank_cd` (RRF score được scale nhân với **1200**).

### 3. Thuật toán phân đoạn cải tiến (Hierarchical Semantic Chunking)
*   Tách tài liệu theo cấu trúc heading Markdown (`#`, `##`, `###`).
*   **Không tạo chunk mồ côi**: Tự động gom các tiêu đề cha (H1/H2) rỗng không chứa văn bản vào các quy trình H3 thực tế bên dưới.
*   **Đính kèm Context Path**: Tự động chèn đường dẫn tiêu đề cha (Ví dụ: `# Hướng dẫn... ## I. Thao tác...`) lên đầu mỗi chunk con để đảm bảo LLM không bao giờ bị mất ngữ cảnh khi tìm kiếm RAG.

### 4. Fallback SQLite Thông Minh
Dự án tích hợp cơ chế tự phát hiện môi trường kết nối. Nếu không tìm thấy PostgreSQL (chạy offline/cục bộ trên máy cá nhân), hệ thống sẽ **tự động chuyển sang sử dụng SQLite cục bộ** (`chatbot_local.db`) làm database thay thế, giúp lập trình viên chạy test và phát triển cực kỳ thuận tiện mà không cần cài đặt hạ tầng phức tạp.

---

## 🔄 Đường Ống Cập Nhật Tri Tri thức Tự Động (Continuous Ingestion)

Để liên tục bổ sung tài liệu hướng dẫn mới mà không cần can thiệp mã nguồn:

1.  **Gửi tài liệu**: Quản trị viên (được xác thực qua ID Zalo trong danh sách `ADMIN_ZALO_IDS`) gửi file tài liệu (`.pdf`, `.docx`, `.srt` trích xuất từ video hướng dẫn) trực tiếp vào khung chat Zalo OA.
2.  **Tải và xử lý ngầm (Background Task)**: 
    *   FastAPI nhận webhook sự kiện gửi file (`user_send_file`), gửi phản hồi ngay lập tức cho Zalo server và chuyển file vào tiến trình xử lý ngầm (FastAPI `BackgroundTasks`).
    *   **Parser & OCR**: Module `document_uploader.py` tự động đọc file:
        *   Bóc tách hình ảnh minh họa đính kèm trong DOCX/PDF, lưu trữ trực tiếp vào thư mục ảnh tĩnh `/output/images/` để chatbot gửi kèm thao tác.
        *   Tẩy mốc thời gian và làm sạch cấu trúc đối với tệp video srt.
    *   **Chunking & Embedding**: Cắt nhỏ văn bản thành các chunks giữ nguyên ngữ cảnh (nhãn ảnh, bảng biểu) và gọi Gemini API để tạo vector embeddings 768 chiều.
    *   **Ghi nhận CSDL**: Tự động upsert dữ liệu vào bảng `knowledge_chunks` và lập bản đồ `image_mappings`.
3.  **Thông báo kết quả**: Bot gửi tin nhắn Zalo báo cáo kết quả chi tiết (số chunk đã nạp, số hình ảnh bóc tách thành công) cho Admin.

---

## 🛠️ Cài Đặt và Chạy Thử Cục Bộ (Không Dùng Docker)

### 1. Cài đặt thư viện Python
```bash
pip install -r requirements.txt
```

### 2. Khởi tạo và Di trú dữ liệu ban đầu
Chạy script di trú để tự động đọc tri thức JSON cũ, gọi Gemini API sinh vector 768 chiều và tạo cơ sở dữ liệu SQLite cục bộ:
```bash
python scripts/migrate_data.py
```

### 3. Chạy Server và Bot
```bash
python main.py
```
*Lưu ý: Mặc định trên máy cục bộ, hệ thống sẽ chạy Zalo Bot ở chế độ Polling để bạn test gửi tin nhắn dễ dàng mà không cần cấu hình domain HTTPS Let's Encrypt.*
