"""
Audit Logger — Ghi nhật ký giám sát mọi hoạt động hệ thống.
Thiết kế append-only: không bao giờ sửa hoặc xóa log.
"""
from sqlalchemy.orm import Session
from models import AuditLog
from database import get_db_session


def log_action(
    entity_type: str,
    action: str,
    entity_id: int = 0,
    actor: str = "system",
    details: dict = None,
    ip_address: str = "",
    db: Session = None
):
    """
    Ghi một bản ghi audit log.
    
    Args:
        entity_type: Loại thực thể (document, chunk, chat, system, admin)
        action: Hành động (CREATE, UPDATE, DELETE, REINDEX, SEARCH, CHAT, LOGIN, UPLOAD)
        entity_id: ID thực thể liên quan
        actor: Người thực hiện (admin, system, zalo_user_xxx)
        details: Chi tiết bổ sung (dict → JSONB)
        ip_address: IP nguồn
        db: DB session (tự tạo nếu không truyền)
    """
    should_close = False
    if db is None:
        db = get_db_session()
        should_close = True

    try:
        log_entry = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            details=details or {},
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Audit] Lỗi ghi audit log: {e}")
    finally:
        if should_close:
            db.close()


def log_document_action(action: str, doc_id: int, actor: str = "admin", details: dict = None, db: Session = None):
    """Shortcut ghi log cho tài liệu"""
    log_action("document", action, entity_id=doc_id, actor=actor, details=details, db=db)


def log_chat_action(session_id: int, actor: str, details: dict = None, db: Session = None):
    """Shortcut ghi log cho hội thoại"""
    log_action("chat", "CHAT", entity_id=session_id, actor=actor, details=details, db=db)


def log_system_action(action: str, details: dict = None, db: Session = None):
    """Shortcut ghi log cho hệ thống"""
    log_action("system", action, actor="system", details=details, db=db)


def get_audit_logs(
    db: Session,
    entity_type: str = None,
    action: str = None,
    limit: int = 50,
    offset: int = 0
) -> list:
    """Truy vấn audit logs với bộ lọc"""
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
