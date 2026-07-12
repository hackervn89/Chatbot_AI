"""
Admin Dashboard Router — Quản lý tri thức qua giao diện web.
Session-based authentication, Jinja2 templates.
"""
import os
import hashlib
import secrets
import shutil
from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func

from config import (
    TEMPLATES_DIR, SESSION_SECRET_KEY, ADMIN_DEFAULT_USERNAME,
    ADMIN_DEFAULT_PASSWORD, TEMP_DIR,
    CATEGORY_CORE, CATEGORY_UPDATABLE, CATEGORY_PERSONAL
)
from database import get_db, get_db_session
from models import (
    AdminUser, Document, KnowledgeChunk, ChatSession,
    ChatMessage, AuditLog, DocumentVersion
)
from services.knowledge_manager import (
    ingest_document, toggle_document, delete_document,
    get_all_documents, get_document_detail, publish_document,
    analyze_document_draft
)
from services.audit_logger import log_action

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# In-memory sessions (đủ cho single-admin)
_sessions = {}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _get_current_admin(request: Request) -> AdminUser:
    """Kiểm tra session đăng nhập, trả về AdminUser hoặc None"""
    session_id = request.cookies.get("admin_session")
    if not session_id or session_id not in _sessions:
        return None
    
    username = _sessions[session_id]
    db = get_db_session()
    try:
        admin = db.query(AdminUser).filter(
            AdminUser.username == username, AdminUser.is_active == True
        ).first()
        return admin
    finally:
        db.close()


def _require_login(request: Request):
    """Decorator-like check — redirect to login if not authenticated"""
    admin = _get_current_admin(request)
    if not admin:
        return None
    return admin


# ==================== AUTH ====================

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    admin = _get_current_admin(request)
    if admin:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": ""})


