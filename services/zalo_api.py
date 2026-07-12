"""
Zalo Bot Platform API Wrapper.
Đóng gói các thao tác gửi tin nhắn qua Zalo Bot API.
"""
import requests
from config import ZALO_API_TOKEN


import re

def clean_markdown_for_zalo(text: str) -> str:
    """Chuyển đổi cú pháp Markdown thành plain text phù hợp hiển thị trên Zalo OA"""
    if not text:
        return ""
        
    # 1. Chuyển đổi Markdown Link [text](url) -> text: url
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\1: \2', text)
    
    # 2. Loại bỏ dấu in đậm **text** -> text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    
    # 3. Loại bỏ dấu in nghiêng *text* hoặc _text_ -> text
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    
    # 4. Loại bỏ code inline `code` -> code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # 5. Loại bỏ code block ```code```
    text = re.sub(r'```[a-zA-Z]*\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
    
    # 6. Làm sạch ký tự heading #, ##, ### ở đầu dòng
    def replace_heading(match):
        heading_text = match.group(2).strip()
        return f"\n🔹 {heading_text.upper()}\n"
        
    text = re.sub(r'^(#+)\s*(.*)$', replace_heading, text, flags=re.MULTILINE)
    
    return text.strip()


def send_message(chat_id: str, text: str) -> dict:
    """
    Gửi tin nhắn text qua Zalo Bot API.
    Tự động chuyển đổi Markdown và chia nhỏ nếu tin nhắn > 2000 ký tự.
    
    Returns: dict kết quả API hoặc None nếu lỗi
    """
    if not ZALO_API_TOKEN:
        print("[Zalo API] Lỗi: ZALO_API_TOKEN chưa cấu hình.")
        return None

    # Làm sạch Markdown cho Zalo
    text = clean_markdown_for_zalo(text)

    # Chia nhỏ tin nhắn nếu quá dài
    max_len = 2000
    if len(text) <= max_len:
        return _send_single_message(chat_id, text)
    
    # Chia thông minh theo dòng
    parts = _split_message(text, max_len)
    last_result = None
    for i, part in enumerate(parts):
        result = _send_single_message(chat_id, part)
        print(f"[Zalo API] Đã gửi phần {i+1}/{len(parts)} ({len(part)} ký tự): {result}")
        last_result = result
        
    return last_result


def send_typing_action(chat_id: str):
    """Gửi trạng thái đang gõ (typing indicator)"""
    if not ZALO_API_TOKEN:
        return
    try:
        url = f"https://bot-api.zaloplatforms.com/bot{ZALO_API_TOKEN}/sendChatAction"
        requests.post(url, json={
            "chat_id": str(chat_id),
            "action": "typing"
        }, timeout=5)
    except Exception:
        pass


def _send_single_message(chat_id: str, text: str) -> dict:
    """Gửi một tin nhắn đơn"""
    url = f"https://bot-api.zaloplatforms.com/bot{ZALO_API_TOKEN}/sendMessage"
    payload = {
        "chat_id": str(chat_id),
        "text": text
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"[Zalo API] Lỗi gửi tin nhắn: {e}")
        return None


def _split_message(text: str, max_len: int) -> list:
    """Chia tin nhắn dài thành nhiều phần theo dòng"""
    lines = text.split('\n')
    parts = []
    current = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 cho \n
        if current_len + line_len > max_len and current:
            parts.append('\n'.join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        parts.append('\n'.join(current))

    return parts
