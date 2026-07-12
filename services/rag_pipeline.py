"""
RAG Pipeline — Chunking, Embedding, Hybrid Search, Reranking.
Pipeline 4 giai đoạn cho hệ thống RAG production.
"""
import os
import re
from sqlalchemy import text
from sqlalchemy.orm import Session
from google import genai

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
            contents=text_content
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"[RAG] Lỗi tạo embedding: {e}")
        return [0.0] * EMBEDDING_DIMENSION


# ==================== CHUNKING ====================

def semantic_chunk(text_content: str, chunk_size: int = None, overlap: int = None) -> list:
    """
    Chia văn bản theo ngữ nghĩa (semantic chunking):
    - Ưu tiên tách theo heading (###, ##, #) và dòng trống
    - Fallback: tách theo đoạn với overlap
    - Mỗi chunk chứa metadata: heading cha (nếu có)
    
    Returns: list of dict {'text': str, 'metadata': dict}
    """
    chunk_size = chunk_size or CHUNK_SIZE
    overlap = overlap or CHUNK_OVERLAP

    if not text_content.strip():
        return []

    lines = text_content.split('\n')
    
    # Giai đoạn 1: Tách thành các section theo heading
    sections = []
    current_section = {"heading": "", "lines": []}
    
    for line in lines:
        stripped = line.strip()
        # Phát hiện heading Markdown
        if stripped.startswith('#'):
            # Lưu section trước
            if current_section["lines"]:
                sections.append(current_section)
            current_section = {"heading": stripped.lstrip('#').strip(), "lines": []}
        else:
            current_section["lines"].append(line)
    
    if current_section["lines"]:
        sections.append(current_section)

    # Nếu không có heading → coi toàn bộ là 1 section
    if not sections:
        sections = [{"heading": "", "lines": lines}]

    # Giai đoạn 2: Chia mỗi section thành chunks với overlap
    chunks = []
    for section in sections:
        section_text = '\n'.join(section["lines"]).strip()
        if not section_text:
            continue

        paragraphs = [p.strip() for p in section_text.split('\n') if p.strip()]
        current_chunk_lines = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > chunk_size and current_chunk_lines:
                # Lưu chunk hiện tại
                chunk_text = '\n'.join(current_chunk_lines)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {"heading": section["heading"]} if section["heading"] else {}
                })
                # Overlap: giữ lại 2 dòng cuối
                overlap_lines = current_chunk_lines[-2:] if len(current_chunk_lines) >= 2 else current_chunk_lines[-1:]
                current_chunk_lines = list(overlap_lines) + [para]
                current_len = sum(len(l) for l in current_chunk_lines)
            else:
                current_chunk_lines.append(para)
                current_len += para_len

        if current_chunk_lines:
            chunk_text = '\n'.join(current_chunk_lines)
            chunks.append({
                "text": chunk_text,
                "metadata": {"heading": section["heading"]} if section["heading"] else {}
            })

    return chunks


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

    if IS_POSTGRES:
        return _postgres_hybrid_search(db, query, top_n)
    else:
        return _sqlite_keyword_search(db, query, top_n)


def _postgres_hybrid_search(db: Session, query: str, top_n: int) -> list:
    """PostgreSQL Hybrid Search: pgvector + Full-Text Search + RRF"""
    try:
        # Tạo embedding cho query
        query_vector = get_embedding(query)
        vector_str = f"[{','.join(map(str, query_vector))}]"
        
        # RRF (Reciprocal Rank Fusion) kết hợp dense + sparse
        # RRF score = 1/(k+rank_dense) + 1/(k+rank_sparse), k=60 (constant)
        sql_query = text("""
            WITH dense_search AS (
                SELECT 
                    id,
                    ROW_NUMBER() OVER (ORDER BY embedding <=> cast(:vector as vector)) as rank_dense
                FROM knowledge_chunks kc
                JOIN documents d ON kc.document_id = d.id
                WHERE d.is_active = true
                ORDER BY embedding <=> cast(:vector as vector)
                LIMIT 50
            ),
            sparse_search AS (
                SELECT 
                    kc.id,
                    ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(to_tsvector('simple', kc.text), plainto_tsquery('simple', :query)) DESC
                    ) as rank_sparse
                FROM knowledge_chunks kc
                JOIN documents d ON kc.document_id = d.id
                WHERE d.is_active = true
                    AND to_tsvector('simple', kc.text) @@ plainto_tsquery('simple', :query)
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
            "query": query,
            "top_n": top_n
        }).fetchall()

        formatted = []
        for r in results:
            formatted.append((
                float(r.rrf_score) * 100,  # Scale để dễ đọc
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
