"""
RAG Pipeline — Chunking, Embedding, Hybrid Search, Reranking.
Pipeline 4 giai đoạn cho hệ thống RAG production.
"""
import os
import re
from sqlalchemy import text
from sqlalchemy.orm import Session
from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY, IS_POSTGRES, EMBEDDING_MODEL, EMBEDDING_DIMENSION,
    CHUNK_SIZE, CHUNK_OVERLAP, HYBRID_SEARCH_DENSE_WEIGHT,
    HYBRID_SEARCH_SPARSE_WEIGHT, SEARCH_TOP_K, RERANK_TOP_N
)

# ==================== EMBEDDING ====================

def get_embedding(text_content: str) -> list:
    """Tạo vector embedding bằng Gemini Embedding 2 (3072 chiều)"""
    if not GEMINI_API_KEY:
        print("[RAG] Warning: GEMINI_API_KEY chưa cấu hình. Trả về vector rỗng.")
        return [0.0] * EMBEDDING_DIMENSION
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text_content,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSION)
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"[RAG] Lỗi tạo embedding: {e}")
        return [0.0] * EMBEDDING_DIMENSION


def get_embeddings_batch(texts: list) -> list:
    """Tạo batch vector embeddings cho danh sách văn bản (tối đa 100 bản ghi)"""
    if not texts:
        return []
    if not GEMINI_API_KEY:
        print("[RAG] Warning: GEMINI_API_KEY chưa cấu hình. Trả về vector rỗng.")
        return [[0.0] * EMBEDDING_DIMENSION for _ in texts]
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSION)
        )
        return [emb.values for emb in response.embeddings]
    except Exception as e:
        print(f"[RAG] Lỗi tạo batch embedding: {e}")
        return [[0.0] * EMBEDDING_DIMENSION for _ in texts]


# ==================== CHUNKING ====================

