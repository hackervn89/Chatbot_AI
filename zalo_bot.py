import os
import sys
import re
import time
import requests
import json
from pypdf import PdfReader
from PIL import Image
from google import genai
from google.genai import types

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Resolve paths
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

# Detect project structure
if os.path.basename(script_dir) == "scripts":
    PROJECT_ROOT = os.path.dirname(script_dir)
    sys.path.append(script_dir)
else:
    PROJECT_ROOT = os.path.join(script_dir, "taovanban_khoidang")
    sys.path.append(os.path.join(PROJECT_ROOT, "scripts"))

from generate_docx import generate_document

# Configs
ZALO_API_TOKEN = os.environ.get('ZALO_API_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

GEMINI_MODELS = [
    "gemini-1.5-flash",
    "gemini-2.5-flash",
    "gemini-1.5-pro",
    "gemini-3.5-flash",
]

TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "references", "cong_van_giao_viec_mau.docx")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
TEMP_DIR = os.path.join(PROJECT_ROOT, "scripts", "temp")
MAP_FILE = os.path.join(TEMP_DIR, "file_map.json")
KIENTHUC_PATH = os.path.join(PROJECT_ROOT, "references", "kienthuc_dhtn.md")
IMAGE_MAP_PATH = os.path.join(OUTPUT_DIR, "images", "image_map.json")
IMAGE_MAP_DATA = {}

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

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
            print(f"[Zalo Bot] Đã tải bộ kiến thức hệ thống ĐHTN ({len(KIENTHUC_CONTENT)} ký tự).")
        except Exception as e:
            print(f"[Zalo Bot] Lỗi khi đọc file kiến thức: {e}")
    else:
        print(f"[Zalo Bot] Cảnh báo: Không tìm thấy tệp kiến thức tại: {KIENTHUC_PATH}")

    # 2. Tải hdsd_chunks.json (RAG)
    if os.path.exists(CHUNKS_PATH):
        try:
            with open(CHUNKS_PATH, 'r', encoding='utf-8') as f:
                CHUNKS_DATA = json.load(f)
            for chunk in CHUNKS_DATA:
                chunk["text_unsigned"] = remove_accents(chunk["text"].lower())
                chunk["source_unsigned"] = remove_accents(chunk["source"].lower())
            CHUNKS_IDFS = calculate_idfs(CHUNKS_DATA)
            print(f"[Zalo Bot] Đã tải RAG database ({len(CHUNKS_DATA)} chunks).")
        except Exception as e:
            print(f"[Zalo Bot] Lỗi khi tải RAG database: {e}")
    else:
        print(f"[Zalo Bot] Cảnh báo: Không tìm thấy tệp RAG tại: {CHUNKS_PATH}")

    # 3. Tải bản đồ hình ảnh
    if os.path.exists(IMAGE_MAP_PATH):
        try:
            with open(IMAGE_MAP_PATH, 'r', encoding='utf-8') as f:
                IMAGE_MAP_DATA = json.load(f)
            print(f"[Zalo Bot] Đã tải bản đồ hình ảnh ({len(IMAGE_MAP_DATA)} tài liệu).")
        except Exception as e:
            print(f"[Zalo Bot] Lỗi khi tải bản đồ hình ảnh: {e}")

load_knowledge_bases()

# Shared Prompts
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

DHTN_QA_SYSTEM_PROMPT = """Bạn là Chuyên viên ảo hỗ trợ nghiệp vụ Hành chính Đảng và trợ lý đa nhiệm tại Đảng ủy xã.
Nhiệm vụ của bạn là giải đáp các thắc mắc của người dùng.

Quy tắc trả lời:
1. Đối với các câu hỏi về thao tác phần mềm Hệ thống Điều hành tác nghiệp (ĐHTN) hoặc Thủ tục hành chính (TTHC) Đảng: Bạn ưu tiên sử dụng thông tin chi tiết trong Bộ Kiến Thức Nghiệp Vụ được cung cấp dưới đây để trả lời chính xác các bước bấm nút, giao diện.
2. Đối với các quy trình nghiệp vụ Đảng chung (như quy trình chuyển sinh hoạt Đảng, thủ tục kết nạp Đảng, đảng phí...) hoặc khi tài liệu được cung cấp chưa có hướng dẫn chi tiết: Bạn hãy sử dụng kiến thức chuyên môn sâu rộng của mình về Điều lệ Đảng, Quy định số 24-QĐ/TW, Hướng dẫn số 09-HD/BTCTW... để trả lời đầy đủ, cụ thể từng bước và đúng quy định của Đảng cho người dùng.
3. Luôn giữ phong cách hành văn lịch sự, nhã nhặn, chuẩn mực công vụ Việt Nam.
4. Khi hướng dẫn thao tác phần mềm, nếu tài liệu tham chiếu có đề cập đến hình ảnh minh họa (ví dụ: "Hình 1", "Hình 2"...), hãy giữ nguyên nhãn "Hình N" trong câu trả lời để hệ thống có thể tự động đính kèm ảnh minh họa tương ứng cho người dùng.

Dưới đây là Bộ Kiến Thức Nghiệp Vụ để bạn tham chiếu:
=== BẮT ĐẦU BỘ KIẾN THỨC ===
{kienthuc_content}
=== KẾT THÚC BỘ KIẾN THỨC ==="""

