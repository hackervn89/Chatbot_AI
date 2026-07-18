"""
SQLAlchemy Models — Schema đầy đủ cho hệ thống RAG.
Bao gồm: Documents, Versions, Chunks, ChatSessions, ChatMessages, AuditLogs, AdminUsers, ImageMappings.
"""
import json
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Float,
    DateTime, Date, Boolean, ForeignKey, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator, TEXT
from database import Base
from config import IS_POSTGRES

# ==================== CUSTOM TYPES ====================


class SQLiteVector(TypeDecorator):
    """Lưu vector embeddings dưới dạng JSON text cho SQLite fallback"""
    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None


# Chọn kiểu vector phù hợp
if IS_POSTGRES:
    from pgvector.sqlalchemy import Vector
    from config import EMBEDDING_DIMENSION
    VectorColumnType = Vector(EMBEDDING_DIMENSION)
    BigIntegerIDType = BigInteger
else:
    VectorColumnType = SQLiteVector
    BigIntegerIDType = Integer


# ==================== MODELS ====================

class Document(Base):
    """Tài liệu tri thức — nguồn gốc của mọi chunks"""
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    source = Column(String(500), unique=True, nullable=False)
    category = Column(String(50), nullable=False, default='core')  # core, updatable, personal
    description = Column(Text, default='')
    file_type = Column(String(20), default='')  # pdf, docx, srt, txt, md
    raw_text = Column(Text, default='')  # Nội dung văn bản đầy đủ
    current_version = Column(Integer, default=1)
    chunk_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)  # Bật/tắt khỏi RAG
    status = Column(String(20), nullable=False, default='active')  # draft, active, archived
    
    # Metadata bổ sung cho phân loại nâng cao
    document_type = Column(String(50), nullable=False, default='other')  # nq, qd, ct, qyd, kl, hd, bc, other
    issuer = Column(String(50), nullable=False, default='other')  # tw, tinh, huyen, xa, other
    domain = Column(String(50), nullable=False, default='other')  # to_chuc, kiem_tra, tuyen_giao, dan_van, van_phong, other
    effective_date = Column(Date, nullable=True)  # Ngày hiệu lực / Ngày báo cáo số liệu
    is_latest = Column(Boolean, default=True)  # Đánh dấu báo cáo số liệu mới nhất
    validity = Column(String(50), nullable=False, default='active')  # active, expired, replaced
    
    created_by = Column(String(100), default='system')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    images = relationship("ImageMapping", back_populates="document", cascade="all, delete-orphan")


class DocumentVersion(Base):
    """Lịch sử phiên bản tài liệu — mỗi lần cập nhật tạo bản ghi mới"""
    __tablename__ = 'document_versions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    version = Column(Integer, nullable=False)
    raw_text = Column(Text, default='')
    change_summary = Column(Text, default='')
    changed_by = Column(String(100), default='system')
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="versions")

    __table_args__ = (
        UniqueConstraint('document_id', 'version', name='unique_doc_version'),
    )


class KnowledgeChunk(Base):
    """Chunks tri thức — đơn vị tìm kiếm cơ bản trong RAG"""
    __tablename__ = 'knowledge_chunks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    chunk_index = Column(Integer, default=0)  # Thứ tự trong tài liệu
    text = Column(Text, nullable=False)
    embedding = Column(VectorColumnType, nullable=False)
    chunk_metadata = Column(JSON, default=dict)  # Heading, page number...
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="chunks")


class ChatSession(Base):
    """Phiên hội thoại — nhóm các tin nhắn theo user + platform"""
    __tablename__ = 'chat_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False, default='zalo')  # zalo, telegram, web
    external_chat_id = Column(String(100), nullable=False, index=True)
    user_display_name = Column(String(200), default='')
    message_count = Column(Integer, default=0)
    last_activity = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('platform', 'external_chat_id', name='unique_platform_chat'),
    )


class ChatMessage(Base):
    """Tin nhắn hội thoại — lưu chi tiết từng tin nhắn + metadata AI"""
    __tablename__ = 'chat_messages'

    id = Column(BigIntegerIDType, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    ai_model_used = Column(String(50), default='')  # Model AI đã dùng
    rag_score = Column(Float, default=0.0)  # Điểm RAG cao nhất
    rag_sources = Column(JSON, default=list)  # Danh sách nguồn
    response_time_ms = Column(Integer, default=0)  # Thời gian phản hồi
    created_at = Column(DateTime, server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")


class AuditLog(Base):
    """Nhật ký giám sát — append-only, ghi lại mọi hoạt động"""
    __tablename__ = 'audit_logs'

    id = Column(BigIntegerIDType, primary_key=True, autoincrement=True)
    entity_type = Column(String(50), nullable=False)  # document, chunk, chat, system
    entity_id = Column(Integer, default=0)
    action = Column(String(30), nullable=False)  # CREATE, UPDATE, DELETE, REINDEX, SEARCH, CHAT
    actor = Column(String(100), default='system')  # admin, system, zalo_user_xxx
    details = Column(JSON, default=dict)  # Chi tiết thay đổi
    ip_address = Column(String(45), default='')
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('idx_audit_entity_time', 'entity_type', 'created_at'),
        Index('idx_audit_action', 'action', 'created_at'),
    )


class AdminUser(Base):
    """Tài khoản admin dashboard"""
    __tablename__ = 'admin_users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), default='Admin')
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ImageMapping(Base):
    """Mapping hình ảnh minh họa trong tài liệu"""
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


class FileMapping(Base):
    """Mapping file tạm thời (download links)"""
    __tablename__ = 'file_mappings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(50), unique=True, nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