def semantic_chunk(text_content: str, chunk_size: int = None, overlap: int = None) -> list:
    """
    Chia văn bản theo ngữ nghĩa (semantic chunking):
    - Phân tách văn bản thành các section dựa trên các heading Markdown (#, ##, ###...)
    - Các section tiêu đề rỗng (chỉ chứa dòng tiêu đề mà không có nội dung) sẽ không tạo chunk riêng,
      mà được dùng để làm ngữ cảnh phân cấp (context path) cho các section nội dung bên dưới.
    - Chèn ngữ cảnh tiêu đề cha vào đầu mỗi chunk để tránh mất ngữ cảnh khi tìm kiếm RAG.
    
    Returns: list of dict {'text': str, 'metadata': dict}
    """
    chunk_size = chunk_size or CHUNK_SIZE
    overlap = overlap or CHUNK_OVERLAP

    if not text_content.strip():
        return []

    lines = text_content.split('\n')
    
    # Giai đoạn 1: Phân tách thành các section theo heading Markdown
    sections = []
    current_section = None
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            # Đếm số lượng dấu # để xác định level
            level = len(stripped) - len(stripped.lstrip('#'))
            heading_text = stripped.lstrip('#').strip()
            
            if current_section:
                sections.append(current_section)
                
            current_section = {
                "level": level,
                "heading": heading_text,
                "raw_heading": line,
                "lines": [line]
            }
        else:
            if current_section is None:
                current_section = {
                    "level": 0,
                    "heading": "",
                    "raw_heading": "",
                    "lines": []
                }
            current_section["lines"].append(line)
            
    if current_section:
        sections.append(current_section)

    # Giai đoạn 2: Duyệt qua các section, duy trì cấu trúc phân cấp và sinh chunk
    chunks = []
    header_hierarchy = {}  # {level: heading_text}
    
    for section in sections:
        # Cập nhật cấu trúc phân cấp tiêu đề
        if section["level"] > 0:
            header_hierarchy[section["level"]] = section["heading"]
            # Loại bỏ các tiêu đề cấp thấp hơn (chỉ số level lớn hơn)
            for lvl in list(header_hierarchy.keys()):
                if lvl > section["level"]:
                    header_hierarchy.pop(lvl)
                    
        # Kiểm tra xem section này có nội dung thực tế không (loại bỏ dòng tiêu đề và các dòng trống)
        actual_content_lines = []
        for line in section["lines"]:
            if section["raw_heading"] and line == section["raw_heading"]:
                continue
            if line.strip():
                actual_content_lines.append(line)
                
        # Nếu section không có nội dung thực tế (chỉ là tiêu đề rỗng), bỏ qua không tạo chunk
        if not actual_content_lines:
            continue
            
        # Tạo context prefix từ các tiêu đề cha (các tiêu đề có level nhỏ hơn level hiện tại)
        context_parts = []
        for lvl in sorted(header_hierarchy.keys()):
            if lvl < section["level"]:
                context_parts.append(f"{'#' * lvl} {header_hierarchy[lvl]}")
        context_prefix = "\n".join(context_parts) + "\n\n" if context_parts else ""
        
        # Nội dung chính của section này (giữ nguyên tiêu đề của chính nó nếu có)
        section_text = "\n".join(section["lines"]).strip()
        
        # Nếu tổng độ dài bao gồm cả context prefix nhỏ hơn hoặc bằng chunk_size, tạo thành 1 chunk duy nhất
        if len(context_prefix + section_text) <= chunk_size:
            chunks.append({
                "text": (context_prefix + section_text).strip(),
                "metadata": {"heading": section["heading"]} if section["heading"] else {}
            })
            continue
            
        # Nếu vượt quá chunk_size, chia nhỏ theo các đoạn văn (paragraphs)
        paragraphs = [p.strip() for p in section_text.split('\n') if p.strip()]
        current_chunk_lines = []
        current_len = len(context_prefix)
        
        for para in paragraphs:
            para_len = len(para) + 1  # Cộng 1 cho ký tự xuống dòng
            # Nếu thêm đoạn văn này vào vượt quá chunk_size
            if current_len + para_len > chunk_size and current_chunk_lines:
                chunk_text = context_prefix + "\n".join(current_chunk_lines)
                chunks.append({
                    "text": chunk_text.strip(),
                    "metadata": {"heading": section["heading"]} if section["heading"] else {}
                })
                # Overlap: Giữ lại 1 hoặc 2 dòng cuối tùy thuộc số lượng dòng
                overlap_lines = current_chunk_lines[-2:] if len(current_chunk_lines) >= 2 else current_chunk_lines[-1:]
                current_chunk_lines = list(overlap_lines) + [para]
                current_len = len(context_prefix) + sum(len(l) + 1 for l in current_chunk_lines)
            else:
                current_chunk_lines.append(para)
                current_len += para_len
                
        if current_chunk_lines:
            chunk_text = context_prefix + "\n".join(current_chunk_lines)
            chunks.append({
                "text": chunk_text.strip(),
                "metadata": {"heading": section["heading"]} if section["heading"] else {}
            })

    return chunks


def normalize_abbreviations(query: str) -> str:
    """Chuẩn hóa từ viết tắt tiếng Việt đặc thù văn phòng Đảng trước khi tìm kiếm"""
    if not query:
        return ""
    
    # Từ điển viết tắt Đảng & Hành chính
    abbrev_dict = {
        r'\bdhtn\b': 'điều hành tác nghiệp',
        r'\bđhtn\b': 'điều hành tác nghiệp',
        r'\btthc\b': 'thủ tục hành chính',
        r'\bktgs\b': 'kiểm tra giám sát',
        r'\btccb\b': 'tổ chức cán bộ',
        r'\btg\b': 'tuyên giáo',
        r'\bdv\b': 'dân vận',
        r'\bvp\b': 'văn phòng'
    }
    
    normalized = query.lower()
    for pattern, replacement in abbrev_dict.items():
        normalized = re.sub(pattern, replacement, normalized)
        
    return normalized


