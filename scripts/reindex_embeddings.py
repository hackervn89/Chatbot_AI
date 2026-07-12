"""
Re-index Script — Xóa toàn bộ embedding cũ (3072 chiều) và tạo lại embedding mới (768 chiều).
Sau đó tạo HNSW index cho vector search cực nhanh.

Chạy: docker exec chatbot-web python scripts/reindex_embeddings.py
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_session
from models import KnowledgeChunk, Document
from services.rag_pipeline import get_embeddings_batch
from config import EMBEDDING_DIMENSION
from sqlalchemy import text

def reindex_all():
    db = get_db_session()
    
    try:
        # 1. Drop old vector index if exists
        print(f"[Re-index] Cấu hình: EMBEDDING_DIMENSION = {EMBEDDING_DIMENSION}")
        
        # 2. Alter column dimension if needed
        print("[Re-index] Đang thay đổi kích thước cột embedding...")
        try:
            db.execute(text(f"ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSION})"))
            db.commit()
            print(f"[Re-index] Đã thay đổi cột embedding thành vector({EMBEDDING_DIMENSION}).")
        except Exception as e:
            db.rollback()
            print(f"[Re-index] Lưu ý ALTER COLUMN: {e}")
        
        # 3. Get all active documents
        docs = db.query(Document).filter(Document.is_active == True, Document.status == "active").all()
        print(f"[Re-index] Tổng: {len(docs)} documents cần xử lý lại.")
        
        # 4. Re-chunk and re-embed per document
        from services.rag_pipeline import semantic_chunk
        batch_size = 50
        processed = 0
        errors = 0
        
        for doc in docs:
            if not doc.raw_text:
                print(f"[Re-index] Doc ID={doc.id}: Không có nội dung raw_text. Bỏ qua.")
                continue
                
            # Xóa các chunks cũ của doc
            db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).delete()
            
            # Cắt chunks mới
            chunks = semantic_chunk(doc.raw_text)
            if not chunks:
                print(f"[Re-index] Doc ID={doc.id}: Không tạo được chunks từ raw_text. Bỏ qua.")
                continue
                
            print(f"\n[Re-index] Doc ID={doc.id}: {doc.title[:50]}... ({len(chunks)} chunks mới)")
            doc_inserted = 0
            
            for idx in range(0, len(chunks), batch_size):
                batch = chunks[idx:idx + batch_size]
                texts = [c["text"] for c in batch]
                
                try:
                    vectors = get_embeddings_batch(texts)
                    
                    for j, chunk_data in enumerate(batch):
                        vector = vectors[j] if j < len(vectors) else [0.0] * EMBEDDING_DIMENSION
                        chunk_obj = KnowledgeChunk(
                            document_id=doc.id,
                            chunk_index=idx + j,
                            text=chunk_data["text"],
                            embedding=vector,
                            chunk_metadata=chunk_data.get("metadata", {})
                        )
                        db.add(chunk_obj)
                        doc_inserted += 1
                    
                    db.commit()
                    processed += len(batch)
                    print(f"  Batch {idx//batch_size + 1}: {len(batch)} chunks OK (tổng doc: {doc_inserted}/{len(chunks)})")
                    
                    # Rate limit: 1 second between batches
                    time.sleep(1.0)
                    
                except Exception as e:
                    db.rollback()
                    errors += len(batch)
                    print(f"  Batch {idx//batch_size + 1}: LỖI - {e}")
            
            # Cập nhật số chunk
            doc.chunk_count = doc_inserted
            db.commit()
        
        print(f"\n[Re-index] Hoàn tất: {processed} chunks OK, {errors} chunks lỗi.")
        
        # 5. Create HNSW index
        if EMBEDDING_DIMENSION <= 2000:
            print(f"\n[Re-index] Tạo HNSW index (vector({EMBEDDING_DIMENSION}))...")
            try:
                db.execute(text("DROP INDEX IF EXISTS idx_chunks_embedding_hnsw"))
                db.execute(text("DROP INDEX IF EXISTS idx_chunks_embedding_ivfflat"))
                db.execute(text(f"""
                    CREATE INDEX idx_chunks_embedding_hnsw 
                    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) 
                    WITH (m = 16, ef_construction = 64)
                """))
                db.commit()
                print("[Re-index] ✅ HNSW index tạo thành công!")
            except Exception as e:
                db.rollback()
                print(f"[Re-index] Lỗi tạo HNSW: {e}")
        else:
            print(f"[Re-index] ⚠️ EMBEDDING_DIMENSION={EMBEDDING_DIMENSION} > 2000, không thể tạo HNSW index.")
        
        # 6. ANALYZE
        db.execute(text("ANALYZE knowledge_chunks"))
        db.commit()
        print("[Re-index] ANALYZE hoàn tất.")
        
    except Exception as e:
        print(f"[Re-index] Lỗi: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    reindex_all()
