"""
Webhook Router — Xử lý webhook từ Zalo Bot Platform.
Hỗ trợ: Hỏi đáp RAG, OCR ảnh soạn công văn Word, Admin gửi tệp nạp tri thức.
"""
import os
import time
import requests
from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from config import ADMIN_ZALO_IDS, TEMP_DIR, ZALO_WEBHOOK_SECRET
from services.chat_engine import answer_question
from services.zalo_api import send_message, send_typing_action
from services.knowledge_manager import ingest_document
from services.document_creator import analyze_image_with_gemini, generate_and_send_word_doc

router = APIRouter()

def download_file_from_url(url: str, dest_path: str) -> bool:
    """Tải tệp từ một URL bất kỳ (Zalo server)"""
    try:
        response = requests.get(url, stream=True, timeout=20)
        if response.status_code == 200:
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
    except Exception as e:
        print(f"[Webhook Helper] Lỗi tải tệp: {e}")
    return False

def _process_zalo_payload(payload: dict):
    """Xử lý payload webhook Zalo trong background"""
    try:
        event_name = payload.get("event_name", "")
        message_data = payload.get("message", payload)
        
        # Nhận diện chat_id (ID phòng chat - có thể là Group ID hoặc User ID 1-1)
        chat_id = None
        if message_data.get("chat", {}).get("id"):
            chat_id = message_data["chat"]["id"]
        elif payload.get("sender", {}).get("id"):
            chat_id = payload["sender"]["id"]
        elif message_data.get("from", {}).get("id"):
            chat_id = message_data["from"]["id"]
        elif payload.get("sender_id"):
            chat_id = payload["sender_id"]
        elif payload.get("user_id"):
            chat_id = payload["user_id"]
            
        # Nhận diện sender_id (ID của người gửi cụ thể) để phân quyền Admin
        sender_id = None
        if payload.get("sender", {}).get("id"):
            sender_id = payload["sender"]["id"]
        elif message_data.get("from", {}).get("id"):
            sender_id = message_data["from"]["id"]
        elif payload.get("sender_id"):
            sender_id = payload["sender_id"]
        elif payload.get("user_id"):
            sender_id = payload["user_id"]
            
        if not sender_id:
            sender_id = chat_id
            
        if not chat_id:
            print("[Webhook Warning] Không xác định được chat_id từ payload.")
            return

        # Bỏ qua tin nhắn từ bot
        from_info = message_data.get("from", {})
        if from_info.get("is_bot", False):
            return

        display_name = from_info.get("display_name", "Người dùng Zalo")

        # 1. Xử lý trường hợp gửi file tài liệu để nạp tri thức (chỉ dành cho Admin)
        if event_name in ["user_send_file", "message.file.received"]:
            attachments = message_data.get("attachments", [])
            if attachments:
                file_payload = attachments[0].get("payload", {})
                file_url = file_payload.get("url")
                file_name = file_payload.get("name")
                
                # Kiểm tra phân quyền Admin bằng sender_id (User ID) thay vì chat_id (Group ID)
                if sender_id not in ADMIN_ZALO_IDS:
                    send_message(chat_id, "❌ Bạn không có quyền nạp tài liệu tri thức vào hệ thống.")
                    return
                    
                if file_url and file_name:
                    send_message(chat_id, f"📥 Đang tải tài liệu: {file_name}...")
                    
                    temp_file_path = os.path.join(TEMP_DIR, file_name)
                    if download_file_from_url(file_url, temp_file_path):
                        send_message(chat_id, "⚙️ Đang tiến hành phân tích văn bản và nạp tri thức RAG...")
                        
                        # Ingest document
                        result = ingest_document(
                            file_path=temp_file_path,
                            title=os.path.splitext(file_name)[0].replace('_', ' '),
                            category="core",
                            created_by=f"zalo_admin_{sender_id}"
                        )
                        
                        # Xóa file tạm
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                            
                        if result.get("status") == "success":
                            details = result.get("details", {})
                            send_message(
                                chat_id,
                                f"✅ Nạp tri thức thành công!\n"
                                f"📄 Tài liệu: {details.get('title')}\n"
                                f"🧩 Số chunks tri thức: {details.get('chunks')}\n"
                                f"📸 Số ảnh minh họa: {details.get('images')}"
                            )
                        else:
                            send_message(chat_id, f"❌ Nạp tri thức thất bại: {result.get('message')}")
                    else:
                        send_message(chat_id, "❌ Không thể tải file tài liệu từ Zalo Server.")
            return

        # 2. Xử lý tin nhắn hình ảnh (soạn thảo công văn hành chính)
        is_image_event = event_name in ["user_send_image", "message.image.received"]
        has_photo = "photo" in message_data or "photo_url" in message_data or message_data.get("attachments")
        
        photo_url = ""
        if is_image_event or has_photo:
            attachments = message_data.get("attachments", [])
            if attachments and attachments[0].get("type") == "image":
                payload_data = attachments[0].get("payload", {})
                photo_url = payload_data.get("url", "")
                
        if photo_url:
            send_message(chat_id, "📥 Đang nhận hình ảnh và tiến hành phân tích OCR...")
            send_typing_action(chat_id)
            
            temp_img_name = f"ocr_{sender_id}_{int(time.time())}.png"
            temp_img_path = os.path.join(TEMP_DIR, temp_img_name)
            
            if download_file_from_url(photo_url, temp_img_path):
                try:
                    # Phân tích ảnh chụp văn bản chỉ đạo bằng Gemini Vision
                    metadata = analyze_image_with_gemini(temp_img_path)
                    
                    # Soạn thảo và gửi văn bản Word
                    response_msg = generate_and_send_word_doc(chat_id, metadata, display_name)
                    send_message(chat_id, response_msg)
                except Exception as e:
                    send_message(chat_id, f"❌ Đã xảy ra lỗi khi phân tích ảnh: {str(e)}")
                finally:
                    if os.path.exists(temp_img_path):
                        os.remove(temp_img_path)
            else:
                send_message(chat_id, "❌ Không thể tải hình ảnh từ Zalo Server.")
            return

        # 3. Xử lý tin nhắn chữ thông thường (hỏi đáp RAG)
        text = message_data.get("text", "").strip()
        if not text:
            return

        print(f"[Webhook] Nhận tin nhắn từ {display_name}: {text[:80]}...")
        send_typing_action(chat_id)

        # Xác định người gửi có phải quản trị viên không (dựa trên Zalo User ID)
        is_admin = sender_id in ADMIN_ZALO_IDS

        reply, model_name, results = answer_question(
            chat_id=chat_id,
            question=text,
            platform="zalo",
            display_name=display_name,
            is_admin=is_admin
        )

        
        if reply:
            send_message(chat_id, reply)
        else:
            send_message(
                chat_id, 
                "Hiện tại tôi chưa thể trả lời câu hỏi này. Bạn vui lòng thử lại sau.\n\n"
                "👉 Để soạn thảo công văn giao việc, bạn hãy gửi ảnh chụp trang đầu văn bản chỉ đạo vào đây."
            )
            
    except Exception as e:
        print(f"[Webhook Log Error] Lỗi trong background task: {e}")

@router.post("/webhook/zalo")
async def zalo_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook endpoint tiếp nhận tin nhắn từ Zalo OA"""
    try:
        # Xác thực Secret Token (nếu đã cấu hình ZALO_WEBHOOK_SECRET).
        # Chỉ chặn khi secret được đặt để tránh làm gián đoạn bot khi env chưa cấu hình.
        if ZALO_WEBHOOK_SECRET:
            received_token = request.headers.get("X-Bot-Api-Secret-Token", "")
            if received_token != ZALO_WEBHOOK_SECRET:
                print("[Webhook Security] Từ chối request: Secret Token không hợp lệ.")
                return JSONResponse(status_code=403, content={"status": "forbidden"})

        payload = await request.json()
        
        # Đẩy luồng xử lý tin nhắn vào Background Tasks
        background_tasks.add_task(_process_zalo_payload, payload)
        
        return {"status": "received"}
    except Exception as e:
        print(f"[Webhook Error] Lỗi tiếp nhận Zalo Webhook: {e}")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