def is_chitchat(query: str) -> bool:
    """Nhận diện nhanh các câu chào hỏi, cảm ơn, xã giao ngắn không chứa nghiệp vụ"""
    q = query.strip().lower()
    q = re.sub(r'[^\w\s]', '', q).strip()
    
    chitchat_patterns = [
        r'^xin chào$', r'^chào$', r'^chào bạn$', r'^chào bot$', r'^chào trợ lý$',
        r'^hello$', r'^hi$', r'^gút chóp$', r'^good$', r'^ok$', r'^okay$', r'^dạ$',
        r'^cảm ơn$', r'^cám ơn$', r'^thank$', r'^thanks$', r'^cảm ơn bạn$', r'^tạm biệt$',
        r'^bye$', r'^bạn là ai$', r'^tên bạn là gì$', r'^ai đây$'
    ]
    
    for pattern in chitchat_patterns:
        if re.match(pattern, q):
            return True
            
    # Nếu câu hỏi quá ngắn (dưới 2 từ) và không chứa từ khóa nghiệp vụ đặc thù
    words = q.split()
    if len(words) <= 2:
        nghiep_vu_keywords = {"đảng", "phí", "trình", "phần", "mềm", "văn", "bản", "ký", "duyệt", "dự", "thảo", "hồ", "sơ", "nhiệm", "vụ", "tác", "nghiệp", "đhtn", "lãnh", "đạo", "phòng"}
        if not any(w in nghiep_vu_keywords for w in words):
            return True
            
    return False


# ==================== HYBRID SEARCH ====================

def hybrid_search(db: Session, query: str, top_n: int = None) -> list:
    """
    Hybrid Search kết hợp Dense (pgvector cosine) + Sparse (Full-Text Search).
    Sử dụng Reciprocal Rank Fusion (RRF) để merge kết quả.
    
    Returns: list of (score, chunk_dict) sorted by relevance
    """
    top_n = top_n or SEARCH_TOP_K
    
    if not query.strip():
        return []

    # Nhận diện và bỏ qua RAG đối với chitchat xã giao
    if is_chitchat(query):
        print(f"[RAG] Phát hiện câu hỏi xã giao/chitchat: '{query}'. Bỏ qua RAG search.")
        return []

    # Chuẩn hóa viết tắt trước khi truy vấn vector và full-text search
    query = normalize_abbreviations(query)

    if IS_POSTGRES:
        return _postgres_hybrid_search(db, query, top_n)
    else:
        return _sqlite_keyword_search(db, query, top_n)


def _prepare_tsquery(query_str: str) -> str:
    """Chuẩn hóa query thành tsquery format dùng toán tử OR (|) để tăng độ khớp"""
    if not query_str:
        return ""
    # Làm sạch ký tự đặc biệt
    query_str = re.sub(r'[^\w\s]', ' ', query_str)
    words = [w.strip().lower() for w in query_str.split() if len(w.strip()) > 1]
    
    if not words:
        return ""
        
    # Lọc stop-word tiếng Việt phổ biến ở đầu câu hỏi
    stopwords = {"hướng", "dẫn", "chi", "tiết", "làm", "sao", "để", "quy", "trình", "cách", "như", "thế", "nào", "cho", "tôi", "hỏi", "hệ", "thống"}
    filtered_words = [w for w in words if w not in stopwords]
    
    if not filtered_words:
        filtered_words = words
        
    return " | ".join(filtered_words)