@router.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    db = get_db_session()
    try:
        admin = db.query(AdminUser).filter(AdminUser.username == username).first()
        
        # Auto-seed admin nếu chưa có
        if not admin and username == ADMIN_DEFAULT_USERNAME:
            admin = AdminUser(
                username=ADMIN_DEFAULT_USERNAME,
                password_hash=hash_password(ADMIN_DEFAULT_PASSWORD),
                display_name="Quản trị viên"
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        
        if admin and admin.password_hash == hash_password(password) and admin.is_active:
            session_id = secrets.token_hex(32)
            _sessions[session_id] = admin.username
            admin.last_login = datetime.utcnow()
            db.commit()
            
            log_action("admin", "LOGIN", actor=username, db=db)
            
            response = RedirectResponse(url="/admin/dashboard", status_code=302)
            response.set_cookie("admin_session", session_id, httponly=True, max_age=86400)
            return response
        
        return templates.TemplateResponse(request=request, name="login.html", context={
            "request": request, "error": "Sai tên đăng nhập hoặc mật khẩu"
        })
    finally:
        db.close()


@router.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("admin_session")
    if session_id and session_id in _sessions:
        del _sessions[session_id]
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie("admin_session")
    return response


# ==================== DASHBOARD ====================

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        stats = {
            "total_documents": db.query(Document).count(),
            "active_documents": db.query(Document).filter(Document.is_active == True).count(),
            "total_chunks": db.query(KnowledgeChunk).count(),
            "total_sessions": db.query(ChatSession).count(),
            "total_messages": db.query(ChatMessage).count(),
            "total_audit_logs": db.query(AuditLog).count(),
        }
        
        # Category breakdown
        stats["core_docs"] = db.query(Document).filter(Document.category == CATEGORY_CORE).count()
        stats["updatable_docs"] = db.query(Document).filter(Document.category == CATEGORY_UPDATABLE).count()
        stats["personal_docs"] = db.query(Document).filter(Document.category == CATEGORY_PERSONAL).count()
        
        # Recent activity
        recent_chats = db.query(ChatSession).order_by(
            ChatSession.last_activity.desc()
        ).limit(5).all()
        
        recent_logs = db.query(AuditLog).order_by(
            AuditLog.created_at.desc()
        ).limit(10).all()
        
        return templates.TemplateResponse(request=request, name="dashboard.html", context={
            "request": request,
            "admin": admin,
            "stats": stats,
            "recent_chats": recent_chats,
            "recent_logs": recent_logs
        })
    finally:
        db.close()


# Danh sách Danh mục tri thức mặc định
DEFAULT_CATEGORIES = [
    "Văn bản của Trung ương",
    "Văn bản của Tỉnh",
    "Văn bản của Xã",
    "Hướng dẫn điều hành tác nghiệp",
    "Hướng dẫn sổ tay điện tử"
]


# ==================== DOCUMENTS ====================

@router.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        category = request.query_params.get("category", "")
        docs = get_all_documents(db, category=category if category else None)
        
        # Gợi ý danh mục động từ database
        db_categories = [r[0] for r in db.query(Document.category).distinct().all() if r[0]]
        suggested_categories = sorted(list(set(DEFAULT_CATEGORIES + db_categories)))
        
        return templates.TemplateResponse(request=request, name="documents.html", context={
            "request": request, "admin": admin, "documents": docs,
            "current_category": category,
            "suggested_categories": suggested_categories
        })
    finally:
        db.close()


@router.get("/documents/{doc_id}", response_class=HTMLResponse)
async def document_detail_page(request: Request, doc_id: int):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        detail = get_document_detail(db, doc_id)
        if not detail:
            return RedirectResponse(url="/admin/documents", status_code=302)
            
        # Gợi ý danh mục động từ database
        db_categories = [r[0] for r in db.query(Document.category).distinct().all() if r[0]]
        suggested_categories = sorted(list(set(DEFAULT_CATEGORIES + db_categories)))
        
        return templates.TemplateResponse(request=request, name="document_detail.html", context={
            "request": request, "admin": admin, **detail,
            "suggested_categories": suggested_categories
        })
    finally:
        db.close()


@router.post("/documents/upload")
async def upload_document(
    request: Request,
    title: str = Form(...),
    category: str = Form("Văn bản của Xã"),
    description: str = Form(""),
    status: str = Form("active"),
    effective_date: str = Form(None),
    no_split: bool = Form(False),
    file: UploadFile = File(...)
):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    # Lưu file tạm
    temp_path = os.path.join(TEMP_DIR, file.filename)
    try:
        with open(temp_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        result = ingest_document(
            file_path=temp_path,
            title=title,
            category=category,
            description=description,
            created_by=admin.username,
            status=status,
            document_type="other",
            issuer="other",
            domain="other",
            effective_date=effective_date if effective_date else None,
            validity="active",
            no_split=no_split
        )
        
        # Redirect with message
        if result["status"] == "success":
            return RedirectResponse(url="/admin/documents?msg=upload_success", status_code=302)
        else:
            return RedirectResponse(url=f"/admin/documents?msg=error&detail={result['message']}", status_code=302)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/documents/{doc_id}/toggle")
async def toggle_doc(request: Request, doc_id: int):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            toggle_document(doc_id, not doc.is_active, actor=admin.username, db=db)
    finally:
        db.close()
    
    return RedirectResponse(url=f"/admin/documents/{doc_id}", status_code=302)


@router.post("/documents/{doc_id}/delete")
async def delete_doc(request: Request, doc_id: int):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    delete_document(doc_id, actor=admin.username)
    return RedirectResponse(url="/admin/documents?msg=deleted", status_code=302)


@router.post("/documents/{doc_id}/publish")
async def publish_doc(request: Request, doc_id: int):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
        
    result = publish_document(doc_id, actor=admin.username)
    if result["status"] == "success":
        return RedirectResponse(url=f"/admin/documents/{doc_id}?msg=published", status_code=302)
    else:
        return RedirectResponse(url=f"/admin/documents/{doc_id}?msg=error&detail={result['message']}", status_code=302)


@router.post("/documents/{doc_id}/analyze")
async def analyze_doc(request: Request, doc_id: int):
    admin = _require_login(request)
    if not admin:
        return JSONResponse({"status": "error", "message": "Unauthorized"}, status_code=401)
        
    result = analyze_document_draft(doc_id)
    return JSONResponse(result)


@router.post("/documents/{doc_id}/edit")
async def edit_doc(
    request: Request, 
    doc_id: int, 
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    effective_date: str = Form(None),
    raw_text: str = Form(...)
):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
        
    db = get_db_session()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.title = title
            doc.category = category
            doc.description = description
            
            # Parse effective_date
            from datetime import datetime
            eff_date = None
            if effective_date:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                    try:
                        eff_date = datetime.strptime(effective_date, fmt).date()
                        break
                    except ValueError:
                        pass
            doc.effective_date = eff_date
            
            # Logic tự động tính toán is_latest cho báo cáo số liệu (nhận diện động qua category hoặc title)
            is_report = False
            if category:
                cat_lower = category.lower()
                if "báo cáo" in cat_lower or "số liệu" in cat_lower:
                    is_report = True
            if title and not is_report:
                title_lower = title.lower()
                if "báo cáo" in title_lower or "số liệu" in title_lower:
                    is_report = True

            if is_report and eff_date:
                other_reports = db.query(Document).filter(
                    Document.category == category,
                    Document.status == 'active',
                    Document.id != doc.id
                ).all()
                
                is_new_latest = True
                for r in other_reports:
                    if r.effective_date:
                        if r.effective_date > eff_date:
                            is_new_latest = False
                        else:
                            r.is_latest = False
                doc.is_latest = is_new_latest
            
            text_changed = doc.raw_text != raw_text
            if text_changed:
                doc.raw_text = raw_text
                doc.current_version += 1
                version = DocumentVersion(
                    document_id=doc.id,
                    version=doc.current_version,
                    raw_text=raw_text,
                    change_summary="Chỉnh sửa nội dung trực tiếp qua Dashboard",
                    changed_by=admin.username
                )
                db.add(version)
            
            db.commit()
            
            # Nếu đang hoạt động và nội dung đổi, re-publish để sinh lại embeddings
            if doc.status == "active" and text_changed:
                publish_document(doc_id, actor=admin.username, db=db)
                
            return RedirectResponse(url=f"/admin/documents/{doc_id}?msg=updated", status_code=302)
        return RedirectResponse(url="/admin/documents", status_code=302)
    except Exception as e:
        db.rollback()
        return RedirectResponse(url=f"/admin/documents/{doc_id}?msg=error&detail={str(e)}", status_code=302)
    finally:
        db.close()


# ==================== CHAT SESSIONS ====================

@router.get("/chats", response_class=HTMLResponse)
async def chat_sessions_page(request: Request):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        sessions = db.query(ChatSession).order_by(
            ChatSession.last_activity.desc()
        ).limit(50).all()
        return templates.TemplateResponse(request=request, name="chat_sessions.html", context={
            "request": request, "admin": admin, "sessions": sessions
        })
    finally:
        db.close()


@router.get("/chats/{session_id}", response_class=HTMLResponse)
async def chat_detail_page(request: Request, session_id: int):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        return templates.TemplateResponse(request=request, name="chat_detail.html", context={
            "request": request, "admin": admin,
            "session": session, "messages": messages
        })
    finally:
        db.close()


# ==================== AUDIT LOGS ====================

@router.get("/audit", response_class=HTMLResponse)
async def audit_logs_page(request: Request):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        entity_type = request.query_params.get("type", "")
        action = request.query_params.get("action", "")
        
        query = db.query(AuditLog)
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        if action:
            query = query.filter(AuditLog.action == action)
        
        logs = query.order_by(AuditLog.created_at.desc()).limit(100).all()
        
        return templates.TemplateResponse(request=request, name="audit_logs.html", context={
            "request": request, "admin": admin, "logs": logs,
            "filter_type": entity_type, "filter_action": action
        })
    finally:
        db.close()


# ==================== SETTINGS ====================

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    from config import AI_PRIMARY_ENGINE, DEEPSEEK_API_KEY, GEMINI_API_KEY
    
    return templates.TemplateResponse(request=request, name="settings.html", context={
        "request": request, "admin": admin,
        "ai_engine": AI_PRIMARY_ENGINE,
        "has_deepseek": bool(DEEPSEEK_API_KEY),
        "has_gemini": bool(GEMINI_API_KEY),
        "msg": request.query_params.get("msg", "")
    })


@router.post("/settings/password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...)
):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        user = db.query(AdminUser).filter(AdminUser.id == admin.id).first()
        if user and user.password_hash == hash_password(current_password):
            user.password_hash = hash_password(new_password)
            db.commit()
            log_action("admin", "CHANGE_PASSWORD", actor=admin.username, db=db)
            return RedirectResponse(url="/admin/settings?msg=password_changed", status_code=302)
        return RedirectResponse(url="/admin/settings?msg=wrong_password", status_code=302)
    finally:
        db.close()


@router.get("/logs")
async def show_logs_page(request: Request):
    admin = _require_login(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse("logs.html", {"request": request, "admin": admin})


@router.get("/logs/data")
async def get_logs_data(request: Request, lines: int = 300):
    admin = _require_login(request)
    if not admin:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    
    log_file = "app.log"
    if not os.path.exists(log_file):
        return {"status": "success", "content": "[System] Chưa có log hệ thống được tạo."}
        
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            content = "".join(tail_lines)
            return {"status": "success", "content": content}
    except Exception as e:
        return {"status": "error", "content": f"Không thể đọc file log: {str(e)}"}
