-- init.sql: Khởi tạo PostgreSQL cho hệ thống RAG
-- Chạy tự động khi container PostgreSQL được tạo lần đầu

-- 1. Kích hoạt extension pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. HNSW Index sẽ được tạo sau khi bảng knowledge_chunks được tạo bởi SQLAlchemy
-- Ta dùng script riêng để tạo index sau khi migrate

-- Ghi chú: SQLAlchemy sẽ tự tạo các bảng khi ứng dụng khởi chạy (Base.metadata.create_all)
-- File này chỉ đảm bảo extension pgvector có sẵn trước khi ứng dụng chạy
