import os
import re
import sys
import json
import time
import requests
import telebot
from pypdf import PdfReader
from google import genai
from google.genai import types

# Configure UTF-8 for console output on Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Dynamically resolve import paths so we can run from anywhere
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define custom dotenv loader to read .env file safely
def load_dotenv():
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

# Detect if we are running at the workspace root or inside taovanban_khoidang/scripts
if os.path.basename(script_dir) == "scripts":
    PROJECT_ROOT = os.path.dirname(script_dir)
    sys.path.append(script_dir)
else:
    PROJECT_ROOT = os.path.join(script_dir, "taovanban_khoidang")
    sys.path.append(os.path.join(PROJECT_ROOT, "scripts"))

from generate_docx import generate_document

# ==================== CONFIGURATION ====================
API_TOKEN = os.environ.get('TELEGRAM_API_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

# Danh sách mô hình Gemini theo thứ tự ưu tiên (fallback chain)
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
]
# =======================================================

# Validate tokens are loaded
if not API_TOKEN:
    print("[!] LỖI: Không tìm thấy TELEGRAM_API_TOKEN trong môi trường hoặc tệp .env")
    sys.exit(1)

bot = telebot.TeleBot(API_TOKEN)

# Paths relative to the project root
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "references", "cong_van_giao_viec_mau.docx")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
TEMP_DIR = os.path.join(PROJECT_ROOT, "scripts", "temp")
IMAGE_MAP_PATH = os.path.join(OUTPUT_DIR, "images", "image_map.json")
IMAGE_MAP_DATA = {}

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# System Prompt cho Gemini API (tiếng Việt)
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


KIENTHUC_PATH = os.path.join(PROJECT_ROOT, "references", "kienthuc_dhtn.md")
CHUNKS_PATH = os.path.join(PROJECT_ROOT, "references", "hdsd_chunks.json")
KIENTHUC_CONTENT = ""
CHUNKS_DATA = []
CHUNKS_IDFS = {}

def remove_accents(input_str):
    import unicodedata
    input_str = unicodedata.normalize('NFC', input_str)
    s1 = u'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẬậẸẹẺẻẼẽẾếỀềỂểỄễỆệỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỶỷỸỹỴỵ'
    s0 = u'AAAAEEEIIOOOOUUYaaaaeeeiioooouuyAaDdIiUuOoUuAaAaAaAaAaAaAaAaAaAaAaAaEeEeEeEeEeEeEeEeIiOoOoOoOoOoOoOoOoOoOoOoOoUuUuUuUuUuUuUuYyYyYyYy'
    s = ""
    for c in input_str:
        if c in s1:
            s += s0[s1.index(c)]
        else:
            s += c
    return s

def calculate_idfs(chunks):
    import math
    total_docs = len(chunks)
    doc_counts = {}
    for chunk in chunks:
        unique_words = set(chunk["text_unsigned"].split())
        path_words = chunk["source_unsigned"].replace("/", " ").replace("_", " ").replace(".", " ").split()
        unique_words.update(path_words)
        for word in unique_words:
            if len(word) > 1:
                doc_counts[word] = doc_counts.get(word, 0) + 1
    idfs = {}
    for word, count in doc_counts.items():
        idfs[word] = math.log(total_docs / count)
    return idfs

def retrieve_chunks(question, chunks, idfs, top_n=3):
    question_clean = remove_accents(question.lower())
    words = [w for w in question_clean.split() if len(w) > 1]
    if not words:
        return []
    
    # Tạo bigram (cặp từ liên tiếp) để khớp cụm từ đặc trưng
    # Ví dụ: "đảng phí" → "dang phi", "thủ tục" → "thu tuc"
    bigrams = []
    for i in range(len(words) - 1):
        bigrams.append(words[i] + " " + words[i + 1])
    
    scored_chunks = []
    for chunk in chunks:
        text_lower = chunk["text_unsigned"]
        source_lower = chunk["source_unsigned"]
        score = 0
        
        # 1. Unigram scoring (giữ nguyên logic gốc)
        for word in words:
            if word not in idfs:
                continue
            idf = idfs[word]
            word_score = 0
            if word in text_lower:
                tf = min(text_lower.count(word), 5)
                word_score += tf * idf
            if word in source_lower:
                word_score += 80 * idf
            score += word_score
        
        # 2. Bigram scoring (boost x3 cho cụm từ ghép khớp chính xác)
        for bigram in bigrams:
            if bigram in text_lower:
                tf = min(text_lower.count(bigram), 3)
                # Boost cao hơn unigram vì cụm từ chính xác hơn
                bigram_idf = sum(idfs.get(w, 0) for w in bigram.split())
                score += tf * bigram_idf * 3
            if bigram in source_lower:
                bigram_idf = sum(idfs.get(w, 0) for w in bigram.split())
                score += 120 * bigram_idf
        
        if score > 0:
            scored_chunks.append((score, chunk))
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return scored_chunks[:top_n]