def download_gdrive_file(url, output_path):
    """Tải file PDF công khai từ Google Drive"""
    file_id = None
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
    else:
        match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        if match:
            file_id = match.group(1)
            
    if not file_id:
        return False
        
    download_url = f"https://docs.google.com/uc?export=download&id={file_id}"
    session = requests.Session()
    response = session.get(download_url, stream=True)
    
    token = None
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            token = value
            break
            
    if token:
        download_url += f"&confirm={token}"
        response = session.get(download_url, stream=True)
        
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    return False

def save_file_mapping(file_id, filename):
    """Lưu mapping giữa mã file ngắn và tên tệp tin thực tế vào Database"""
    from database import SessionLocal
    import models
    db = SessionLocal()
    try:
        # Xóa các mapping cũ của cùng file đó nếu có
        db.query(models.FileMapping).filter(models.FileMapping.filename == filename).delete()
        mapping = models.FileMapping(file_id=file_id, filename=filename)
        db.add(mapping)
        db.commit()
        print(f"[Zalo Bot] Đã lưu mapping file vào CSDL: {file_id} -> {filename}")
    except Exception as e:
        print(f"[Zalo Bot] Lỗi khi ghi file_map vào CSDL: {e}")
    finally:
        db.close()

MAX_HISTORY_LEN = 10  # 10 tin nhắn gần nhất (5 lượt hội thoại)

def get_chat_history(chat_id):
    """Lấy lịch sử hội thoại từ CSDL"""
    from database import SessionLocal
    import models
    db = SessionLocal()
    try:
        rows = db.query(models.ChatHistory).filter(models.ChatHistory.chat_id == str(chat_id))\
                 .order_by(models.ChatHistory.created_at.desc()).limit(MAX_HISTORY_LEN).all()
        history = [{"role": r.role, "content": r.content} for r in reversed(rows)]
        return history
    except Exception as e:
        print(f"[Zalo Bot Error] Lỗi đọc chat history từ DB: {e}")
        return []
    finally:
        db.close()

def add_chat_message(chat_id, role, content):
    """Lưu tin nhắn hội thoại mới vào CSDL"""
    from database import SessionLocal
    import models
    db = SessionLocal()
    try:
        msg = models.ChatHistory(chat_id=str(chat_id), role=role, content=content)
        db.add(msg)
        db.commit()
    except Exception as e:
        print(f"[Zalo Bot Error] Lỗi ghi chat history vào DB: {e}")
    finally:
        db.close()

def download_file_from_url(url, output_path):
    """Tải tệp từ một URL bất kỳ (dùng cho ảnh trên server Zalo)"""
    try:
        response = requests.get(url, stream=True, timeout=15)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
    except Exception as e:
        print(f"[Zalo API] Lỗi tải file từ URL: {e}")
    return False

def upload_to_file_io(file_path):
    """Tải tệp lên file.io và lấy link tải về dùng một lần (bảo mật)"""
    try:
        with open(file_path, 'rb') as f:
            r = requests.post('https://file.io', files={'file': f}, timeout=15)
            if r.status_code == 200:
                return r.json().get('link')
    except Exception as e:
        print(f"[!] Lỗi khi tải file lên file.io: {e}")
    return None

