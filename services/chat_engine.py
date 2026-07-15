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
    REFERENCES_DIR, ENABLE_WEB_SEARCH
)
from database import get_db_session
from models import ChatSession, ChatMessage
from services.rag_pipeline import hybrid_search, classify_question, is_chitchat, normalize_abbreviations
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
1. Phạm vi từ chối nghiệp vụ (Chỉ áp dụng cho thao tác phần mềm ĐHTN): Đối với các câu hỏi yêu cầu hướng dẫn thao tác cụ thể, các bước bấm nút, giao diện hoặc cấu hình kỹ thuật của phần mềm Điều hành tác nghiệp (ĐHTN) của cơ quan, bạn BẮT BUỘC chỉ được trả lời dựa trên Bộ Kiến Thức Nghiệp Vụ được cung cấp. Nếu Bộ Kiến Thức không đề cập hoặc trống, bạn phải trả lời trung thực câu mặc định: "Thông tin này chưa được cập nhật trong tài liệu hướng dẫn sử dụng ĐHTN của cơ quan. Vui lòng liên hệ cán bộ quản trị hoặc văn thư phụ trách để được hỗ trợ." Tuyệt đối KHÔNG tự suy diễn giao diện phần mềm.
2. Đối với câu hỏi về kiến thức chung, nghiệp vụ văn phòng và học thuật ngoài lề: Đối với các câu hỏi về kỹ năng hành chính văn phòng chung, nghiệp vụ văn thư lưu trữ chung, hướng dẫn viết lách, học thuật (như viết luận văn, phương pháp tham mưu văn bản hành chính chung, soạn thảo văn bản mẫu chung...), hoặc trò chuyện chit-chat, toán học, lập trình, thời tiết...: Bạn ĐƯỢC PHÉP sử dụng tri thức chuyên môn sâu rộng của mình để trả lời trực tiếp, đầy đủ, nhiệt tình và chính xác để hỗ trợ tối đa cho người dùng.
3. Phong cách ngôn ngữ: Lịch sự, nhã nhặn, cô đọng, chuẩn mực công vụ. Lược bỏ hoàn toàn mọi câu chào hỏi, giới thiệu học thuật rườm rà ở đầu tin nhắn (ví dụ: "Chào bạn, tôi sẽ hướng dẫn...") và các câu chúc ở cuối tin nhắn. Hãy trả lời trực tiếp ngay vào nội dung nghiệp vụ hoặc các bước thực hiện.
4. Khi hướng dẫn thao tác phần mềm, nếu tài liệu tham chiếu có đề cập đến hình ảnh minh họa (ví dụ: "Hình 1", "Hình 2"...), hãy giữ nguyên nhãn "Hình N" trong câu trả lời để hệ thống có thể tự động đính kèm ảnh minh họa tương ứng cho người dùng.
5. Quy tắc phản hồi theo phân cấp (Cực kỳ quan trọng để tránh tin nhắn quá dài): Nếu người dùng hỏi chung chung về một chủ đề lớn, một phân hệ lớn hoặc tiêu đề cấp 1/cấp 2 (Ví dụ: "Hướng dẫn quản lý văn bản đi", "Thao tác trên giao diện Trang chủ"...), bạn KHÔNG ĐƯỢC trả lời chi tiết tất cả các bước của mọi quy trình con. Thay vào đó, hãy trả lời tóm tắt tổng quan ngắn gọn (1-2 câu), sau đó LIỆT KÊ danh sách các quy trình/chức năng con tương ứng có trong tài liệu tham chiếu (Ví dụ: "Phân hệ này gồm các quy trình: 1. Xem danh sách dự thảo, 2. Xem lịch sử chỉnh sửa..."). Cuối cùng, hãy chủ động hỏi lại người dùng bằng câu: "Đồng chí muốn tôi hướng dẫn chi tiết quy trình nào ở trên?" để hướng dẫn họ chọn lựa.