def load_knowledge_bases():
    global KIENTHUC_CONTENT, CHUNKS_DATA, CHUNKS_IDFS, IMAGE_MAP_DATA
    # 1. Tải kienthuc_dhtn.md
    if os.path.exists(KIENTHUC_PATH):
        try:
            with open(KIENTHUC_PATH, 'r', encoding='utf-8') as f:
                KIENTHUC_CONTENT = f.read().strip()
            print(f"[Telegram Bot] Đã tải bộ kiến thức hệ thống ĐHTN ({len(KIENTHUC_CONTENT)} ký tự).")
        except Exception as e:
            print(f"[Telegram Bot] Lỗi khi đọc file kiến thức: {e}")
    else:
        print(f"[Telegram Bot] Cảnh báo: Không tìm thấy tệp kiến thức tại: {KIENTHUC_PATH}")

    # 2. Tải hdsd_chunks.json (RAG)
    if os.path.exists(CHUNKS_PATH):
        try:
            with open(CHUNKS_PATH, 'r', encoding='utf-8') as f:
                CHUNKS_DATA = json.load(f)
            for chunk in CHUNKS_DATA:
                chunk["text_unsigned"] = remove_accents(chunk["text"].lower())
                chunk["source_unsigned"] = remove_accents(chunk["source"].lower())
            CHUNKS_IDFS = calculate_idfs(CHUNKS_DATA)
            print(f"[Telegram Bot] Đã tải RAG database ({len(CHUNKS_DATA)} chunks).")
        except Exception as e:
            print(f"[Telegram Bot] Lỗi khi tải RAG database: {e}")
    else:
        print(f"[Telegram Bot] Cảnh báo: Không tìm thấy tệp RAG tại: {CHUNKS_PATH}")

    # 3. Tải bản đồ hình ảnh
    if os.path.exists(IMAGE_MAP_PATH):
        try:
            with open(IMAGE_MAP_PATH, 'r', encoding='utf-8') as f:
                IMAGE_MAP_DATA = json.load(f)
            print(f"[Telegram Bot] Đã tải bản đồ hình ảnh ({len(IMAGE_MAP_DATA)} tài liệu).")
        except Exception as e:
            print(f"[Telegram Bot] Lỗi khi tải bản đồ hình ảnh: {e}")

load_knowledge_bases()

DHTN_QA_SYSTEM_PROMPT = """Bạn là Trợ lý ảo hành chính Đảng chuyên nghiệp tại Đảng ủy xã, hỗ trợ nghiệp vụ và vận hành phần mềm Điều hành tác nghiệp (ĐHTN).

Quy tắc ứng xử và nghiệp vụ:
1. Độ chính xác thông tin: Đối với các quy trình, thao tác và thông số của phần mềm Điều hành tác nghiệp (ĐHTN) hoặc Thủ tục hành chính Đảng, bạn BẮT BUỘC chỉ được trả lời dựa trên Bộ Kiến Thức Nghiệp Vụ được cung cấp dưới đây. Nếu Bộ Kiến Thức không đề cập hoặc thiếu thông tin, bạn phải trả lời trung thực là: "Thông tin này chưa được cập nhật trong tài liệu hướng dẫn sử dụng ĐHTN của cơ quan. Vui lòng liên hệ cán bộ quản trị hoặc văn thư phụ trách để được hỗ trợ." Tuyệt đối KHÔNG tự suy diễn logic, không đoán bừa thông số kỹ thuật hoặc sử dụng kiến thức về phần mềm khác.
2. Phong cách ngôn ngữ: Lịch sự, nhã nhặn, cô đọng, chuẩn mực công vụ. Lược bỏ hoàn toàn mọi câu chào hỏi, giới thiệu học thuật rườm rà ở đầu tin nhắn (ví dụ: "Chào bạn, tôi sẽ hướng dẫn...") và các câu chúc ở cuối tin nhắn. Hãy trả lời trực tiếp ngay vào nội dung nghiệp vụ hoặc các bước thực hiện.
3. Khi hướng dẫn thao tác phần mềm, nếu tài liệu tham chiếu có đề cập đến hình ảnh minh họa (ví dụ: "Hình 1", "Hình 2"...), hãy giữ nguyên nhãn "Hình N" trong câu trả lời để hệ thống có thể tự động đính kèm ảnh minh họa tương ứng cho người dùng.
4. Đối với các câu hỏi ngoài lề (như trò chuyện hàng ngày, toán học, lập trình, nấu ăn, thời tiết...): Trả lời trực tiếp, ngắn gọn, nhiệt tình và chính xác theo kiến thức chung của bạn.

Quy tắc định dạng tin nhắn Zalo/Telegram (CỰC KỲ QUAN TRỌNG để tin nhắn đẹp mắt, gọn gàng):
- KHÔNG sử dụng các tiêu đề ký tự Markdown như #, ##, ###, ----.
- KHÔNG sử dụng dòng trống liên tiếp (ví dụ: không dùng \n\n). Mỗi phân đoạn hoặc bước chỉ ngăn cách bằng đúng một dấu xuống dòng (\n) để tin nhắn không bị giãn cách quá rộng và lê thê trên điện thoại.
- Sử dụng các biểu tượng biểu cảm (emoji) hành chính như 🔹, 📌, ⚠️, ✅ ở đầu mỗi bước hoặc đầu dòng lưu ý để tạo điểm nhấn trực quan thay vì dùng gạch đầu dòng Markdown (- hoặc *).
- Sử dụng chữ in đậm bằng ký tự ** (ví dụ: **Nhấn Ghi lại**) để làm nổi bật các tên nút bấm, chức năng hoặc trạng thái quan trọng, giúp người dùng dễ dàng lướt đọc nhanh.

Dưới đây là Bộ Kiến Thức Nghiệp Vụ để bạn tham chiếu:
=== BẮT ĐẦU BỘ KIẾN THỨC ===
{kienthuc_content}
=== KẾT THÚC BỘ KIẾN THỨC ==="""

MAX_HISTORY_LEN = 10  # 10 tin nhắn gần nhất (5 lượt hội thoại)
CONVERSATION_HISTORY = {}

def get_chat_history(chat_id):
    if chat_id not in CONVERSATION_HISTORY:
        CONVERSATION_HISTORY[chat_id] = []
    return CONVERSATION_HISTORY[chat_id]

def add_chat_message(chat_id, role, content):
    if chat_id not in CONVERSATION_HISTORY:
        CONVERSATION_HISTORY[chat_id] = []
    CONVERSATION_HISTORY[chat_id].append({"role": role, "content": content})
    if len(CONVERSATION_HISTORY[chat_id]) > MAX_HISTORY_LEN:
        CONVERSATION_HISTORY[chat_id] = CONVERSATION_HISTORY[chat_id][-MAX_HISTORY_LEN:]