def save_file_mapping(file_id, filename):
    """Lưu mapping giữa mã file ngắn và tên tệp tin thực tế"""
    try:
        data = {}
        if os.path.exists(MAP_FILE):
            with open(MAP_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data[file_id] = filename
        with open(MAP_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[Zalo Bot] Đã lưu mapping file: {file_id} -> {filename}")
    except Exception as e:
        print(f"[Zalo Bot] Lỗi khi ghi file_map: {e}")

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

def ask_dhtn_qa(chat_id, question, db=None):
    """Trả lời thắc mắc của người dùng dựa trên bộ tri thức ĐHTN kết hợp RAG HDSD và giữ ngữ cảnh hội thoại, chỉ dùng DeepSeek làm mô hình chính"""
    if not KIENTHUC_CONTENT:
        return None, None, []
        
    history = get_chat_history(chat_id)
    best_score = 0
    relevant_results = []
    
    # Sử dụng database hybrid search để tìm kiếm tri thức
    should_close_db = False
    if db is None:
        from database import SessionLocal
        db = SessionLocal()
        should_close_db = True
        
    try:
        from rag_engine import hybrid_search
        relevant_results = hybrid_search(db, question, top_n=3)
        if relevant_results:
            best_score = relevant_results[0][0]
    except Exception as e:
        print(f"[Zalo Bot Error] Lỗi thực hiện Hybrid Search: {e}")
    finally:
        if should_close_db:
            db.close()
            
    # Lấy thông tin ngữ cảnh (Nội bộ hoặc Tìm kiếm Web)
    relevant_context = ""
    if best_score >= 35:
        print(f"[RAG] Điểm số nội bộ cao ({best_score:.1f}). Sử dụng tài liệu nghiệp vụ nội bộ.")
        relevant_context = "\n\nDưới đây là tài liệu hướng dẫn chi tiết trích từ HDSD hệ thống:\n"
        for idx, (score, chunk) in enumerate(relevant_results):
            relevant_context += f"--- Nguồn tài liệu: {chunk['source']} ---\n{chunk['text']}\n"
    else:
        print(f"[RAG] Điểm số nội bộ thấp ({best_score:.1f}). Đang tìm kiếm Web...")
        web_results = search_duckduckgo_free(question)
        if web_results:
            relevant_context = "\n\nDưới đây là thông tin tìm kiếm thời gian thực trên Internet về câu hỏi này:\n"
            for idx, snippet in enumerate(web_results):
                relevant_context += f"- Kết quả {idx+1}: {snippet}\n"
                
    system_prompt = DHTN_QA_SYSTEM_PROMPT.format(
        kienthuc_content=KIENTHUC_CONTENT + relevant_context
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
                        tools=tools_config if tools_config else None
                    ),
                )
                reply = response.text.strip()
                if reply:
                    add_chat_message(chat_id, "user", question)
                    add_chat_message(chat_id, "assistant", reply)
                    return reply, model_name, relevant_results
            except Exception as e:
                print(f"[QA] Lỗi gọi Gemini dự phòng: {e}")
                
    return None, None, []

def analyze_with_deepseek(text):
    """Phân tích văn bản sử dụng Deepseek Chat API (Có phí, ưu tiên hàng đầu)"""
    if not DEEPSEEK_API_KEY:
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
            if all(field in data for field in required_fields):
                data["model_used"] = "DeepSeek-V3"
                print("[+] Phân tích thành công bởi: DeepSeek-V3")
                return data
        else:
            print(f"[-] Deepseek API Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[-] Lỗi khi gọi Deepseek API: {e}")
    return None

def analyze_with_gemini(pdf_path):
    """Hàm trích xuất dữ liệu bằng Gemini API (Đọc PDF)"""
    if not GEMINI_API_KEY:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY")
        
    reader = PdfReader(pdf_path)
    first_page_text = reader.pages[0].extract_text() or ""
    last_page_text = reader.pages[-1].extract_text() or ""
    
    combined_text = first_page_text
    if last_page_text and last_page_text != first_page_text:
        combined_text += "\n\n--- TRANG CUỐI ---\n\n" + last_page_text
        
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    for model_name in GEMINI_MODELS:
        try:
            print(f"[Zalo API] Đang phân tích bằng mô hình: {model_name}")
            response = client.models.generate_content(
                model=model_name,
                contents=combined_text,
                config=types.GenerateContentConfig(
                    system_instruction=GEMINI_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            raw_text = response.text.strip()
            data = json.loads(raw_text)
            
            # Kiểm tra định dạng trường
            required_fields = ["doc_type", "number", "date", "authority", "title", "co_quan_2"]
            if all(field in data for field in required_fields):
                data["model_used"] = model_name
                return data
            else:
                print(f"[Zalo API] Phản hồi thiếu trường từ {model_name}")
        except Exception as e:
            print(f"[Zalo API] Lỗi ở mô hình {model_name}: {e}")
            
    raise RuntimeError("Tất cả mô hình Gemini đều gặp lỗi hoặc trả về sai cấu trúc JSON.")

def analyze_image_with_gemini(image_path):
    """Hàm trích xuất dữ liệu từ ảnh chụp trang đầu bằng Gemini API (Đa phương thức)"""
    if not GEMINI_API_KEY:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY")
        
    try:
        img = Image.open(image_path)
    except Exception as e:
        raise RuntimeError(f"Không thể mở file ảnh: {e}")
        
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    for model_name in GEMINI_MODELS:
        try:
            print(f"[Zalo API] Đang phân tích ảnh bằng mô hình: {model_name}")
            response = client.models.generate_content(
                model=model_name,
                contents=[img, GEMINI_SYSTEM_PROMPT],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            raw_text = response.text.strip()
            data = json.loads(raw_text)
            
            # Kiểm tra định dạng trường
            required_fields = ["doc_type", "number", "date", "authority", "title", "co_quan_2"]
            if all(field in data for field in required_fields):
                data["model_used"] = model_name
                return data
            else:
                print(f"[Zalo API] Phản hồi thiếu trường từ {model_name}")
        except Exception as e:
            print(f"[Zalo API] Lỗi ở mô hình {model_name}: {e}")
            
    raise RuntimeError("Tất cả mô hình Gemini đều gặp lỗi hoặc trả về sai cấu trúc JSON.")

def normalize_agency_name(name):
    if not name:
        return ""
    val = name.strip().lower().replace("  ", " ")
    val = val.replace("uỷ", "ủy").replace("oà", "òa").replace("uý", "úy")
    return val

def determine_agency_2(title, first_page_text):
    text = (title + " " + first_page_text).lower()
    text = text.replace("uỷ", "ủy").replace("oà", "òa").replace("uý", "úy")

    # Giám sát
    has_giamsat = "giám sát" in text
    is_mttq_giamsat = has_giamsat and any(k in text for k in ["phản biện xã hội", "cộng đồng", "của nhân dân"])
    
    # Phòng chống tham nhũng
    has_pctn = any(k in text for k in ["phòng chống tham nhũng", "tiêu cực", "lãng phí"])
    is_ubkt_pctn = has_pctn and any(k in text for k in ["kiểm tra", "kỷ luật", "đảng viên", "vi phạm"])
    
    # Tuyên truyền
    has_tuyentruyen = "tuyên truyền" in text
    is_mttq_tuyentruyen = has_tuyentruyen and any(k in text for k in ["vận động quần chúng", "vận động nhân dân"])
    
    if is_ubkt_giamsat := has_giamsat and not is_mttq_giamsat or is_ubkt_pctn or any(k in text for k in ["kiểm tra", "kỷ luật", "vi phạm", "suy thoái"]):
        return "Uỷ ban kiểm tra Đảng uỷ xã"
    if has_pctn and not is_ubkt_pctn or any(k in text for k in ["văn thư", "lưu trữ", "quy chế làm việc", "chương trình công tác"]):
        return "Văn phòng Đảng uỷ xã"
    if has_tuyentruyen and not is_mttq_tuyentruyen or any(k in text for k in ["tổ chức cán bộ", "quy hoạch", "nhân sự", "tuyên giáo", "dân vận"]):
        return "Ban Xây dựng Đảng"
    if is_mttq_giamsat or is_mttq_tuyentruyen or any(k in text for k in ["mặt trận tổ quốc", "mttq", "đoàn thanh niên", "hội phụ nữ", "cựu chiến binh"]):
        return "Uỷ ban Mặt trận Tổ quốc Việt Nam xã"
        
    return "Uỷ ban nhân dân xã"

def parse_pdf_metadata(pdf_path):
    reader = PdfReader(pdf_path)
    first_page_text = reader.pages[0].extract_text() or ""
    lines = [line.strip() for line in first_page_text.split('\n') if line.strip()]
    
    number = ""
    num_match = re.search(r'Số\s+([^\r\n]+)', first_page_text, re.IGNORECASE)
    if num_match:
        number = num_match.group(1).strip()
        
    date_str = ""
    date_match = re.search(r'ngày\s+(\d+)\s+tháng\s+(\d+)\s+năm\s+(\d+)', first_page_text, re.IGNORECASE)
    if date_match:
        d, m, y = date_match.groups()
        date_str = f"{int(d):02d}/{int(m):02d}/{y}"
        
    doc_type = "Kế hoạch"
    title = ""
    types = ["KẾ HOẠCH", "NGHỊ QUYẾT", "CHƯƠNG TRÌNH", "CHỈ THỊ", "QUY ĐỊNH", "QUYẾT ĐỊNH"]
    type_idx = -1
    for idx, line in enumerate(lines):
        if any(t in line.upper() for t in types):
            doc_type = line.title()
            type_idx = idx
            break
            
    if type_idx != -1:
        title_lines = []
        for idx in range(type_idx + 1, len(lines)):
            line = lines[idx]
            if line.startswith("---") or line.startswith("I.") or "mục đích" in line.lower():
                break
            title_lines.append(line)
        title = " ".join(title_lines).strip()
        
    title = re.sub(r'\s*\-+\s*$', '', title)
    
    authority = "Ban Thường vụ Tỉnh ủy"
    if "ban thường vụ tỉnh ủy" in first_page_text.lower():
        authority = "Ban Thường vụ Tỉnh ủy"
    elif "thường trực tỉnh ủy" in first_page_text.lower():
        authority = "Thường trực Tỉnh ủy"
    elif "tỉnh ủy" in first_page_text.lower():
        authority = "Tỉnh ủy"
        
    return doc_type, number, date_str, authority, title

def get_short_type(doc_type):
    """Lấy viết tắt thể loại văn bản."""
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
    """Rút gọn trích yếu nội dung để đặt tên file."""
    match = re.search(r'về\s+(.*)', title, re.IGNORECASE)
    if match:
        target = match.group(1).strip()
    else:
        target = re.sub(r'^(Thực hiện\s+|Triển khai\s+)', '', title, flags=re.IGNORECASE)

    words = target.split()
    if len(words) > 6:
        return " ".join(words[:6])
    return target

def split_message(text, max_len=1800):
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

def send_zalo_message(chat_id, text):
    """Gửi tin nhắn phản hồi qua Zalo hỗ trợ định dạng Markdown và tự động chia nhỏ nếu tin quá dài, có retry khi lỗi"""
    parts = split_message(text, max_len=1800)
    results = []
    total_parts = len(parts)
    for i, part in enumerate(parts, 1):
        if not part:
            continue
        url = f"https://bot-api.zaloplatforms.com/bot{ZALO_API_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": part,
            "parse_mode": "markdown"
        }
        max_retries = 3
        for attempt in range(max_retries):
            try:
                r = requests.post(url, json=payload, timeout=10)
                res_data = r.json()
                results.append(res_data)
                print(f"[Zalo API] Đã gửi phần {i}/{total_parts} ({len(part)} ký tự): {res_data}")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 1.5  # 1.5s, 3s, 4.5s
                    print(f"[Zalo API] Lỗi gửi phần {i}/{total_parts}, thử lại sau {wait_time}s... ({e})")
                    time.sleep(wait_time)
                else:
                    print(f"[Zalo API Error] Không thể gửi phần {i}/{total_parts} sau {max_retries} lần: {e}")
        # Chờ giữa các phần để tránh rate limit
        if i < total_parts:
            time.sleep(1.0)
    return results

def send_zalo_chat_action(chat_id, action="typing"):
    """Gửi trạng thái (như đang soạn tin nhắn) qua Zalo"""
    url = f"https://bot-api.zaloplatforms.com/bot{ZALO_API_TOKEN}/sendChatAction"
    payload = {
        "chat_id": chat_id,
        "action": action
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[Zalo API] Gửi chat action lỗi: {e}")

def generate_and_send_word_doc(chat_id, metadata, sender_name):
    """Sinh văn bản Word từ dữ liệu đã phân tích và gửi trả link tải trực tiếp"""
    doc_type = metadata["doc_type"]
    number = metadata["number"]
    date_str = metadata["date"]
    authority = metadata["authority"]
    title = metadata["title"]
    co_quan_2 = metadata["co_quan_2"]

    van_ban_cap_tren = f"{doc_type} số {number}, ngày {date_str} của {authority} về {title}"
    trich_yeu = f"V/v thực hiện {doc_type} số {number} ngày {date_str} của {authority}"

    data = {
        "van_ban_cap_tren": van_ban_cap_tren,
        "Ngay_den_han_1": "",
        "Co_quan_2": co_quan_2,
        "ngay_den_han_2": "",
        "TRICH_YEU_CONG_VAN": trich_yeu,
        "DANH_SACH_NOI_NHAN": ["Thường trực Đảng ủy", "Các chi bộ trực thuộc", "Lưu VPĐU"]
    }

    # Generate output filename following naming convention
    short_type = get_short_type(doc_type)
    short_title = get_short_title(title)
    docx_filename = f"CV tham mưu {short_type} TU về {short_title}.docx"
    docx_filename = re.sub(r'[\\/*?:"<>|]', "", docx_filename)
    output_docx_path = os.path.join(OUTPUT_DIR, docx_filename)

    # Generate document
    generate_document(data, TEMPLATE_PATH, output_docx_path)

    if os.path.exists(output_docx_path):
        # Tạo file ID ngắn gọn bằng phần dư epoch time
        file_id = f"f{int(time.time() * 1000) % 10000000}"
        save_file_mapping(file_id, docx_filename)
        
        server_domain = os.environ.get('SERVER_DOMAIN', '').strip().rstrip('/')
        
        if server_domain:
            download_link = f"{server_domain}/download/{file_id}"
            link_desc = "tải trực tiếp từ server"
        else:
            print("[Zalo Bot] SERVER_DOMAIN chưa cấu hình. Dùng fallback file.io...")
            download_link = upload_to_file_io(output_docx_path)
            link_desc = "link bảo mật dùng 1 lần"
            
        if download_link:
            msg = (
                f"📊 KẾT QUẢ PHÂN TÍCH (Dựa trên kiến thức được đào tạo):\n"
                f"• Loại văn bản: {doc_type}\n"
                f"• Số hiệu: {number}\n"
                f"• Ngày ban hành: {date_str}\n"
                f"• Cơ quan ban hành: {authority}\n"
                f"• Cơ quan tham mưu: {co_quan_2}\n\n"
                f"🚀 Đã tạo văn bản Word thành công!\n"
                f"📁 Tên file: {docx_filename}\n"
                f"🔗 Tải xuống tại đây ({link_desc}): {download_link}"
            )
            send_zalo_message(chat_id, msg)
        else:
            send_zalo_message(chat_id, "❌ Soạn văn bản thành công nhưng không thể tạo liên kết tải về.")
    else:
        send_zalo_message(chat_id, "❌ Lỗi trong quá trình tạo tệp văn bản từ biểu mẫu Word.")

def process_zalo_message(message):
    """Xử lý tin nhắn nhận được (chữ hoặc ảnh)"""
    print(f"[Zalo Bot Log] Nhận tin nhắn raw: {json.dumps(message, ensure_ascii=False)}")

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()
    sender_name = message.get("from", {}).get("display_name", "bạn")
    
    # Trích xuất photo_url
    photo_url = message.get("photo_url", "").strip()
    raw_photo = message.get("photo") if not photo_url else None
    
    if raw_photo and isinstance(raw_photo, str):
        photo_url = raw_photo.strip()
    elif raw_photo and isinstance(raw_photo, dict):
        photo_url = raw_photo.get("url", "").strip() or raw_photo.get("photo", "").strip()
    elif raw_photo and isinstance(raw_photo, list) and len(raw_photo) > 0:
        last_photo = raw_photo[-1]
        if isinstance(last_photo, dict):
            photo_url = last_photo.get("url", "").strip() or last_photo.get("photo", "").strip()
            
    attachments = message.get("attachments", [])
    if not photo_url and isinstance(attachments, list) and len(attachments) > 0:
        payload = attachments[0].get("payload", {})
        if isinstance(payload, dict):
            photo_url = payload.get("url", "").strip() or payload.get("thumbnailUrl", "").strip()
            
    if not chat_id:
        return
        
    # 1. Xử lý hình ảnh (Ảnh chụp trang đầu văn bản chỉ đạo) -> Quy trình soạn thảo công văn
    if photo_url:
        send_zalo_chat_action(chat_id, "typing")
        
        img_filename = f"zalo_ocr_{int(time.time())}.jpg"
        img_path = os.path.join(TEMP_DIR, img_filename)
        
        if not download_file_from_url(photo_url, img_path):
            send_zalo_message(chat_id, "❌ Không thể tải hình ảnh từ máy chủ Zalo. Vui lòng thử gửi lại.")
            return
            
        try:
            # Phân tích ảnh bằng Gemini
            metadata = analyze_image_with_gemini(img_path)
            
            # Xử lý tạo tài liệu Word và gửi link tải
            generate_and_send_word_doc(chat_id, metadata, sender_name)
            
        except Exception as e:
            send_zalo_message(chat_id, f"❌ Đã xảy ra lỗi khi phân tích ảnh: {str(e)}")
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)
        return

    # 2. Tất cả tin nhắn văn bản còn lại -> Chuyển sang Hỏi đáp nghiệp vụ (Q&A)
    if text:
        send_zalo_chat_action(chat_id, "typing")
        reply_text, model_used, relevant_results = ask_dhtn_qa(chat_id, text)
        
        if reply_text:
            # Tự động phát hiện các hình ảnh liên quan từ NỘI DUNG RAG chunks VÀ reply_text
            # AI model có thể giữ hoặc không giữ nhãn "Hình N" nên ta quét cả hai nguồn
            matched_images = []
            seen_images = set()  # Tránh gửi trùng ảnh
            sources_with_images = set()  # Theo dõi sources đã có ảnh
            
            # Bước 1: Quét "Hình N" trong CÂU TRẢ LỜI AI (nếu AI giữ nhãn)
            from database import SessionLocal
            import models
            
            db = SessionLocal()
            try:
                for match in re.finditer(r'Hình\s+(\d+)', reply_text, re.IGNORECASE):
                    hinh_num = match.group(1)
                    hinh_key = f"Hình {hinh_num}"
                    for score, chunk in relevant_results:
                        source = chunk.get('source', '')
                        
                        # Tra cứu ảnh trong CSDL
                        img_map = db.query(models.ImageMapping).join(models.Document).filter(
                            models.Document.source == source,
                            models.ImageMapping.hinh_key == hinh_key
                        ).first()
                        
                        if img_map:
                            img_rel_path = img_map.img_rel_path
                            img_local_path = os.path.join(OUTPUT_DIR, img_rel_path)
                            if os.path.exists(img_local_path) and img_rel_path not in seen_images:
                                matched_images.append((hinh_key, img_rel_path))
                                seen_images.add(img_rel_path)
                                sources_with_images.add(source)
                                break
                
                # Bước 2: Quét "Hình N" trong NỘI DUNG RAG chunks (bổ sung thêm nếu chưa đủ)
                if len(matched_images) < 5:
                    for score, chunk in relevant_results:
                        source = chunk.get('source', '')
                        for match in re.finditer(r'Hình\s+(\d+)', chunk.get('text', '')):
                            hinh_num = match.group(1)
                            hinh_key = f"Hình {hinh_num}"
                            
                            img_map = db.query(models.ImageMapping).join(models.Document).filter(
                                models.Document.source == source,
                                models.ImageMapping.hinh_key == hinh_key
                            ).first()
                            
                            if img_map:
                                img_rel_path = img_map.img_rel_path
                                img_local_path = os.path.join(OUTPUT_DIR, img_rel_path)
                                if os.path.exists(img_local_path) and img_rel_path not in seen_images:
                                    matched_images.append((hinh_key, img_rel_path))
                                    seen_images.add(img_rel_path)
                                    sources_with_images.add(source)
                        if len(matched_images) >= 5:
                            break
                
                # Bước 3: Fallback - nếu chưa tìm thấy ảnh nào, gửi Hình 1 từ mỗi source liên quan
                if not matched_images:
                    for score, chunk in relevant_results:
                        source = chunk.get('source', '')
                        if source not in sources_with_images:
                            img_map = db.query(models.ImageMapping).join(models.Document).filter(
                                models.Document.source == source,
                                models.ImageMapping.hinh_key == "Hình 1"
                            ).first()
                            
                            if img_map:
                                img_rel_path = img_map.img_rel_path
                                img_local_path = os.path.join(OUTPUT_DIR, img_rel_path)
                                if os.path.exists(img_local_path) and img_rel_path not in seen_images:
                                    matched_images.append(("Hình 1", img_rel_path))
                                    seen_images.add(img_rel_path)
                                    sources_with_images.add(source)
                        if len(matched_images) >= 3:  # Giới hạn fallback 3 ảnh
                            break
            except Exception as e:
                print(f"[Zalo Bot Error] Lỗi truy vấn ảnh minh họa từ CSDL: {e}")
            finally:
                db.close()
            
            print(f"[Zalo QA] Matched images: {len(matched_images)}")


            # Chèn link ảnh nếu cấu hình SERVER_DOMAIN
            server_domain = os.environ.get('SERVER_DOMAIN', '').strip().rstrip('/')
            image_links_text = ""
            if server_domain and matched_images:
                for hinh_key, rel_path in matched_images:
                    img_url = f"{server_domain}/{rel_path}"
                    # Chuyển chữ "Hình X" thành link click được dạng Markdown
                    reply_text = re.sub(rf'({hinh_key}\b)', r'[\1](' + img_url + ')', reply_text, flags=re.IGNORECASE)
            elif matched_images:
                # Nếu không có SERVER_DOMAIN riêng, tải lên file.io tạm thời để lấy link xem ảnh
                image_links_text = "\n\n📷 Ảnh minh họa thao tác:\n"
                for hinh_key, rel_path in matched_images:
                    img_local_path = os.path.join(OUTPUT_DIR, rel_path)
                    try:
                        img_url = upload_to_file_io(img_local_path)
                        if img_url:
                            image_links_text += f"- {hinh_key}: {img_url}\n"
                    except Exception as e:
                        print(f"[Zalo Bot Error] Không thể upload ảnh {hinh_key} lên file.io: {e}")

            footnote = f"\n\n(Bạn cần kiểm tra lại thông tin trước khi sử dụng)"
            send_zalo_message(chat_id, reply_text + image_links_text + footnote)
        else:
            # Nhắc nhở nếu lỗi hệ thống
            reply = (
                "Hiện tại tôi chưa thể trả lời câu hỏi này. Bạn vui lòng thử lại sau.\n\n"
                "👉 Để soạn thảo công văn giao việc, bạn hãy gửi ảnh chụp trang đầu văn bản chỉ đạo vào đây."
            )
            send_zalo_message(chat_id, reply)

def process_zalo_webhook_payload(payload):
    """
    Xử lý payload webhook từ Zalo Official Account.
    Hỗ trợ: tin nhắn text, tin nhắn ảnh, và tin nhắn gửi file tài liệu từ Admin để nạp tri thức.
    """
    print(f"[Zalo Webhook Log] Nhận payload: {json.dumps(payload, ensure_ascii=False)}")
    
    event_name = payload.get("event_name")
    sender_id = payload.get("sender", {}).get("id")
    if not sender_id:
        return
        
    # Tạo cấu trúc tin nhắn chuẩn để tương thích với process_zalo_message
    message = {
        "chat": {"id": sender_id},
        "from": {"display_name": "Người dùng Zalo"},
        "text": "",
        "photo_url": ""
    }
    
    msg_data = payload.get("message", {})
    
    # 1. Xử lý trường hợp Admin gửi file tài liệu để nạp tri thức
    if event_name == "user_send_file":
        attachments = msg_data.get("attachments", [])
        if attachments:
            file_payload = attachments[0].get("payload", {})
            file_url = file_payload.get("url")
            file_name = file_payload.get("name")
            
            # Kiểm tra phân quyền Admin (đọc cấu hình từ môi trường)
            admin_ids = [i.strip() for i in os.environ.get('ADMIN_ZALO_IDS', '').split(',') if i.strip()]
            if sender_id not in admin_ids:
                send_zalo_message(sender_id, "❌ Bạn không có quyền nạp tài liệu tri thức vào hệ thống.")
                return
                
            if file_url and file_name:
                send_zalo_message(sender_id, f"📥 Đang tải tài liệu: {file_name}...")
                
                # Tải file về thư mục tạm
                temp_file_path = os.path.join(TEMP_DIR, file_name)
                if download_file_from_url(file_url, temp_file_path):
                    send_zalo_message(sender_id, "⚙️ Đang tiến hành phân tích văn bản và nạp tri thức RAG...")
                    
                    from document_uploader import ingest_document_file
                    result = ingest_document_file(temp_file_path)
                    
                    # Xóa file tạm
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                        
                    if result.get("status") == "success":
                        details = result.get("details", {})
                        send_zalo_message(
                            sender_id,
                            f"✅ Nạp tri thức thành công!\n"
                            f"📄 Tài liệu: {details.get('title')}\n"
                            f"🧩 Số chunks tri thức: {details.get('chunks')}\n"
                            f"📸 Số ảnh minh họa: {details.get('images')}"
                        )
                    else:
                        send_zalo_message(sender_id, f"❌ Nạp tri thức thất bại: {result.get('message')}")
                else:
                    send_zalo_message(sender_id, "❌ Không thể tải file tài liệu từ Zalo Server.")
        return

    # 2. Chuẩn hóa các sự kiện text/image thông thường
    if event_name == "user_send_text":
        message["text"] = msg_data.get("text", "")
    elif event_name == "user_send_image":
        attachments = msg_data.get("attachments", [])
        if attachments:
            message["photo_url"] = attachments[0].get("payload", {}).get("url", "")
            
    # Chạy xử lý thông qua logic chung
    process_zalo_message(message)

def main():
    if not ZALO_API_TOKEN:
        print("[!] LỖI: Không tìm thấy ZALO_API_TOKEN trong môi trường.")
        sys.exit(1)
        
    print("==================================================")
    print("🤖 Zalo Bot Chuyên viên số đang chạy...")
    print("📌 Phiên bản: 1.1.0 (Rút gọn link + Q&A ĐHTN)")
    print("==================================================")
    
    # Xóa Webhook cũ để tránh xung đột với cơ chế getUpdates (Polling)
    url_delete_webhook = f"https://bot-api.zaloplatforms.com/bot{ZALO_API_TOKEN}/deleteWebhook"
    try:
        print("[Zalo API] Đang xóa Webhook cũ...")
        res = requests.post(url_delete_webhook, timeout=10)
        print(f"[Zalo API] Kết quả xóa Webhook: {res.text}")
    except Exception as e:
        print(f"[Zalo API] Lỗi khi gỡ bỏ Webhook: {e}")
        
    url_get_updates = f"https://bot-api.zaloplatforms.com/bot{ZALO_API_TOKEN}/getUpdates"
    
    while True:
        try:
            payload = {"timeout": 30}
            response = requests.post(url_get_updates, json=payload, timeout=35)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and data.get("ok") and data.get("result"):
                    update = data["result"]
                    event_name = update.get("event_name")
                    message = update.get("message", {})
                    
                    if event_name in ["message.text.received", "message.image.received"] or "text" in message or "photo" in message or "photo_url" in message:
                        process_zalo_message(message)
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nZalo Bot đã dừng.")
            break
        except Exception as e:
            if "Read timed out" not in str(e):
                print(f"[Zalo Bot Error] {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