6. Quy tắc chào hỏi và trò chuyện xã giao (RẤT QUAN TRỌNG để gần gũi, tự nhiên): Khi người dùng chỉ chào hỏi (xin chào, hi, chào bạn...), hỏi thăm sức khỏe, hoặc hỏi "bạn là ai": hãy trả lời NGẮN GỌN, ẤM ÁP, TỰ NHIÊN trong 1-2 câu. TUYỆT ĐỐI KHÔNG liệt kê các phân hệ/chức năng của phần mềm ĐHTN và KHÔNG chủ động hỏi "đồng chí cần hướng dẫn nghiệp vụ nào" khi người dùng mới chỉ chào. Khi cần giới thiệu bản thân, hãy diễn đạt gần gũi kiểu "Tôi là Chuyên viên số được tích hợp trí tuệ nhân tạo để hỗ trợ đồng chí trong công việc hằng ngày" — nhưng ĐA DẠNG cách diễn đạt mỗi lần, KHÔNG lặp lại y hệt một câu giới thiệu cố định giữa các lần trò chuyện. Với cùng một lời chào, hãy linh hoạt thay đổi câu chữ để cuộc trò chuyện không nhàm chán. Chỉ khi người dùng đặt câu hỏi nghiệp vụ cụ thể thì mới đi vào hướng dẫn.

