"""
Chat Engine — Xử lý hội thoại chính.
Kết hợp RAG pipeline + AI engine + session management.
"""
import time
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

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

QA_SYSTEM_PROMPT = """Bạn là Chuyên viên ảo hỗ trợ nghiệp vụ Hành chính Đảng và trợ lý đa nhiệm tại Đảng ủy xã.
Nhiệm vụ của bạn là giải đáp các thắc mắc của người dùng.

Quy tắc trả lời:
1. Đối với các câu hỏi về thao tác phần mềm Hệ thống Điều hành tác nghiệp (ĐHTN) hoặc Thủ tục hành chính (TTHC) Đảng: Bạn ưu tiên sử dụng thông tin chi tiết trong Bộ Kiến Thức Nghiệp Vụ được cung cấp dưới đây để trả lời chính xác các bước bấm nút, giao diện.
2. Đối với các quy trình nghiệp vụ Đảng chung (như quy trình chuyển sinh hoạt Đảng, thủ tục kết nạp Đảng, đảng phí...) hoặc khi tài liệu được cung cấp chưa có hướng dẫn chi tiết: Bạn hãy sử dụng kiến thức chuyên môn sâu rộng của mình để trả lời đầy đủ, cụ thể từng bước và đúng quy định.
3. Đối với các câu hỏi chung ngoài lề (trò chuyện, toán học, dịch thuật, lập trình, nấu ăn, thời tiết...): Trả lời trực tiếp, đầy đủ, nhiệt tình theo kiến thức chung.
4. Luôn giữ phong cách lịch sự, nhã nhặn, chuẩn mực công vụ Việt Nam.
5. Khi hướng dẫn phần mềm, giữ nguyên nhãn "Hình N" nếu tài liệu có đề cập.

Dưới đây là Bộ Kiến Thức Nghiệp Vụ:
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
            # 6. Tự động phát hiện các hình ảnh liên quan từ NỘI DUNG RAG chunks VÀ reply
            matched_images = []
            seen_images = set()
            sources_with_images = set()

            import models
            try:
                # Bước 1: Quét "Hình N" trong CÂU TRẢ LỜI AI (nếu AI giữ nhãn)
                for match in re.finditer(r'Hình\s+(\d+)', reply, re.IGNORECASE):
                    hinh_num = match.group(1)
                    hinh_key = f"Hình {hinh_num}"
                    for score, chunk in relevant_results:
                        source = chunk.get('source', '')
                        img_map = db.query(models.ImageMapping).join(models.Document).filter(
                            models.Document.source == source,
                            models.ImageMapping.hinh_key == hinh_key
                        ).first()
                        if img_map:
                            img_rel_path = img_map.img_rel_path
                            if img_rel_path not in seen_images:
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
                                if img_rel_path not in seen_images:
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
                                if img_rel_path not in seen_images:
                                    matched_images.append(("Hình 1", img_rel_path))
                                    seen_images.add(img_rel_path)
                                    sources_with_images.add(source)
                        if len(matched_images) >= 3:
                            break
            except Exception as e:
                print(f"[Chat] Lỗi truy vấn ảnh minh họa từ CSDL: {e}")

            # Chèn link ảnh nếu cấu hình SERVER_DOMAIN
            from config import SERVER_DOMAIN
            from services.document_creator import upload_to_file_io
            server_domain = SERVER_DOMAIN.strip().rstrip('/')
            image_links_text = ""
            
            if server_domain and matched_images:
                for hinh_key, rel_path in matched_images:
                    img_url = f"{server_domain}/{rel_path}"
                    reply = re.sub(rf'({hinh_key}\b)', r'[\1](' + img_url + ')', reply, flags=re.IGNORECASE)
            elif matched_images:
                # Fallback file.io
                image_links_text = "\n\n📷 Ảnh minh họa thao tác:\n"
                for hinh_key, rel_path in matched_images:
                    from config import OUTPUT_DIR
                    img_local_path = os.path.join(OUTPUT_DIR, rel_path)
                    try:
                        img_url = upload_to_file_io(img_local_path)
                        if img_url:
                            image_links_text += f"- {hinh_key}: {img_url}\n"
                    except Exception as e:
                        print(f"[Chat Error] Không thể upload ảnh {hinh_key} lên file.io: {e}")

            footnote = f"\n\n(Bạn cần kiểm tra lại thông tin trước khi sử dụng)"
            final_reply = reply + image_links_text + footnote

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
