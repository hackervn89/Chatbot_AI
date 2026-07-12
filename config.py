"""
Cấu hình tập trung cho hệ thống RAG Chatbot.
Tất cả biến môi trường, hằng số, và thiết lập được quản lý tại đây.
"""
import os
import sys

# Cấu hình encoding UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ==================== LOAD .ENV ====================
def _load_dotenv():
    """Đọc file .env thủ công để hỗ trợ môi trường không có python-dotenv"""
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
                    if key not in os.environ:  # Không ghi đè env đã có sẵn
                        os.environ[key] = val

_load_dotenv()

# ==================== PATHS ====================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
REFERENCES_DIR = os.path.join(PROJECT_ROOT, "references")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")

# Tạo thư mục cần thiết
for d in [OUTPUT_DIR, TEMP_DIR, IMAGES_DIR, STATIC_DIR]:
    os.makedirs(d, exist_ok=True)

# ==================== DATABASE ====================
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    f'sqlite:///{os.path.join(TEMP_DIR, "chatbot_local.db")}'
)
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# ==================== API KEYS ====================
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

# ==================== AI ENGINE ====================
# Chọn AI engine chính: "deepseek" hoặc "gemini"
AI_PRIMARY_ENGINE = os.environ.get('AI_PRIMARY_ENGINE', 'deepseek')

# DeepSeek config
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
DEEPSEEK_TIMEOUT = int(os.environ.get('DEEPSEEK_TIMEOUT', '10'))

# Gemini config — danh sách model theo thứ tự ưu tiên fallback
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
]

# Embedding model
EMBEDDING_MODEL = "models/gemini-embedding-2"
EMBEDDING_DIMENSION = 3072

# ==================== ZALO BOT ====================
ZALO_API_TOKEN = os.environ.get('ZALO_API_TOKEN', '')
ZALO_MODE = os.environ.get('ZALO_MODE', 'polling').lower()
ZALO_WEBHOOK_SECRET = os.environ.get('ZALO_WEBHOOK_SECRET', '')

# ==================== TELEGRAM BOT ====================
TELEGRAM_API_TOKEN = os.environ.get('TELEGRAM_API_TOKEN', '')

# ==================== SERVER ====================
SERVER_DOMAIN = os.environ.get('SERVER_DOMAIN', 'http://localhost:8080')
SERVER_PORT = int(os.environ.get('PORT', '8080'))

# ==================== ADMIN ====================
ADMIN_ZALO_IDS = [x.strip() for x in os.environ.get('ADMIN_ZALO_IDS', '').split(',') if x.strip()]
ADMIN_DEFAULT_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_DEFAULT_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
SESSION_SECRET_KEY = os.environ.get('SESSION_SECRET_KEY', 'rag-chatbot-secret-key-change-me-2026')

# ==================== RAG CONFIG ====================
# Chunking
CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', '800'))
CHUNK_OVERLAP = int(os.environ.get('CHUNK_OVERLAP', '150'))

# Search
HYBRID_SEARCH_DENSE_WEIGHT = float(os.environ.get('DENSE_WEIGHT', '0.6'))
HYBRID_SEARCH_SPARSE_WEIGHT = float(os.environ.get('SPARSE_WEIGHT', '0.4'))
SEARCH_TOP_K = int(os.environ.get('SEARCH_TOP_K', '5'))
RERANK_TOP_N = int(os.environ.get('RERANK_TOP_N', '3'))

# Score thresholds (quyết định dùng tri thức nội bộ hay tìm web)
RAG_SCORE_HIGH = float(os.environ.get('RAG_SCORE_HIGH', '35'))
RAG_SCORE_MEDIUM = float(os.environ.get('RAG_SCORE_MEDIUM', '15'))

# ==================== CHAT ====================
MAX_CHAT_HISTORY = int(os.environ.get('MAX_CHAT_HISTORY', '10'))

