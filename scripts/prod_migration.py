"""Production migration: indexes, constraints, defaults"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import get_db_session, IS_POSTGRES
from config import EMBEDDING_DIMENSION

def run_production_migration():
    print("[Prod Migration] Starting production database migration...")
    db = get_db_session()
    
    try:
        if IS_POSTGRES:
            # GIN index for FTS
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chunks_text_fts 
                ON knowledge_chunks USING gin (to_tsvector('simple', text));
            """))
            print("[Prod Migration] ✓ GIN FTS index created")
            
            # B-tree indexes
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON knowledge_chunks (document_id);"))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_is_active ON documents (is_active);"))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs (created_at DESC);"))
            print("[Prod Migration] ✓ B-tree indexes created")
            
            # HNSW vector index (if dimension <= 2000)
            if EMBEDDING_DIMENSION <= 2000:
                db.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
                    ON knowledge_chunks
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                """))
                print(f"[Prod Migration] ✓ HNSW index created ({EMBEDDING_DIMENSION}D)")
            else:
                print(f"[Prod Migration] ⚠ Skipping HNSW (dimension {EMBEDDING_DIMENSION} > 2000)")
            
            db.commit()
            print("[Prod Migration] ✅ All migrations completed successfully")
        else:
            print("[Prod Migration] SQLite detected - skipping PostgreSQL-specific indexes")
    
    except Exception as e:
        print(f"[Prod Migration] ❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_production_migration()