def _postgres_hybrid_search(db: Session, query: str, top_n: int) -> list:
    """PostgreSQL Hybrid Search: pgvector + Full-Text Search + RRF"""
    try:
        # Tạo embedding cho query
        query_vector = get_embedding(query)
        vector_str = f"[{','.join(map(str, query_vector))}]"
        
        # Chuẩn hóa tsquery dạng OR
        tsquery_val = _prepare_tsquery(query)
        
        # RRF (Reciprocal Rank Fusion) kết hợp dense + sparse
        sql_query = text("""
            WITH dense_search AS (
                SELECT 
                    kc.id,
                    ROW_NUMBER() OVER (ORDER BY embedding <=> cast(:vector as vector)) as rank_dense
                FROM knowledge_chunks kc
                JOIN documents d ON kc.document_id = d.id
                WHERE d.is_active = true 
                    AND (d.is_latest = true OR d.effective_date IS NULL)
                ORDER BY embedding <=> cast(:vector as vector)
                LIMIT 50
            ),
            sparse_search AS (
                SELECT 
                    kc.id,
                    ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(to_tsvector('simple', kc.text), to_tsquery('simple', :tsquery)) DESC
                    ) as rank_sparse
                FROM knowledge_chunks kc
                JOIN documents d ON kc.document_id = d.id
                WHERE d.is_active = true
                    AND (d.is_latest = true OR d.effective_date IS NULL)
                    AND to_tsvector('simple', kc.text) @@ to_tsquery('simple', :tsquery)
                ORDER BY rank_sparse
                LIMIT 50
            )
            SELECT 
                kc.id,
                kc.text,
                d.source,
                d.title as doc_title,
                d.category,
                kc.chunk_metadata,
                COALESCE(1.0 / (60 + ds.rank_dense), 0) as rrf_dense,
                COALESCE(1.0 / (60 + ss.rank_sparse), 0) as rrf_sparse,
                (COALESCE(1.0 / (60 + ds.rank_dense), 0) + COALESCE(1.0 / (60 + ss.rank_sparse), 0)) as rrf_score
            FROM knowledge_chunks kc
            JOIN documents d ON kc.document_id = d.id
            LEFT JOIN dense_search ds ON kc.id = ds.id
            LEFT JOIN sparse_search ss ON kc.id = ss.id
            WHERE ds.id IS NOT NULL OR ss.id IS NOT NULL
            ORDER BY rrf_score DESC
            LIMIT :top_n;
        """)

        results = db.execute(sql_query, {
            "vector": vector_str,
            "tsquery": tsquery_val,
            "top_n": top_n
        }).fetchall()

        formatted = []
        for r in results:
            formatted.append((
                float(r.rrf_score) * 1200,  # Scale để tương thích với ngưỡng HIGH(35)/MEDIUM(15) trong config
                {
                    "id": r.id,
                    "text": r.text,
                    "source": r.source,
                    "doc_title": r.doc_title,
                    "category": r.category,
                    "metadata": r.chunk_metadata or {}
                }
            ))
        return formatted

    except Exception as e:
        print(f"[RAG] PostgreSQL Hybrid Search Error: {e}")
        db.rollback()
        return _sqlite_keyword_search(db, query, top_n)


def _sqlite_keyword_search(db: Session, query: str, top_n: int) -> list:
    """SQLite fallback: tìm kiếm từ khóa cơ bản"""
    try:
        words = [w.strip() for w in query.split() if len(w.strip()) > 1]
        if not words:
            words = [query]

        conditions = " OR ".join([f"kc.text LIKE :w{i}" for i in range(len(words))])
        sql_query = text(f"""
            SELECT kc.id, kc.text, d.source, d.title as doc_title, d.category
            FROM knowledge_chunks kc
            JOIN documents d ON kc.document_id = d.id
            WHERE d.is_active = 1 AND ({conditions})
            LIMIT 50
        """)

        params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
        results = db.execute(sql_query, params).fetchall()

        formatted = []
        for r in results:
            text_lower = r.text.lower()
            match_count = sum(1 for w in words if w.lower() in text_lower)
            score = (match_count / len(words)) * 100 if words else 0
            formatted.append((
                score,
                {
                    "id": r.id,
                    "text": r.text,
                    "source": r.source,
                    "doc_title": r.doc_title,
                    "category": r.category,
                    "metadata": {}
                }
            ))

        formatted.sort(key=lambda x: x[0], reverse=True)
        return formatted[:top_n]

    except Exception as e:
        print(f"[RAG] SQLite Search Error: {e}")
        return []