# ==================== KNOWLEDGE CATEGORIES ====================
CATEGORY_CORE = "core"           # Tri thức gốc, không thay đổi
CATEGORY_UPDATABLE = "updatable"  # Tri thức cập nhật theo thời gian
CATEGORY_PERSONAL = "personal"    # Tri thức cá nhân admin nhập

# ==================== OCR SYSTEM PROMPT ====================
GEMINI_SYSTEM_PROMPT = """Bạn là chuyên viên văn thư hành chính Đảng. Nhiệm vụ của bạn là đọc văn bản chỉ đạo của cấp trên và trích xuất chính xác các thông tin sau.

Quy tắc xác định Cơ quan ban hành:
- Nếu văn bản ghi "Ban Thường vụ Tỉnh ủy ban hành" → Cơ quan ban hành là "Ban Thường vụ Tỉnh uỷ"
- Nếu văn bản ghi "Thường trực Tỉnh ủy chỉ đạo/yêu cầu" → Cơ quan ban hành là "Thường trực Tỉnh uỷ"
- Nếu văn bản ghi "Tỉnh ủy ban hành" hoặc "Ban Chấp hành Tỉnh ủy" → Cơ quan ban hành là "Tỉnh uỷ"
- Không ghép thêm tên địa phương (Khánh Hòa, Lâm Đồng...) vào tên cơ quan.

Quy tắc xác định Cơ quan tham mưu triển khai (co_quan_2) — chọn 1 trong 5:
1. "Uỷ ban nhân dân xã" — nếu nội dung liên quan đến: kinh tế, đất đai, môi trường, nông nghiệp, giao thông, xây dựng, y tế, giáo dục, thể dục thể thao, an ninh quốc phòng, giảm nghèo, lao động việc làm, tài chính ngân sách, dịch vụ công.
2. "Uỷ ban kiểm tra Đảng uỷ xã" — nếu nội dung liên quan đến: kiểm tra giám sát đảng viên, kỷ luật đảng, vi phạm, suy thoái, tự diễn biến, kê khai tài sản.
3. "Ban Xây dựng Đảng" — nếu nội dung liên quan đến: tổ chức cán bộ, tuyên giáo, chính trị tư tưởng, học tập nghị quyết, đạo đức cách mạng, nêu gương, xây dựng chỉnh đốn đảng, phát triển đảng viên, dân vận.
4. "Uỷ ban Mặt trận Tổ quốc Việt Nam xã" — nếu nội dung liên quan đến: đại đoàn kết toàn dân, phản biện xã hội, các đoàn thể (thanh niên, phụ nữ, cựu chiến binh, nông dân), vận động nhân dân, an sinh xã hội.
5. "Văn phòng Đảng uỷ xã" — nếu nội dung liên quan đến: quy chế làm việc, văn thư lưu trữ, nội chính, phòng chống tham nhũng lãng phí tiêu cực, chuyển đổi số, cải cách hành chính trong đảng.

Quy tắc xử lý chồng lấn:
- "giám sát" + "phản biện xã hội/cộng đồng/nhân dân" → MTTQ. Còn lại → UBKT.
- "tuyên truyền" + "vận động quần chúng/phong trào nhân dân" → MTTQ. Còn lại → Ban Xây dựng Đảng.
- "phòng chống tham nhũng" + "kiểm tra kỷ luật đảng viên" → UBKT. Còn lại → Văn phòng Đảng uỷ.

Bạn PHẢI trả lời bằng JSON hợp lệ với đúng cấu trúc sau (không thêm bất kỳ văn bản nào khác ngoài JSON):
{
  "doc_type": "Thể loại văn bản (Kế hoạch, Nghị quyết, Chỉ thị, Quy định, Chương trình...)",
  "number": "Ký hiệu số (ví dụ: 19-KH/TU)",
  "date": "Ngày ban hành theo định dạng DD/MM/YYYY",
  "authority": "Cơ quan ban hành",
  "title": "Trích yếu nội dung (phần sau chữ 'về')",
  "co_quan_2": "Tên cơ quan tham mưu triển khai (1 trong 5 cơ quan ở trên)"
}"""
