"""
AI Engine — Switchable giữa DeepSeek và Gemini.
DeepSeek là primary, Gemini là fallback tự động.
"""
import time
import requests
from google import genai
from google.genai import types

from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT,
    GEMINI_API_KEY, GEMINI_MODELS, AI_PRIMARY_ENGINE
)


def call_ai(
    system_prompt: str,
    user_message: str,
    history: list = None,
    temperature: float = 0.5,
    max_tokens: int = 2048
) -> tuple:
    """
    Gọi AI Engine theo thứ tự ưu tiên với fallback chain rõ ràng.
    
    Args:
        system_prompt: System prompt (instruction)
        user_message: Tin nhắn người dùng
        history: Lịch sử hội thoại [{"role": "user/assistant", "content": "..."}]
        temperature: Mức sáng tạo (0-1)
        max_tokens: Giới hạn token đầu ra
        
    Returns: (reply_text, model_name, response_time_ms)
    """
    history = history or []
    start_time = time.time()
    
    # Xác định thứ tự gọi dựa trên AI_PRIMARY_ENGINE
    call_order = []
    if AI_PRIMARY_ENGINE == 'deepseek' and DEEPSEEK_API_KEY:
        call_order.append(('deepseek', _call_deepseek))
        if GEMINI_API_KEY:
            call_order.append(('gemini', _call_gemini))
    elif AI_PRIMARY_ENGINE == 'gemini' and GEMINI_API_KEY:
        call_order.append(('gemini', _call_gemini))
        if DEEPSEEK_API_KEY:
            call_order.append(('deepseek', _call_deepseek))
    else:
        # Fallback: thử cả hai theo thứ tự mặc định
        if DEEPSEEK_API_KEY:
            call_order.append(('deepseek', _call_deepseek))
        if GEMINI_API_KEY:
            call_order.append(('gemini', _call_gemini))
    
    # Thử gọi theo thứ tự
    for engine_name, call_func in call_order:
        if engine_name == 'deepseek':
            result = call_func(system_prompt, user_message, history, temperature, max_tokens)
        else:  # gemini
            result = call_func(system_prompt, user_message, history, temperature)
        
        if result:
            elapsed = int((time.time() - start_time) * 1000)
            return result[0], result[1], elapsed
    
    return None, None, 0


def call_ai_json(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.1
) -> tuple:
    """
    Gọi AI Engine và yêu cầu trả JSON (dùng cho phân tích văn bản).
    
    Returns: (json_string, model_name)
    """
    # Thử DeepSeek (hỗ trợ JSON mode native)
    if DEEPSEEK_API_KEY:
        result = _call_deepseek_json(system_prompt, user_message, temperature)
        if result:
            return result

    # Fallback Gemini
    if GEMINI_API_KEY:
        result = _call_gemini_json(system_prompt, user_message, temperature)
        if result:
            return result

    return None, None


# ==================== DEEPSEEK IMPLEMENTATION ====================

def _call_deepseek(
    system_prompt: str,
    user_message: str,
    history: list,
    temperature: float,
    max_tokens: int
) -> tuple:
    """Gọi DeepSeek Chat API"""
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    try:
        print(f"[AI] Đang gọi DeepSeek ({DEEPSEEK_MODEL})...")
        response = requests.post(
            DEEPSEEK_API_URL, json=payload, headers=headers, timeout=DEEPSEEK_TIMEOUT
        )
        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"].strip()
            if reply:
                print(f"[AI] DeepSeek trả lời thành công ({len(reply)} ký tự).")
                return reply, f"DeepSeek-{DEEPSEEK_MODEL}"
        else:
            print(f"[AI] DeepSeek lỗi HTTP {response.status_code}: {response.text[:200]}")
    except requests.exceptions.ConnectTimeout:
        print("[AI] DeepSeek connection timeout. Chuyển sang Gemini...")
    except requests.exceptions.ReadTimeout:
        print("[AI] DeepSeek read timeout. Chuyển sang Gemini...")
    except Exception as e:
        print(f"[AI] Lỗi DeepSeek: {e}. Chuyển sang Gemini...")
    
    return None


def _call_deepseek_json(
    system_prompt: str,
    user_message: str,
    temperature: float
) -> tuple:
    """Gọi DeepSeek với JSON response format"""
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "response_format": {"type": "json_object"},
        "temperature": temperature
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    try:
        print("[AI] Đang gọi DeepSeek (JSON mode)...")
        response = requests.post(
            DEEPSEEK_API_URL, json=payload, headers=headers, timeout=DEEPSEEK_TIMEOUT
        )
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"].strip()
            return content, f"DeepSeek-{DEEPSEEK_MODEL}"
    except Exception as e:
        print(f"[AI] Lỗi DeepSeek JSON: {e}")
    
    return None


# ==================== GEMINI IMPLEMENTATION ====================

def _call_gemini(
    system_prompt: str,
    user_message: str,
    history: list,
    temperature: float,
    tools_config: list = None
) -> tuple:
    """Gọi Gemini API với fallback qua nhiều models"""
    client = genai.Client(api_key=GEMINI_API_KEY)

    # Build contents
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
            parts=[types.Part.from_text(text=user_message)]
        )
    )

    for model_name in GEMINI_MODELS:
        try:
            print(f"[AI] Đang gọi Gemini ({model_name})...")
            response = client.models.generate_content(
                model=model_name,
                contents=gemini_contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    tools=tools_config if tools_config else None
                ),
            )
            if response and response.text:
                reply = response.text.strip()
                print(f"[AI] Gemini ({model_name}) trả lời thành công ({len(reply)} ký tự).")
                return reply, model_name
        except Exception as e:
            print(f"[AI] Lỗi Gemini ({model_name}): {e}")

    return None


def call_gemini_with_grounding(
    system_prompt: str,
    user_message: str,
    history: list = None,
    temperature: float = 0.5
) -> tuple:
    """Gọi Gemini kèm Google Search Grounding — dùng cho câu hỏi cần thông tin thời gian thực"""
    if not GEMINI_API_KEY:
        return None, None
    
    google_search_tool = types.Tool(google_search=types.GoogleSearch())
    return _call_gemini(
        system_prompt, user_message, history or [],
        temperature, tools_config=[google_search_tool]
    )


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
