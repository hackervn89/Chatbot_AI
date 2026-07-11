import json
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, type_coerce
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator, TEXT
from database import Base, IS_POSTGRES

# Tự định nghĩa kiểu JSON fallback cho SQLite nếu lưu vector làm mảng float
class SQLiteVector(TypeDecorator):
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None

# Import pgvector nếu đang dùng PostgreSQL
if IS_POSTGRES:
    from pgvector.sqlalchemy import Vector
    VectorColumnType = Vector(3072)
else:
    VectorColumnType = SQLiteVector

class Document(Base):
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    source = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")
    images = relationship("ImageMapping", back_populates="document", cascade="all, delete-orphan")

class KnowledgeChunk(Base):
    __tablename__ = 'knowledge_chunks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(VectorColumnType, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="chunks")

class ImageMapping(Base):
    __tablename__ = 'image_mappings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    hinh_key = Column(String(100), nullable=False)
    img_rel_path = Column(String(500), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="images")

    __table_args__ = (
        UniqueConstraint('document_id', 'hinh_key', name='unique_doc_image'),
    )

class ChatHistory(Base):
    __tablename__ = 'chat_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(100), nullable=False, index=True)
    role = Column(String(20), nullable=False) # 'user' hoặc 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class FileMapping(Base):
    __tablename__ = 'file_mappings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(50), unique=True, nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