def search_duckduckgo_free(query, max_results=3):
    """Tìm kiếm DuckDuckGo sử dụng thư viện ddgs để lấy thông tin thời gian thực"""
    from ddgs import DDGS
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            if results:
                return [r["body"] for r in results if "body" in r]
    except Exception as e:
        print(f"[Search Error] {e}")
    return []

def ask_dhtn_qa(chat_id, question):
    """Trả lời thắc mắc của người dùng dựa trên bộ tri thức ĐHTN kết hợp RAG HDSD và giữ ngữ cảnh hội thoại, chỉ dùng DeepSeek làm mô hình chính"""
    if not KIENTHUC_CONTENT and not CHUNKS_DATA:
        return None, None, []
        
    history = get_chat_history(chat_id)
    best_score = 0
    relevant_results = []
    
    if CHUNKS_DATA:
        relevant_results = retrieve_chunks(question, CHUNKS_DATA, CHUNKS_IDFS, top_n=3)
        if relevant_results:
            best_score = relevant_results[0][0]
            
    # Lấy thông tin ngữ cảnh (Nội bộ hoặc Tìm kiếm Web)
    relevant_context = ""
    use_internal_kt = True
    
    if best_score >= 15:
        # Có sự tương thích tri thức nội bộ
        if best_score >= 35:
            print(f"[RAG] Điểm số nội bộ cao ({best_score:.1f}). Sử dụng tài liệu nghiệp vụ nội bộ.")
            relevant_context = "\n\nDưới đây là tài liệu hướng dẫn chi tiết trích từ HDSD hệ thống:\n"
            for idx, (score, chunk) in enumerate(relevant_results):
                relevant_context += f"--- Nguồn tài liệu: {chunk['source']} ---\n{chunk['text']}\n"
        else:
            print(f"[RAG] Điểm số nội bộ trung bình ({best_score:.1f}). Đang tìm kiếm Web...")
            web_results = search_duckduckgo_free(question)
            if web_results:
                relevant_context = "\n\nDưới đây là thông tin tìm kiếm thời gian thực trên Internet về câu hỏi này:\n"
                for idx, snippet in enumerate(web_results):
                    relevant_context += f"- Kết quả {idx+1}: {snippet}\n"
    else:
        # Điểm số cực thấp -> Chit-chat hoặc câu hỏi chung
        print(f"[RAG] Điểm số nội bộ cực thấp ({best_score:.1f}). Nhận diện câu hỏi chung/ngoài lề.")
        use_internal_kt = False
        web_results = search_duckduckgo_free(question)
        if web_results:
            relevant_context = "\n\ Dưới đây là thông tin tìm kiếm trên Internet:\n"
            for idx, snippet in enumerate(web_results):
                relevant_context += f"- Kết quả {idx+1}: {snippet}\n"
                
    # Toàn bộ ngữ cảnh RAG chỉ lấy từ database động, loại bỏ file tĩnh KIENTHUC_CONTENT
    kt_content = relevant_context if use_internal_kt else "Không có tài liệu tham chiếu nội bộ phù hợp."
    system_prompt = DHTN_QA_SYSTEM_PROMPT.format(
        kienthuc_content=kt_content
    )
    
    # 1. Ưu tiên số 1: Luôn dùng DeepSeek cho mọi câu hỏi
    if DEEPSEEK_API_KEY:
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": question})
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.5
        }
        try:
            print(f"[QA] Đang gửi câu hỏi tới DeepSeek (Lịch sử: {len(history)} tin)...")
            response = requests.post(url, json=payload, headers=headers, timeout=25)
            if response.status_code == 200:
                res_data = response.json()
                reply = res_data["choices"][0]["message"]["content"].strip()
                if reply:
                    add_chat_message(chat_id, "user", question)
                    add_chat_message(chat_id, "assistant", reply)
                    return reply, "DeepSeek-V3", relevant_results
        except Exception as e:
            print(f"[QA] Lỗi gọi DeepSeek Q&A: {e}")
            
    # 2. Phương án dự phòng cuối cùng nếu DeepSeek lỗi hoặc hết tiền -> Dùng Gemini
    if GEMINI_API_KEY:
        client = genai.Client(api_key=GEMINI_API_KEY)
        gemini_contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            gemini_contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                )
            )
        gemini_contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=question)]
            )
        )
        
        # Bật thêm Google Search Grounding cho Gemini dự phòng nếu câu hỏi là chung
        tools_config = []
        if best_score < 35:
            google_search_tool = types.Tool(
                google_search=types.GoogleSearch()
            )
            tools_config = [google_search_tool]
            
        for model_name in GEMINI_MODELS:
            try:
                print(f"[QA] Đang gọi Gemini dự phòng ({model_name})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=gemini_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.5,
                        tools=tools_config
                    )
                )
                reply = response.text.strip() if response.text else ""
                if reply:
                    add_chat_message(chat_id, "user", question)
                    add_chat_message(chat_id, "assistant", reply)
                    return reply, f"Gemini ({model_name})", relevant_results
            except Exception as e:
                print(f"[QA] Lỗi gọi model Gemini {model_name}: {e}")
                
    return "Tôi đang gặp sự cố kết nối tới máy chủ AI. Xin vui lòng thử lại sau.", None, []

