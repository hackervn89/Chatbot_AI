"""
Chat Engine — Xử lý hội thoại chính.
Kết hợp RAG pipeline + AI engine + session management.
"""
import time
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

import re

from config import (
    MAX_CHAT_HISTORY, RAG_SCORE_HIGH, RAG_SCORE_MEDIUM,
    REFERENCES_DIR
)
from database import get_db_session
from models import ChatSession, ChatMessage
from services.rag_pipeline import hybrid_search
from services.ai_engine import call_ai, call_gemini_with_grounding
from services.audit_logger import log_chat_action

import os

# ==================== SYSTEM PROMPTS ====================

KIENTHUC_PATH = os.path.join(REFERENCES_DIR, "kienthuc_dhtn.md")
KIENTHUC_CONTENT = ""

# Load kiến thức gốc khi khởi tạo
if os.path.exists(KIENTHUC_PATH):
    try:
        with open(KIENTHUC_PATH, 'r', encoding='utf-8') as f:
            KIENTHUC_CONTENT = f.read().strip()
        print(f"[Chat Engine] Đã tải kiến thức hệ thống ({len(KIENTHUC_CONTENT)} ký tự).")
    except Exception as e:
        print(f"[Chat Engine] Lỗi tải kiến thức: {e}")

QA_SYSTEM_PROMPT = """Bạn là Trợ lý ảo hành chính Đảng chuyên nghiệp tại Đảng ủy xã, hỗ trợ nghiệp vụ và vận hành phần mềm Điều hành tác nghiệp (ĐHTN).

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


# ==================== SESSION MANAGEMENT ====================

def get_or_create_session(
    platform: str,
    external_chat_id: str,
    display_name: str = "",
    db: Session = None
) -> ChatSession:
    """Lấy hoặc tạo phiên hội thoại"""
    should_close = db is None
    if db is None:
        db = get_db_session()

    try:
        session = db.query(ChatSession).filter(
            ChatSession.platform == platform,
            ChatSession.external_chat_id == str(external_chat_id)
        ).first()

        if not session:
            session = ChatSession(
                platform=platform,
                external_chat_id=str(external_chat_id),
                user_display_name=display_name
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        elif display_name and session.user_display_name != display_name:
            session.user_display_name = display_name
            db.commit()

        return session
    finally:
        if should_close:
            db.close()


def get_chat_history(session_id: int, db: Session = None) -> list:
    """Lấy lịch sử tin nhắn gần nhất của phiên"""
    should_close = db is None
    if db is None:
        db = get_db_session()

    try:
        rows = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.desc()).limit(MAX_CHAT_HISTORY).all()

        return [{"role": r.role, "content": r.content} for r in reversed(rows)]
    finally:
        if should_close:
            db.close()


def add_message(
    session_id: int,
    role: str,
    content: str,
    ai_model: str = "",
    rag_score: float = 0.0,
    rag_sources: list = None,
    response_time_ms: int = 0,
    db: Session = None
):
    """Lưu tin nhắn vào DB"""
    should_close = db is None
    if db is None:
        db = get_db_session()

    try:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            ai_model_used=ai_model,
            rag_score=rag_score,
            rag_sources=rag_sources or [],
            response_time_ms=response_time_ms
        )
        db.add(msg)

        # Update session stats
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.message_count = (session.message_count or 0) + 1
            session.last_activity = func.now()

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Chat] Lỗi lưu tin nhắn: {e}")
    finally:
        if should_close:
            db.close()


# ==================== MAIN QA FUNCTION ====================

def answer_question(
    chat_id: str,
    question: str,
    platform: str = "zalo",
    display_name: str = "",
    db: Session = None
) -> tuple:
    """
    Trả lời câu hỏi người dùng qua RAG + AI Engine.
    
    Returns: (reply_text, model_name, relevant_results)
    """
    should_close = db is None
    if db is None:
        db = get_db_session()

    try:
        # 1. Get/create session
        session = get_or_create_session(platform, chat_id, display_name, db)
        history = get_chat_history(session.id, db)

        # 2. RAG Search
        best_score = 0
        relevant_results = []
        
        try:
            relevant_results = hybrid_search(db, question)
            if relevant_results:
                best_score = relevant_results[0][0]
        except Exception as e:
            print(f"[Chat] Lỗi RAG search: {e}")

        # 3. Xây dựng context
        relevant_context = ""
        use_internal_kt = True

        if best_score >= RAG_SCORE_HIGH:
            # Điểm cao → dùng tri thức nội bộ
            print(f"[RAG] Điểm cao ({best_score:.1f}). Dùng tri thức nội bộ.")
            relevant_context = "\n\nTài liệu hướng dẫn chi tiết:\n"
            for idx, (score, chunk) in enumerate(relevant_results):
                relevant_context += f"--- Nguồn: {chunk['source']} ---\n{chunk['text']}\n"

        elif best_score >= RAG_SCORE_MEDIUM:
            # Điểm trung bình → kết hợp nội bộ + web
            print(f"[RAG] Điểm trung bình ({best_score:.1f}). Kết hợp nội bộ + search.")
            relevant_context = "\n\nTài liệu tham khảo nội bộ:\n"
            for idx, (score, chunk) in enumerate(relevant_results[:2]):
                relevant_context += f"--- {chunk['source']} ---\n{chunk['text']}\n"
            
            # Thêm web search
            web_snippets = _search_web(question)
            if web_snippets:
                relevant_context += "\nThông tin từ Internet:\n"
                for s in web_snippets:
                    relevant_context += f"- {s}\n"
        else:
            # Điểm thấp → câu hỏi chung/chit-chat
            print(f"[RAG] Điểm thấp ({best_score:.1f}). Câu hỏi chung.")
            use_internal_kt = False
            web_snippets = _search_web(question)
            if web_snippets:
                relevant_context = "\nThông tin từ Internet:\n"
                for s in web_snippets:
                    relevant_context += f"- {s}\n"

        # 4. Build prompt
        kt = KIENTHUC_CONTENT if use_internal_kt else "Không có tài liệu nội bộ phù hợp."
        system_prompt = QA_SYSTEM_PROMPT.format(kienthuc_content=kt + relevant_context)

        # 5. Call AI
        reply, model_name, response_time = call_ai(
            system_prompt=system_prompt,
            user_message=question,
            history=history
        )

        if reply:
            # Xóa bỏ câu cảnh báo cũ nếu AI tự sinh từ tri thức để tránh lặp lại
            reply = re.sub(r'\(?Bạn cần kiểm tra lại thông tin trước khi sử dụng\.?\)?', '', reply, flags=re.IGNORECASE).strip()

            footnote = f"\n\n🤖 Trợ lý ảo - Văn phòng Đảng ủy Công Hải"
            final_reply = reply + footnote

            # Save messages
            rag_sources_list = [
                {"source": c["source"], "score": round(s, 1)}
                for s, c in relevant_results[:3]
            ] if relevant_results else []

            add_message(session.id, "user", question, db=db)
            add_message(
                session.id, "assistant", final_reply,
                ai_model=model_name,
                rag_score=best_score,
                rag_sources=rag_sources_list,
                response_time_ms=response_time,
                db=db
            )

            # Audit log
            log_chat_action(session.id, actor=f"{platform}_user_{chat_id}", details={
                "question_preview": question[:100],
                "model": model_name,
                "rag_score": round(best_score, 1),
                "response_time_ms": response_time
            }, db=db)

            return final_reply, model_name, relevant_results

        return None, None, []

    except Exception as e:
        print(f"[Chat] Lỗi xử lý câu hỏi: {e}")
        return None, None, []
    finally:
        if should_close:
            db.close()


def _search_web(query: str, max_results: int = 3) -> list:
    """Tìm kiếm web qua DuckDuckGo"""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            if results:
                return [r["body"] for r in results if "body" in r]
    except Exception as e:
        print(f"[Chat] Web search error: {e}")
    return []
