-- init.sql: Khởi tạo PostgreSQL cho hệ thống RAG
-- Chạy tự động khi container PostgreSQL được tạo lần đầu

-- 1. Kích hoạt extension pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Ghi chú: SQLAlchemy sẽ tự tạo các bảng khi ứng dụng khởi chạy (Base.metadata.create_all)
-- File này chỉ đảm bảo extension pgvector có sẵn trước khi ứng dụng chạy.

-- 3. Các INDEX sẽ được tạo bởi script startup hoặc thủ công sau khi bảng được khởi tạo:
--    - GIN index cho Full-Text Search:
--      CREATE INDEX IF NOT EXISTS idx_chunks_text_fts ON knowledge_chunks USING gin (to_tsvector('simple', text));
--    - B-tree index cho document_id (foreign key JOIN):
--      CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON knowledge_chunks (document_id);
--    - B-tree index cho documents.is_active (filter):
--      CREATE INDEX IF NOT EXISTS idx_documents_is_active ON documents (is_active);
--
-- Lưu ý: pgvector HNSW/IVFFlat index giới hạn tối đa 2000 chiều.
-- Embedding hiện tại dùng 3072 chiều (Gemini Embedding 2), nên cần
-- giảm xuống 768 chiều (output_dimensionality=768) để tạo được vector index.