def analyze_with_gemini(pdf_text):
    """
    Gửi văn bản PDF cho Gemini API để phân tích.
    Thử lần lượt 3 mô hình theo thứ tự ưu tiên.
    Trả về dict kết quả nếu thành công, None nếu tất cả đều thất bại.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == 'ĐIỀN_GEMINI_API_KEY_TẠI_ĐÂY':
        print("[!] Chưa cấu hình Gemini API Key. Sử dụng Rule-based.")
        return None

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"[!] Lỗi khởi tạo Gemini Client: {e}")
        return None

    for model_name in GEMINI_MODELS:
        try:
            print(f"[*] Đang thử mô hình: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=pdf_text,
                config=types.GenerateContentConfig(
                    system_instruction=GEMINI_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

            # Parse JSON response
            result_text = response.text.strip()
            result = json.loads(result_text)

            # Validate required fields
            required_fields = ["doc_type", "number", "date", "authority", "title", "co_quan_2"]
            if all(field in result and result[field] for field in required_fields):
                result["model_used"] = model_name
                print(f"[+] Phân tích thành công bởi: {model_name}")
                return result
            else:
                print(f"[-] Mô hình {model_name} trả về JSON thiếu trường. Thử mô hình tiếp theo...")
                continue

        except json.JSONDecodeError as e:
            print(f"[-] Mô hình {model_name} trả về JSON không hợp lệ: {e}. Thử mô hình tiếp theo...")
            continue
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"[-] Mô hình {model_name} đã hết hạn mức (Rate Limit). Thử mô hình tiếp theo...")
            else:
                print(f"[-] Lỗi khi gọi mô hình {model_name}: {e}. Thử mô hình tiếp theo...")
            continue

    print("[!] Tất cả mô hình Gemini đều thất bại. Chuyển sang Rule-based.")
    return None

def analyze_with_deepseek(text):
    """
    Gửi văn bản cho Deepseek Chat API (Có phí, ưu tiên hàng đầu).
    """
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == 'ĐIỀN_DEEPSEEK_API_KEY_TẠI_ĐÂY':
        print("[Deepseek] DEEPSEEK_API_KEY chưa cấu hình. Bỏ qua...")
        return None
        
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": GEMINI_SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "response_format": {
            "type": "json_object"
        },
        "temperature": 0.1
    }
    
    try:
        print("[Deepseek] Đang gửi yêu cầu phân tích...")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            res_data = response.json()
            content = res_data["choices"][0]["message"]["content"].strip()
            data = json.loads(content)
            
            required_fields = ["doc_type", "number", "date", "authority", "title", "co_quan_2"]
            if all(field in data and data[field] for field in required_fields):
                data["model_used"] = "DeepSeek-V3"
                print("[+] Phân tích thành công bởi: DeepSeek-V3")
                return data
        else:
            print(f"[-] Deepseek API Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[-] Lỗi khi gọi Deepseek API: {e}")
    return None

def parse_pdf_metadata(pdf_path):
    """
    Parse PDF to automatically extract document type, number, date, authority, and title.
    """
    reader = PdfReader(pdf_path)
    first_page_text = ""
    for page in reader.pages[:1]:
        first_page_text += page.extract_text() or ""
        
    lines = [line.strip() for line in first_page_text.split('\n') if line.strip()]
    
    # 1. Identify Number
    number = ""
    num_match = re.search(r'Số\s+([^\r\n]+)', first_page_text, re.IGNORECASE)
    if num_match:
        number = num_match.group(1).strip()
        
    # 2. Identify Date
    date_str = ""
    date_match = re.search(r'ngày\s+(\d+)\s+tháng\s+(\d+)\s+năm\s+(\d+)', first_page_text, re.IGNORECASE)
    if date_match:
        d, m, y = date_match.groups()
        date_str = f"{int(d):02d}/{int(m):02d}/{y}"
    else:
        date_match2 = re.search(r'ngày\s+(\d+)[/-](\d+)[/-](\d+)', first_page_text, re.IGNORECASE)
        if date_match2:
            d, m, y = date_match2.groups()
            date_str = f"{int(d):02d}/{int(m):02d}/{y}"
            
    # 3. Identify Document Type and Title
    doc_type = "Kế hoạch"
    title = ""
    
    types = ["KẾ HOẠCH", "NGHỊ QUYẾT", "CHƯƠNG TRÌNH", "CHỈ THỊ", "QUY ĐỊNH", "QUYẾT ĐỊNH", "CÔNG VĂN"]
    type_idx = -1
    for idx, line in enumerate(lines):
        if any(t in line for t in types):
            doc_type = line.title()
            type_idx = idx
            break
            
    if type_idx != -1:
        title_lines = []
        for idx in range(type_idx + 1, len(lines)):
            line = lines[idx]
            if line.startswith("---") or line.startswith("I.") or "mục đích" in line.lower() or "nhằm" in line.lower():
                break
            title_lines.append(line)
        title = " ".join(title_lines).strip()
        
    title = re.sub(r'\s*\-+\s*$', '', title)
    
    # 4. Identify Issuing Authority
    authority = "Ban Thường vụ Tỉnh ủy"
    if "ban thường vụ tỉnh ủy" in first_page_text.lower():
        authority = "Ban Thường vụ Tỉnh ủy"
    elif "thường trực tỉnh ủy" in first_page_text.lower():
        authority = "Thường trực Tỉnh ủy"
    elif "tỉnh ủy" in first_page_text.lower():
        authority = "Tỉnh ủy"
    elif "trung ương" in first_page_text.lower():
        authority = "Ban Chấp hành Trung ương"
        
    return doc_type, number, date_str, authority, title


def get_short_type(doc_type):
    dt = doc_type.lower()
    if "kế hoạch" in dt:
        return "KH"
    elif "nghị quyết" in dt:
        return "NQ"
    elif "chương trình" in dt:
        return "CTr"
    elif "chỉ thị" in dt:
        return "CT"
    elif "quy định" in dt:
        return "QD"
    elif "quyết định" in dt:
        return "QĐ"
    return "CV"


def get_short_title(title):
    # Try to grab the core topic after "về"
    match = re.search(r'về\s+(.*)', title, re.IGNORECASE)
    if match:
        target = match.group(1).strip()
    else:
        target = re.sub(r'^(Thực hiện\s+|Triển khai\s+)', '', title, flags=re.IGNORECASE)
    
    words = target.split()
    if len(words) > 6:
        return " ".join(words[:6])
    return target


def determine_agency_2(title, first_page_text):
    """
    Determine Co_quan_2 automatically based on keyword matching and disambiguation rules.
    """
    text = (title + " " + first_page_text).lower()

    # Pre-process common spelling variations to simplify matching
    text = text.replace("uỷ", "ủy").replace("oà", "òa").replace("uý", "úy")

    # 1. Disambiguation rules first
    # 1.1 "giám sát"
    has_giamsat = "giám sát" in text
    is_mttq_giamsat = has_giamsat and any(
        k in text for k in ["phản biện xã hội", "cộng đồng", "của nhân dân", "giám sát xã hội", "giám sát cộng đồng"]
    )
    is_ubkt_giamsat = has_giamsat and not is_mttq_giamsat

    # 1.2 "phòng chống tham nhũng, lãng phí, tiêu cực"
    has_pctn = any(k in text for k in ["phòng chống tham nhũng", "tiêu cực", "lãng phí"])
    is_ubkt_pctn = has_pctn and any(
        k in text for k in ["kiểm tra", "kỷ luật", "đảng viên", "chi bộ", "dấu hiệu vi phạm", "kê khai tài sản"]
    )
    is_vpdu_pctn = has_pctn and not is_ubkt_pctn

    # 1.3 "tuyên truyền"
    has_tuyentruyen = "tuyên truyền" in text
    is_mttq_tuyentruyen = has_tuyentruyen and any(
        k in text for k in ["vận động quần chúng", "phong trào nhân dân", "cuộc vận động toàn dân", "vận động nhân dân"]
    )
    is_bxd_tuyentruyen = has_tuyentruyen and not is_mttq_tuyentruyen

    # 1.4 "tôn giáo, dân tộc"
    has_tongiao_dantoc = any(k in text for k in ["tôn giáo", "dân tộc"])
    is_mttq_tongiao_dantoc = has_tongiao_dantoc and any(
        k in text for k in ["thiểu số", "vận động nhân dân các tôn giáo", "đại đoàn kết dân tộc", "khối đại đoàn kết"]
    )
    is_bxd_tongiao_dantoc = has_tongiao_dantoc and not is_mttq_tongiao_dantoc

    # 1.5 "khiếu nại, tố cáo"
    has_kntc = any(k in text for k in ["khiếu nại", "tố cáo"])
    is_ubkt_kntc = has_kntc and any(
        k in text for k in ["đảng viên", "tổ chức đảng", "kỷ luật đảng", "đảng phí", "sinh hoạt đảng"]
    )
    is_ubnd_kntc = has_kntc and not is_ubkt_kntc

    # 2. Match with keyword lists
    # UBKT Keywords
    ubkt_keywords = [
        "kiểm tra", "kỷ luật đảng", "thi hành kỷ luật", "kỷ luật", "vi phạm", "dấu hiệu vi phạm",
        "kiểm tra khi có dấu hiệu vi phạm", "giám sát chuyên đề", "khiển trách", "cảnh cáo", "cách chức",
        "khai trừ", "xử lý đảng viên vi phạm", "suy thoái", "tự diễn biến", "tự chuyển hoá", "đảng phí",
        "thẻ đảng", "thu hồi thẻ đảng", "kê khai tài sản", "khiếu nại tố cáo đối với đảng viên",
        "giải quyết tố cáo đảng viên", "sinh hoạt đảng không đúng quy định"
    ]
    
    # Ban Xây dựng Đảng Keywords
    bxd_keywords = [
        "tổ chức cán bộ", "quy hoạch cán bộ", "đào tạo bồi dưỡng cán bộ", "luân chuyển cán bộ",
        "bổ nhiệm", "đề bạt", "sắp xếp tổ chức bộ máy", "tinh giản biên chế", "nhân sự", "tuyên giáo",
        "chính trị tư tưởng", "giáo dục chính trị", "học tập nghị quyết", "quán triệt nghị quyết",
        "sơ kết tổng kết nghị quyết", "đạo đức cách mạng", "học tập và làm theo", "tư tưởng hồ chí minh",
        "tấm gương đạo đức", "nêu gương", "chuẩn mực đạo đức", "xây dựng đảng", "chỉnh đốn đảng",
        "nâng cao năng lực lãnh đạo", "đổi mới phương thức lãnh đạo", "xây dựng tổ chức đảng",
        "kết nạp đảng", "phát triển đảng viên", "chuyển đảng chính thức", "đảng viên dự bị", "dân vận",
        "dân vận khéo", "công tác dân vận", "tuyên truyền"
    ]

    # MTTQ Keywords
    mttq_keywords = [
        "mặt trận tổ quốc", "ban thường trực mặt trận", "khối đại đoàn kết", "phản biện xã hội",
        "giám sát xã hội", "hiệp thương bầu cử", "ý kiến kiến nghị của cử tri", "phong trào thi đua toàn dân",
        "an sinh xã hội", "quyên góp ủng hộ", "đoàn thanh niên", "hội phụ nữ", "hội liên hiệp phụ nữ",
        "hội cựu chiến binh", "hội nông dân", "công đoàn", "các đoàn thể", "tổ chức chính trị - xã hội",
        "từ thiện", "quyên góp", "ủng hộ", "quỹ vì người nghèo", "ngày vì người nghèo", "phong trào",
        "cuộc vận động", "toàn dân", "vận động nhân dân", "ngày hội đại đoàn kết", "ý kiến cử tri",
        "kiến nghị cử tri", "tiếp xúc cử tri", "mặt trận"
    ]

    # VPĐU Keywords
    vpdu_keywords = [
        "văn phòng đảng uỷ", "văn phòng đảng ủy", "văn thư", "lưu trữ", "phục vụ cấp uỷ", "phục vụ cấp ủy",
        "quy chế làm việc", "chương trình công tác", "tổng hợp", "báo cáo định kỳ", "báo cáo sơ kết",
        "báo cáo tổng kết", "hậu cần", "hội nghị", "phiên họp", "chuyển đổi số", "công nghệ thông tin",
        "ứng dụng cntt", "nội chính", "phòng chống tham nhũng", "lãng phí", "tiêu cực", "cải cách hành chính trong đảng"
    ]

    # UBND Keywords
    ubnd_keywords = [
        "ủy ban nhân dân", "uỷ ban nhân dân", "cơ quan chấp hành", "hành chính nhà nước", "quản lý hành chính địa phương",
        "thi hành pháp luật", "dự toán ngân sách xã", "tài sản công cấp xã", "biên chế công chức xã",
        "an ninh trật tự cơ sở", "dịch vụ công thiết yếu", "tiếp công dân cấp xã", "hoạt động tự quản của thôn",
        "kinh tế", "kinh tế - xã hội", "phát triển kinh tế", "đất đai", "tài nguyên", "khoáng sản",
        "môi trường", "biến đổi khí hậu", "nông nghiệp", "nông thôn", "nông thôn mới", "xây dựng nông thôn mới",
        "thuỷ lợi", "thuỷ sản", "lâm nghiệp", "chăn nuôi", "giao thông", "xây dựng", "hạ tầng",
        "cơ sở hạ tầng", "quy hoạch", "đô thị", "văn hoá", "thể dục", "thể thao", "du lịch", "di tích",
        "lễ hội", "giáo dục", "đào tạo", "trường học", "phổ cập giáo dục", "y tế", "trạm y tế", "dịch bệnh",
        "phòng chống dịch", "an toàn thực phẩm", "vệ sinh an toàn thực phẩm", "an ninh", "quốc phòng",
        "an ninh quốc phòng", "an ninh trật tự", "trật tự an toàn xã hội", "phòng chống tội phạm",
        "ma tuý", "phòng chống thiên tai", "phòng chống lụt bão", "cứu hộ cứu nạn", "ứng phó sự cố",
        "xoá đói giảm nghèo", "giảm nghèo", "lao động", "việc làm", "bảo hiểm xã hội", "bảo hiểm y tế",
        "người có công", "chính sách xã hội", "hộ tịch", "chứng thực", "tư pháp", "hoà giải", "thương mại",
        "dịch vụ", "công nghiệp", "tiểu thủ công nghiệp", "ngân sách", "thuế", "phí", "lệ phí", "tài chính",
        "tài sản công", "dịch vụ công", "điện chiếu sáng", "cấp nước", "xử lý rác thải", "phòng chống cháy nổ"
    ]

    # Matching logic using disambiguations and keyword occurrences
    # Check UBKT first (disciplinary/control has high specificity)
    if is_ubkt_giamsat or is_ubkt_pctn or is_ubkt_kntc or any(k in text for k in ubkt_keywords if k != "giám sát" and k != "tố cáo" and k != "khiếu nại"):
        return "Uỷ ban kiểm tra Đảng uỷ xã"
        
    # Check VPĐU (internal administration / PCTN policy / office matters)
    if is_vpdu_pctn or any(k in text for k in vpdu_keywords if k != "phòng chống tham nhũng" and k != "tiêu cực" and k != "lãng phí"):
        return "Văn phòng Đảng uỷ xã"
        
    # Check Ban Xây dựng Đảng
    if is_bxd_tuyentruyen or is_bxd_tongiao_dantoc or any(k in text for k in bxd_keywords if k != "tuyên truyền" and k != "tôn giáo" and k != "dân tộc"):
        return "Ban Xây dựng Đảng"
        
    # Check MTTQ
    if is_mttq_giamsat or is_mttq_tuyentruyen or is_mttq_tongiao_dantoc or any(k in text for k in mttq_keywords if k != "mặt trận"):
        return "Uỷ ban Mặt trận Tổ quốc Việt Nam xã"
        
    # Check UBND (if specific administrative task is matched)
    if is_ubnd_kntc or any(k in text for k in ubnd_keywords if k not in ["tư pháp", "y tế", "giao thông", "xây dựng", "giáo dục", "an ninh", "quốc phòng"]):
        return "Uỷ ban nhân dân xã"
        
    # Fallback checking with general keywords
    if any(k in text for k in ["ủy ban nhân dân", "uỷ ban nhân dân", "ubnd", "chính quyền"]):
        return "Uỷ ban nhân dân xã"
    if any(k in text for k in ["mặt trận", "mttq", "đoàn thanh niên", "hội phụ nữ"]):
        return "Uỷ ban Mặt trận Tổ quốc Việt Nam xã"
    if any(k in text for k in ["tuyên truyền", "đảng viên", "xây dựng đảng", "tổ chức"]):
        return "Ban Xây dựng Đảng"

    # Default is Uỷ ban nhân dân xã
    return "Uỷ ban nhân dân xã"


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🤖 **Chuyên Viên Ảo - Hệ Thống Soạn Thảo Công Văn Tự Động**\n\n"
        "Chào bạn! Để tạo công văn giao việc từ xa, bạn chỉ cần gửi file PDF văn bản chỉ đạo của cấp trên vào phòng chat này.\n\n"
        "Tôi sẽ tự động phân tích và gửi lại file Word (.docx) đã được căn lề, định dạng chuẩn hành chính và áp dụng đầy đủ quy tắc nghiệp vụ Khối Đảng."
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown')


@bot.message_handler(content_types=['document'])
def handle_docs(message):
    pdf_path = None
    try:
        # 1. Validate PDF format
        pdf_name = message.document.file_name
        if not pdf_name.lower().endswith('.pdf'):
            bot.reply_to(message, "⚠️ Vui lòng gửi tệp định dạng PDF (.pdf).")
            return
            
        bot.reply_to(message, "📥 Đang tải tệp tin và tiến hành phân tích...")
        
        # 2. Download PDF file
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        pdf_path = os.path.join(TEMP_DIR, pdf_name)
        with open(pdf_path, 'wb') as f:
            f.write(downloaded_file)
            
        # 3. Extract PDF text
        reader = PdfReader(pdf_path)
        first_page_text = reader.pages[0].extract_text() or ""
        last_page_text = ""
        if len(reader.pages) > 1:
            last_page_text = reader.pages[-1].extract_text() or ""
        
        # Combine text for AI analysis (page 1 + last page to save tokens)
        combined_text = first_page_text
        if last_page_text and last_page_text != first_page_text:
            combined_text += "\n\n--- TRANG CUỐI ---\n\n" + last_page_text

        # 4. Try AI analysis first, then fallback to Rule-based
        analysis_method = ""
        
        # 4.1 Thử phân tích bằng DeepSeek trước (có phí)
        ai_result = analyze_with_deepseek(combined_text)
        
        # 4.2 Nếu DeepSeek không cấu hình hoặc lỗi, thử Gemini (miễn phí)
        if not ai_result:
            ai_result = analyze_with_gemini(combined_text)
        
        if ai_result:
            # === AI SUCCESS ===
            doc_type = ai_result["doc_type"]
            number = ai_result["number"]
            date_str = ai_result["date"]
            authority = ai_result["authority"]
            title = ai_result["title"]
            co_quan_2 = ai_result["co_quan_2"]
            analysis_method = f"🤖 {ai_result.get('model_used', 'Gemini')}"
        else:
            # === FALLBACK: Rule-based ===
            doc_type, number, date_str, authority, title = parse_pdf_metadata(pdf_path)
            
            if not number or not date_str:
                bot.reply_to(message, "⚠️ Không thể tự động phân tích số hoặc ngày của văn bản này. Vui lòng kiểm tra lại chất lượng tệp PDF.")
                return
                
            co_quan_2 = determine_agency_2(title, first_page_text)
            analysis_method = "⚙️ Hệ thống quy tắc nội bộ"
        
        # 5. Construct payload variables
        van_ban_cap_tren = f"{doc_type} số {number}, ngày {date_str} của {authority} về {title}"
        trich_yeu = f"V/v thực hiện {doc_type} số {number} ngày {date_str} của {authority}"
        
        # Determine output filename based on convention
        short_type = get_short_type(doc_type)
        short_title = get_short_title(title)
        output_name = f"CV tham mưu {short_type} TU về {short_title}.docx"
        # Sanitize filename (remove characters not allowed in windows filenames)
        output_name = re.sub(r'[\\/*?:"<>|]', "", output_name)
        output_path = os.path.join(OUTPUT_DIR, output_name)
        
        # 6. Prepare JSON Data
        data = {
            "van_ban_cap_tren": van_ban_cap_tren,
            "Ngay_den_han_1": "",  # Automatically computed as default (10 days)
            "Co_quan_2": co_quan_2,
            "ngay_den_han_2": "",  # Automatically computed as default (10 days)
            "TRICH_YEU_CONG_VAN": trich_yeu,
            "DANH_SACH_NOI_NHAN": ["Thường trực Đảng ủy", "Các chi bộ trực thuộc", "Lưu VPĐU"]
        }
        
        bot.send_message(
            message.chat.id, 
            f"🔍 **Thông tin trích xuất:**\n"
            f"- Loại văn bản: {doc_type}\n"
            f"- Số hiệu: {number}\n"
            f"- Ngày ban hành: {date_str}\n"
            f"- Cơ quan ban hành: {authority}\n"
            f"- Cơ quan tham mưu: {co_quan_2}\n"
            f"- Phân tích: Dựa trên kiến thức được đào tạo\n\n"
            f"⚡ Đang chạy sinh công văn...",
            parse_mode='Markdown'
        )
        
        # 7. Generate the Document
        generate_document(data, TEMPLATE_PATH, output_path)
        
        # 8. Send Word document back to user
        with open(output_path, 'rb') as doc_file:
            bot.send_document(
                message.chat.id, 
                doc_file, 
                caption=f"✅ Đã soạn thảo xong công văn!\n📁 Tên file: {output_name}\n(Dựa trên kiến thức được đào tạo)"
            )
            
    except Exception as e:
        bot.reply_to(message, f"❌ Có lỗi xảy ra trong quá trình xử lý: {str(e)}")
        
    finally:
        # Clean up downloaded PDF file
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass

@bot.message_handler(content_types=['text'])
def handle_text_questions(message):
    question = message.text.strip()
    if question.startswith('/'):
        return  # Bỏ qua các lệnh hệ thống
        
    bot.send_chat_action(message.chat.id, 'typing')
    
    def split_message(text, max_len=3800):
        """Chia nhỏ tin nhắn thành nhiều phần, ưu tiên chia ở ranh giới đoạn văn"""
        if len(text) <= max_len:
            return [text]
        parts = []
        while text:
            if len(text) <= max_len:
                parts.append(text)
                break
            # Ưu tiên 1: Chia ở dấu đoạn trống (\n\n)
            split_idx = text.rfind('\n\n', 0, max_len)
            if split_idx == -1:
                # Ưu tiên 2: Chia ở dấu xuống dòng (\n)
                split_idx = text.rfind('\n', 0, max_len)
            if split_idx == -1:
                # Ưu tiên 3: Chia ở dấu cách
                split_idx = text.rfind(' ', 0, max_len)
            if split_idx == -1:
                split_idx = max_len
            parts.append(text[:split_idx].strip())
            text = text[split_idx:].strip()
        return parts

    reply_text, model_used, relevant_results = ask_dhtn_qa(message.chat.id, question)
    if reply_text:
        # Tự động phát hiện các hình ảnh liên quan từ NỘI DUNG RAG chunks VÀ reply_text
        # AI model có thể giữ hoặc không giữ nhãn "Hình N" nên ta quét cả hai nguồn
        matched_images = []
        seen_images = set()  # Tránh gửi trùng ảnh
        sources_with_images = set()  # Theo dõi sources đã có ảnh
        
        # Bước 1: Quét "Hình N" trong CÂU TRẢ LỜI AI (nếu AI giữ nhãn)
        for match in re.finditer(r'Hình\s+(\d+)', reply_text, re.IGNORECASE):
            hinh_num = match.group(1)
            hinh_key = f"Hình {hinh_num}"
            for score, chunk in relevant_results:
                source = chunk.get('source', '')
                if source in IMAGE_MAP_DATA and hinh_key in IMAGE_MAP_DATA[source]:
                    img_rel_path = IMAGE_MAP_DATA[source][hinh_key]
                    img_local_path = os.path.join(OUTPUT_DIR, img_rel_path)
                    if os.path.exists(img_local_path) and img_rel_path not in seen_images:
                        matched_images.append((hinh_key, img_local_path, img_rel_path))
                        seen_images.add(img_rel_path)
                        sources_with_images.add(source)
                        break
        
        # Bước 2: Quét "Hình N" trong NỘI DUNG RAG chunks (bổ sung thêm nếu chưa đủ)
        if len(matched_images) < 5:
            for score, chunk in relevant_results:
                source = chunk.get('source', '')
                if source not in IMAGE_MAP_DATA:
                    continue
                for match in re.finditer(r'Hình\s+(\d+)', chunk.get('text', '')):
                    hinh_num = match.group(1)
                    hinh_key = f"Hình {hinh_num}"
                    if hinh_key in IMAGE_MAP_DATA[source]:
                        img_rel_path = IMAGE_MAP_DATA[source][hinh_key]
                        img_local_path = os.path.join(OUTPUT_DIR, img_rel_path)
                        if os.path.exists(img_local_path) and img_rel_path not in seen_images:
                            matched_images.append((hinh_key, img_local_path, img_rel_path))
                            seen_images.add(img_rel_path)
                            sources_with_images.add(source)
                if len(matched_images) >= 5:
                    break
        
        # Bước 3: Fallback - nếu chưa tìm thấy ảnh nào, gửi Hình 1 từ mỗi source liên quan
        if not matched_images:
            for score, chunk in relevant_results:
                source = chunk.get('source', '')
                if source in IMAGE_MAP_DATA and source not in sources_with_images:
                    if "Hình 1" in IMAGE_MAP_DATA[source]:
                        img_rel_path = IMAGE_MAP_DATA[source]["Hình 1"]
                        img_local_path = os.path.join(OUTPUT_DIR, img_rel_path)
                        if os.path.exists(img_local_path) and img_rel_path not in seen_images:
                            matched_images.append(("Hình 1", img_local_path, img_rel_path))
                            seen_images.add(img_rel_path)
                            sources_with_images.add(source)
                if len(matched_images) >= 3:  # Giới hạn fallback 3 ảnh
                    break
        
        print(f"[Telegram QA] Matched images: {len(matched_images)}")


        # Chèn link ảnh nếu cấu hình SERVER_DOMAIN
        server_domain = os.environ.get('SERVER_DOMAIN', '').strip().rstrip('/')
        if server_domain and matched_images:
            for hinh_key, local_path, rel_path in matched_images:
                img_url = f"{server_domain}/{rel_path}"
                # Chuyển chữ "Hình X" thành link click được dạng Markdown
                reply_text = re.sub(rf'({hinh_key}\b)', r'[\1](' + img_url + ')', reply_text, flags=re.IGNORECASE)

        footnote = f"\n\n*Dựa trên kiến thức được đào tạo.*"
        full_msg = reply_text + footnote
        parts = split_message(full_msg, max_len=3800)
        total_parts = len(parts)
        for i, part in enumerate(parts, 1):
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    bot.reply_to(message, part, parse_mode='Markdown')
                    print(f"[Telegram QA] Đã gửi phần {i}/{total_parts} ({len(part)} ký tự)")
                    break
                except Exception:
                    try:
                        bot.reply_to(message, part)
                        print(f"[Telegram QA] Đã gửi phần {i}/{total_parts} ({len(part)} ký tự) [không Markdown]")
                        break
                    except Exception as e:
                        if attempt < max_retries:
                            print(f"[Telegram QA] Lỗi gửi phần {i}/{total_parts}, thử lại lần {attempt + 1}...")
                            time.sleep(1)
                        else:
                            print(f"[Telegram QA Error] Không thể gửi phần {i}/{total_parts} sau {max_retries + 1} lần thử: {e}")
            time.sleep(0.5)

        # Gửi trực tiếp ảnh đính kèm (nếu tìm thấy ảnh cục bộ)
        sent_images = set()
        for hinh_key, local_path, rel_path in matched_images:
            if local_path not in sent_images:
                try:
                    with open(local_path, 'rb') as photo_file:
                        bot.send_photo(message.chat.id, photo_file, caption=f"📸 Ảnh minh họa: {hinh_key}")
                    print(f"[Telegram QA] Đã gửi trực tiếp ảnh minh họa {hinh_key}")
                    sent_images.add(local_path)
                except Exception as e:
                    print(f"[Telegram Bot Error] Không thể gửi ảnh {hinh_key}: {e}")
                time.sleep(0.5)
    else:
        # Nếu cả AI đều lỗi/không trả lời được
        fallback = (
            "Tôi không hiểu yêu cầu này và hiện không thể trả lời thắc mắc của bạn.\n\n"
            "👉 Vui lòng gửi file PDF văn bản chỉ đạo để tôi soạn thảo công văn.\n"
            "👉 Hoặc hỏi rõ ràng về cách sử dụng hệ thống Điều hành tác nghiệp nhé."
        )
        bot.reply_to(message, fallback)

if __name__ == "__main__":
    if API_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN':
        print("[!] LỖI: Vui lòng điền API Token nhận từ @BotFather vào biến API_TOKEN ở dòng 19 trước khi chạy.")
        sys.exit(1)
        
    print("==================================================")
    print("🤖 Chuyên Viên số đang khởi động...")
    print("📌 Phiên bản: 1.0.3")
    print("Lắng nghe yêu cầu soạn thảo từ xa...")
    print("==================================================")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\nBot đã dừng hoạt động.")
        sys.exit(0)