Quy tắc định dạng tin nhắn Zalo/Telegram (CỰC KỲ QUAN TRỌNG để tin nhắn đẹp mắt, gọn gàng):
- KHÔNG sử dụng các tiêu đề ký tự Markdown như #, ##, ###, ----.
- KHÔNG sử dụng dòng trống liên tiếp (ví dụ: không dùng \n\n). Mỗi phân đoạn hoặc bước chỉ ngăn cách bằng đúng một dấu xuống dòng (\n) để tin nhắn không bị giãn cách quá rộng và lê thê trên điện thoại.
- Sử dụng các biểu tượng biểu cảm (emoji) hành chính như 🔹, 📌, ⚠️, ✅ ở đầu mỗi bước hoặc đầu dòng lưu ý để tạo điểm nhấn trực quan thay vì dùng gạch đầu dòng Markdown (- hoặc *).
- Sử dụng chữ in đậm bằng ký tự **...** để làm nổi bật tất cả các từ quan trọng (như tên nút bấm, chức năng, vai trò, phần mềm, menu, hoặc lưu ý). Ví dụ: **Ghi lại**, **Gửi trình**, **Lãnh đạo**, hệ thống **Điều hành tác nghiệp (ĐHTN)**, menu **Văn bản đi**, trạng thái **Chờ xử lý**, **Lưu ý:**. Bạn BẮT BUỘC phải thực hiện bôi đậm để tin nhắn chuyên nghiệp và dễ đọc lướt trên ứng dụng chat.

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

        history = []
        for r in reversed(rows):
            content = r.content
            # Làm sạch các footnote nếu lỡ bị lưu vào DB
            content = re.sub(r'\n*🤖 Trợ lý ảo - Văn phòng Đảng ủy Công Hải', '', content).strip()
            history.append({"role": r.role, "content": content})
        return history
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
    is_admin: bool = False,
    db: Session = None
) -> tuple:
    """
    Trả lời câu hỏi người dùng qua RAG + AI Engine.
    
    Args:
        is_admin: True nếu người gửi là quản trị viên (cho phép bot xưng hô/hỗ trợ riêng).

    Returns: (reply_text, model_name, relevant_results)
    """
    should_close = db is None
    if db is None:
        db = get_db_session()


    try:
        # 1. Get/create session
        session = get_or_create_session(platform, chat_id, display_name, db)
        history = get_chat_history(session.id, db)

        # 2. Phân loại câu hỏi.
        # Tối ưu: lọc chitchat bằng regex TRƯỚC để tránh gọi LLM classifier không cần thiết (tiết kiệm API).
        # Chuẩn hóa viết tắt (ĐHTN -> điều hành tác nghiệp) trước khi phân loại để tăng độ chính xác.
        if is_chitchat(question):
            question_type = "ngoài_lề"
            print(f"[Chat Engine] Regex nhận diện chitchat: '{question}' -> ngoài_lề (bỏ qua LLM classifier).")
        else:
            normalized_q = normalize_abbreviations(question)
            question_type = classify_question(normalized_q, history=history[-4:])
            print(f"[Chat Engine] LLM phân loại câu hỏi: '{question}' -> {question_type}")
        
        best_score = 0
        relevant_results = []
        
        if question_type == "nội_bộ":
            try:
                relevant_results = hybrid_search(db, question)
                if relevant_results:
                    best_score = relevant_results[0][0]
            except Exception as e:
                print(f"[Chat] Lỗi RAG search: {e}")
        else:
            print("[Chat Engine] Bỏ qua RAG search vì câu hỏi xã giao/ngoài lề.")

        # 2b. Phát hiện khoảng trống tri thức (Knowledge Gap): câu hỏi nghiệp vụ nội bộ
        # nhưng RAG không tìm thấy tài liệu đủ liên quan -> ghi log để admin bổ sung tài liệu.
        if question_type == "nội_bộ" and best_score < RAG_SCORE_MEDIUM:
            print(f"[Knowledge Gap] ⚠️ Câu hỏi nội bộ không có tài liệu phù hợp (score={best_score:.1f}): '{question[:120]}'")


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
            if ENABLE_WEB_SEARCH:
                web_snippets = _search_web(question)
                if web_snippets:
                    relevant_context += "\nThông tin từ Internet:\n"
                    for s in web_snippets:
                        relevant_context += f"- {s}\n"
            else:
                relevant_context += "\n[ENABLE_WEB_SEARCH=False] Bỏ qua thông tin bổ sung từ Internet.\n"
        else:
            # Điểm thấp → câu hỏi chung/chit-chat
            print(f"[RAG] Điểm thấp ({best_score:.1f}). Câu hỏi chung.")
            use_internal_kt = False
            if ENABLE_WEB_SEARCH:
                web_snippets = _search_web(question)
                if web_snippets:
                    relevant_context = "\nThông tin từ Internet:\n"
                    for s in web_snippets:
                        relevant_context += f"- {s}\n"
            else:
                relevant_context = "Không có tài liệu nội bộ phù hợp."

        # 4. Build prompt - Toàn bộ ngữ cảnh RAG chỉ lấy từ database động, loại bỏ file tĩnh KIENTHUC_CONTENT
        kt = relevant_context if use_internal_kt else "Không có tài liệu nội bộ phù hợp."
        system_prompt = QA_SYSTEM_PROMPT.format(kienthuc_content=kt)

        # Nếu người gửi là quản trị viên, bổ sung ghi chú vai trò để bot xưng hô phù hợp.
        if is_admin:
            admin_display = display_name or "Quản trị viên"
            system_prompt += (
                f"\n\n[GHI CHÚ NỘI BỘ] Người bạn đang trò chuyện là **{admin_display}** — "
                f"QUẢN TRỊ VIÊN của hệ thống. Hãy xưng hô trân trọng và có thể nhắc rằng đồng chí "
                f"có quyền nạp tài liệu tri thức mới bằng cách gửi tệp trực tiếp qua Zalo."
            )


        # 5. Call AI
        # Với câu chào hỏi/ngoài lề, nâng temperature để câu chữ đa dạng, tự nhiên hơn,
        # tránh lặp lại y hệt một câu giới thiệu cố định gây nhàm chán.
        ai_temperature = 0.9 if question_type == "ngoài_lề" else 0.5
        reply, model_name, response_time = call_ai(
            system_prompt=system_prompt,
            user_message=question,
            history=history,
            temperature=ai_temperature
        )

        if reply:
            # Xóa bỏ câu cảnh báo cũ nếu AI tự sinh từ tri thức để tránh lặp lại
            reply = re.sub(r'\(?Bạn cần kiểm tra lại thông tin trước khi sử dụng\.?\)?', '', reply, flags=re.IGNORECASE).strip()

            # Trích dẫn nguồn tài liệu khi câu trả lời dựa trên tri thức nội bộ (điểm RAG cao),
            # giúp người dùng tin cậy và tra cứu lại. Chỉ hiển thị các nguồn duy nhất.
            citation = ""
            if best_score >= RAG_SCORE_HIGH and relevant_results:
                unique_sources = []
                for _s, _c in relevant_results:
                    src = _c.get("source") or _c.get("doc_title")
                    if src and src not in unique_sources:
                        unique_sources.append(src)
                if unique_sources:
                    citation = "\n\n📚 Nguồn tham khảo: " + "; ".join(unique_sources[:3])

            footnote = f"\n\n🤖 Trợ lý ảo - Văn phòng Đảng ủy Công Hải"
            final_reply = reply + citation + footnote


            # Save messages
            rag_sources_list = [
                {"source": c["source"], "score": round(s, 1)}
                for s, c in relevant_results[:3]
            ] if relevant_results else []

            add_message(session.id, "user", question, db=db)
            add_message(
                session.id, "assistant", reply, # Lưu reply gốc (chưa có footnote)
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
