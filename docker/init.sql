-- Khởi tạo pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Bảng lưu trữ tài liệu gốc
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    source VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng lưu trữ các chunk văn bản và vector embeddings tương ứng
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id SERIAL PRIMARY KEY,
    document_id INT REFERENCES documents(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    -- 3072 chiều tương ứng với mô hình gemini-embedding-2 mới
    embedding VECTOR(3072) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng lưu trữ bản đồ hình ảnh minh họa (Hình X -> Đường dẫn ảnh)
CREATE TABLE IF NOT EXISTS image_mappings (
    id SERIAL PRIMARY KEY,
    document_id INT REFERENCES documents(id) ON DELETE CASCADE,
    hinh_key VARCHAR(100) NOT NULL, -- Ví dụ: "Hình 1", "Hình 2"
    img_rel_path VARCHAR(500) NOT NULL, -- Đường dẫn tương đối từ thư mục static
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_doc_image UNIQUE (document_id, hinh_key)
);

-- Bảng lưu trữ lịch sử trò chuyện dài hạn (Chat History) theo người dùng Zalo
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    chat_id VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL, -- 'user' hoặc 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng lưu trữ mapping file Word sinh ra để phục vụ việc tải xuống bảo mật
CREATE TABLE IF NOT EXISTS file_mappings (
    id SERIAL PRIMARY KEY,
    file_id VARCHAR(50) UNIQUE NOT NULL,
    filename VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tạo các chỉ mục tối ưu hóa tìm kiếm
-- Chỉ mục HNSW cho pgvector (sử dụng độ đo Cosine)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON knowledge_chunks 
USING hnsw (embedding vector_cosine_ops);

-- Chỉ mục Full-Text Search trên trường văn bản của chunk để thực hiện Hybrid Search
CREATE INDEX IF NOT EXISTS idx_chunks_text_fts ON knowledge_chunks 
USING gin (to_tsvector('simple', text));

-- Chỉ mục tìm kiếm nhanh lịch sử hội thoại
CREATE INDEX IF NOT EXISTS idx_chat_history_chat_id ON chat_history (chat_id, created_at DESC);
