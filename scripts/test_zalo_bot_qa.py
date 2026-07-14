import sys
import os

# Reconfigure encoding for Windows/Linux console to prevent Unicode errors
sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.chat_engine import answer_question
from database import SessionLocal

def run_tests():
    questions = [
        # 1. Câu hỏi tổng quan về hệ thống
        "Hệ thống điều hành tác nghiệp có những phân hệ quản lý chính nào?",
        
        # 2. Câu hỏi chi tiết về văn bản đi
        "Làm thế nào để thêm mới văn bản đi dự thảo?",
        
        # 3. Câu hỏi chi tiết về văn bản đến
        "Văn thư tiếp nhận văn bản liên thông vào sổ theo các bước nào?",
        
        # 4. Câu hỏi ngoài lề (kiến thức chung)
        "Thủ đô của Việt Nam là gì?",
        
        # 5. Câu hỏi ngoài lề (chitchat chào hỏi)
        "Xin chào bot, hôm nay bạn khỏe không?"
    ]
    
    db = SessionLocal()
    try:
        for idx, q in enumerate(questions, 1):
            print(f"\n==========================================")
            print(f"TEST CÂU HỎI {idx}: '{q}'")
            print(f"==========================================")
            
            # Gọi chat engine
            reply, model_name, relevant_results = answer_question(
                chat_id="test_user_123",
                question=q,
                platform="zalo",
                display_name="Người dùng thử nghiệm",
                db=db
            )
            
            print(f"\n[Thông tin phản hồi]")
            print(f"- Model sử dụng: {model_name}")
            if relevant_results:
                best_score = relevant_results[0][0]
                print(f"- Điểm RAG cao nhất: {best_score:.2f}")
                print(f"- Số lượng tài liệu tham chiếu khớp: {len(relevant_results)}")
                print(f"- Nguồn tài liệu khớp: {relevant_results[0][1]['source']}")
            else:
                print(f"- Điểm RAG: 0.0 (Bỏ qua RAG)")
                
            print(f"\n[Câu trả lời của Bot]:\n{reply}")
            
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
