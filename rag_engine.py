import os
import sys
from sqlalchemy import text
from sqlalchemy.orm import Session
from google import genai
from database import IS_POSTGRES
import models

# Cấu hình encoding cho Windows
sys.stdout.reconfigure(encoding='utf-8')

# Define custom dotenv loader to read .env file safely
def load_dotenv():
    script_dir = os.path.dirname(os.path.abspath(__file__))
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

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

def get_embedding(text_content: str) -> list:
    """Tạo vector embeddings 3072 chiều bằng Gemini API gemini-embedding-2"""
    if not GEMINI_API_KEY:
        print("[!] RAG Engine Warning: GEMINI_API_KEY chưa cấu hình. Trả về vector rỗng.")
        return [0.0] * 3072
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.embed_content(
            model="models/gemini-embedding-2",
            contents=text_content
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"[!] RAG Engine Error: Không thể tạo embedding: {e}")
        return [0.0] * 3072

def hybrid_search(db: Session, query: str, top_n: int = 5) -> list:
    """
    Thực hiện Hybrid Search (Tìm kiếm lai) trên PostgreSQL hoặc SQLite:
    - PostgreSQL: Kết hợp pgvector (Cosine similarity) + Postgres Full-Text Search (simple).
    - SQLite: Fallback về tìm kiếm từ khóa thô (LIKE) kết hợp ranking cơ bản.
    Trả về danh sách tuple: (score, chunk_dict) với chunk_dict chứa 'text' và 'source'.
    """
    if not query.strip():
        return []

    # 1. TRƯỜNG HỢP POSTGRESQL (PRODUCTION SERVER)
    if IS_POSTGRES:
        try:
            # Tạo vector embedding của câu hỏi
            query_vector = get_embedding(query)
            
            # Khởi tạo truy vấn SQL kết hợp:
            # - Dense Score: 1 - cosine_distance (độ tương đồng từ 0 đến 1)
            # - Sparse Score: ts_rank (điểm số trùng khớp từ khóa)
            # - Kết hợp có trọng số: 0.7 * Dense + 0.3 * Sparse
            sql_query = text("""
                WITH dense_search AS (
                    SELECT 
                        id, 
                        (1 - (embedding <=> :vector::vector)) as dense_score
                    FROM knowledge_chunks
                    ORDER BY embedding <=> :vector::vector
                    LIMIT 50
                ),
                sparse_search AS (
                    SELECT 
                        id, 
                        ts_rank_cd(to_tsvector('simple', text), plainto_tsquery('simple', :query)) as sparse_score
                    FROM knowledge_chunks
                    WHERE to_tsvector('simple', text) @@ plainto_tsquery('simple', :query)
                    ORDER BY sparse_score DESC
                    LIMIT 50
                )
                SELECT 
                    kc.id,
                    kc.text,
                    d.source,
                    COALESCE(ds.dense_score, 0) as dense_score,
                    COALESCE(ss.sparse_score, 0) as sparse_score,
                    (0.7 * COALESCE(ds.dense_score, 0) + 0.3 * COALESCE(ss.sparse_score, 0)) as combined_score
                FROM knowledge_chunks kc
                JOIN documents d ON kc.document_id = d.id
                LEFT JOIN dense_search ds ON kc.id = ds.id
                LEFT JOIN sparse_search ss ON kc.id = ss.id
                WHERE ds.id IS NOT NULL OR ss.id IS NOT NULL
                ORDER BY combined_score DESC
                LIMIT :top_n;
            """)
            
            # Chuyển đổi vector sang định dạng chuỗi '[f1, f2, ...]' để truyền vào postgres
            vector_str = f"[{','.join(map(str, query_vector))}]"
            
            results = db.execute(sql_query, {
                "vector": vector_str,
                "query": query,
                "top_n": top_n
            }).fetchall()
            
            formatted_results = []
            for r in results:
                formatted_results.append((
                    float(r.combined_score) * 100,  # Quy đổi thang điểm 100
                    {
                        "id": r.id,
                        "text": r.text,
                        "source": r.source
                    }
                ))
            return formatted_results
            
        except Exception as e:
            print(f"[!] PostgreSQL Hybrid Search Error: {e}. Fallback sang từ khóa cơ bản...")
            # Fallback nếu câu lệnh SQL phức tạp bị lỗi

    # 2. TRƯỜNG HỢP SQLITE (FALLBACK LOCAL)
    # Tìm kiếm từ khóa cơ bản dùng LIKE trong cơ sở dữ liệu và tính score đơn giản
    try:
        # Tách từ khóa để tìm kiếm
        words = [w.strip() for w in query.split() if len(w.strip()) > 1]
        if not words:
            words = [query]
            
        # Xây dựng câu truy vấn chứa LIKE cho từng từ khóa
        conditions = " OR ".join(["kc.text LIKE :w" + str(i) for i in range(len(words))])
        sql_query = text(f"""
            SELECT kc.id, kc.text, d.source
            FROM knowledge_chunks kc
            JOIN documents d ON kc.document_id = d.id
            WHERE {conditions}
            LIMIT 50
        """)
        
        params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
        results = db.execute(sql_query, params).fetchall()
        
        # Đánh giá điểm thủ công trên Python (dựa trên tần suất từ khóa)
        formatted_results = []
        for r in results:
            text_lower = r.text.lower()
            match_count = sum(1 for w in words if w.lower() in text_lower)
            score = (match_count / len(words)) * 100 if words else 0
            
            formatted_results.append((
                score,
                {
                    "id": r.id,
                    "text": r.text,
                    "source": r.source
                }
            ))
            
        # Sắp xếp theo score giảm dần
        formatted_results.sort(key=lambda x: x[0], reverse=True)
        return formatted_results[:top_n]
        
    except Exception as e:
        print(f"[!] SQLite Fallback Search Error: {e}")
        return []
