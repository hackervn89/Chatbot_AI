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
