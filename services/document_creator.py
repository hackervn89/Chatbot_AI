"""
Document Creator Service — Soạn thảo công văn hành chính tự động từ ảnh chụp văn bản chỉ đạo.
Sử dụng Gemini Vision để phân tích và python-docx để điền biểu mẫu.
"""
import os
import re
import time
import json
from PIL import Image
from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY, GEMINI_MODELS, OUTPUT_DIR, REFERENCES_DIR, SERVER_DOMAIN,
    GEMINI_SYSTEM_PROMPT
)
from database import get_db_session
from models import FileMapping
from services.ai_engine import call_ai_json

# Import generate_document từ taovanban_khoidang.scripts
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "taovanban_khoidang", "scripts"))
try:
    from generate_docx import generate_document
except ImportError:
    # Fallback nếu đường dẫn imports khác
    try:
        from taovanban_khoidang.scripts.generate_docx import generate_document
    except ImportError:
        def generate_document(data, template_path, output_path):
            print("[Doc Creator] Warning: Không tìm thấy thư viện generate_document thực tế.")
            # Dummy fallback hoặc copy file
            import shutil
            shutil.copy(template_path, output_path)

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "taovanban_khoidang", "references", "cong_van_giao_viec_mau.docx")
if not os.path.exists(TEMPLATE_PATH):
    TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references", "cong_van_giao_viec_mau.docx")


def analyze_image_with_gemini(image_path: str) -> dict:
    """Sử dụng Gemini Vision để phân tích ảnh chụp văn bản chỉ đạo"""
    if not GEMINI_API_KEY:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY")
        
    try:
        img = Image.open(image_path)
    except Exception as e:
        raise RuntimeError(f"Không thể mở file ảnh: {e}")
        
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    for model_name in GEMINI_MODELS:
        try:
            print(f"[Doc Creator] Đang phân tích ảnh bằng mô hình: {model_name}")
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
                print(f"[Doc Creator] Phản hồi thiếu trường từ {model_name}")
        except Exception as e:
            print(f"[Doc Creator] Lỗi ở mô hình {model_name}: {e}")
            
    raise RuntimeError("Tất cả mô hình Gemini đều gặp lỗi hoặc trả về sai cấu trúc JSON.")


def normalize_agency_name(name: str) -> str:
    if not name:
        return ""
    val = name.strip().lower().replace("  ", " ")
    val = val.replace("uỷ", "ủy").replace("oà", "òa").replace("uý", "úy")
    return val


def determine_agency_2(title: str, first_page_text: str) -> str:
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
    
    if (has_giamsat and not is_mttq_giamsat) or is_ubkt_pctn or any(k in text for k in ["kiểm tra", "kỷ luật", "vi phạm", "suy thoái"]):
        return "Uỷ ban kiểm tra Đảng uỷ xã"
    if (has_pctn and not is_ubkt_pctn) or any(k in text for k in ["văn thư", "lưu trữ", "quy chế làm việc", "chương trình công tác"]):
        return "Văn phòng Đảng uỷ xã"
    if (has_tuyentruyen and not is_mttq_tuyentruyen) or any(k in text for k in ["tổ chức cán bộ", "quy hoạch", "nhân sự", "tuyên giáo", "dân vận"]):
        return "Ban Xây dựng Đảng"
    if is_mttq_giamsat or is_mttq_tuyentruyen or any(k in text for k in ["mặt trận tổ quốc", "mttq", "đoàn thanh niên", "hội phụ nữ", "cựu chiến binh"]):
        return "Uỷ ban Mặt trận Tổ quốc Việt Nam xã"
        
    return "Uỷ ban nhân dân xã"


def get_short_type(doc_type: str) -> str:
    """Lấy viết tắt thể loại văn bản"""
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


def get_short_title(title: str) -> str:
    """Rút gọn trích yếu nội dung để đặt tên file"""
    match = re.search(r'về\s+(.*)', title, re.IGNORECASE)
    if match:
        target = match.group(1).strip()
    else:
        target = re.sub(r'^(Thực hiện\s+|Triển khai\s+)', '', title, flags=re.IGNORECASE)

    words = target.split()
    if len(words) > 6:
        return " ".join(words[:6])
    return target


def upload_to_file_io(file_path: str) -> str:
    """Upload tệp lên file.io làm fallback tải về dùng một lần"""
    import requests
    try:
        with open(file_path, 'rb') as f:
            r = requests.post('https://file.io', files={'file': f}, timeout=15)
            if r.status_code == 200:
                return r.json().get('link')
    except Exception as e:
        print(f"[Doc Creator Error] Không thể upload lên file.io: {e}")
    return None


def generate_and_send_word_doc(chat_id: str, metadata: dict, sender_name: str) -> str:
    """Sinh văn bản Word từ dữ liệu phân tích và trả về nội dung tin nhắn kết quả"""
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

    # Sinh tên file Word
    short_type = get_short_type(doc_type)
    short_title = get_short_title(title)
    docx_filename = f"CV tham mưu {short_type} TU về {short_title}.docx"
    docx_filename = re.sub(r'[\\/*?:"<>|]', "", docx_filename)
    output_docx_path = os.path.join(OUTPUT_DIR, docx_filename)

    # Sinh tài liệu Word
    generate_document(data, TEMPLATE_PATH, output_docx_path)

    if os.path.exists(output_docx_path):
        # Lưu file mapping vào CSDL
        import uuid
        file_id = str(uuid.uuid4())
        
        db = get_db_session()
        try:
            # Xóa mapping cũ cùng tên file
            db.query(FileMapping).filter(FileMapping.filename == docx_filename).delete()
            mapping = FileMapping(file_id=file_id, filename=docx_filename)
            db.add(mapping)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[Doc Creator Error] Lỗi ghi file mapping vào CSDL: {e}")
        finally:
            db.close()
            
        server_domain = SERVER_DOMAIN.strip().rstrip('/')
        
        if server_domain:
            download_link = f"{server_domain}/download/{file_id}"
            link_desc = "tải trực tiếp từ server"
        else:
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
            return msg
        else:
            return "❌ Soạn văn bản thành công nhưng không thể tạo liên kết tải về."
    else:
        return "❌ Lỗi trong quá trình tạo tệp văn bản từ biểu mẫu Word."
