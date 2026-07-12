"""
Knowledge Manager — Quản lý tài liệu tri thức (CRUD, Versioning, Re-indexing).
"""
import os
import re
import time
import zipfile
from xml.etree import ElementTree
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from pypdf import PdfReader

from config import (
    IMAGES_DIR, CATEGORY_CORE, CATEGORY_UPDATABLE, CATEGORY_PERSONAL
)
from database import get_db_session
from models import Document, DocumentVersion, KnowledgeChunk, ImageMapping
from services.rag_pipeline import semantic_chunk, get_embedding
from services.audit_logger import log_document_action


# ==================== FILE PARSERS ====================

def parse_pdf(file_path: str) -> str:
    """Trích xuất văn bản từ PDF"""
    reader = PdfReader(file_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def parse_docx(file_path: str) -> tuple:
    """Trích xuất văn bản + hình ảnh từ DOCX"""
    from docx import Document as DocxDocument
    doc = DocxDocument(file_path)
    
    full_text = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
    raw_text = "\n".join(full_text)
    
    # Trích xuất hình ảnh
    image_mappings = _extract_docx_images(file_path)
    
    return raw_text, image_mappings


def _extract_docx_images(docx_path: str) -> dict:
    """Bóc tách hình ảnh từ file DOCX (ZIP format)"""
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', os.path.basename(docx_path).replace('.docx', ''))
    doc_image_dir = os.path.join(IMAGES_DIR, safe_name)
    os.makedirs(doc_image_dir, exist_ok=True)
    
    mappings = {}
    try:
        with zipfile.ZipFile(docx_path) as z:
            rels_xml = z.read('word/_rels/document.xml.rels')
            rels_root = ElementTree.fromstring(rels_xml)
            
            id_to_file = {}
            for child in rels_root:
                r_id = child.attrib.get('Id')
                target = child.attrib.get('Target')
                if r_id and target and 'media' in target:
                    id_to_file[r_id] = os.path.basename(target)
            
            doc_xml = z.read('word/document.xml')
            doc_root = ElementTree.fromstring(doc_xml)
            
            counter = 1
            for elem in doc_root.iter():
                if elem.tag.endswith('drawing'):
                    blips = [e for e in elem.iter() if e.tag.endswith('blip')]
                    if blips:
                        ns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
                        r_id = blips[0].attrib.get(f'{ns}embed')
                        if r_id and r_id in id_to_file:
                            filename = id_to_file[r_id]
                            ext = os.path.splitext(filename)[1] or '.png'
                            dest = f"hinh_{counter}{ext}"
                            dest_path = os.path.join(doc_image_dir, dest)
                            try:
                                with open(dest_path, 'wb') as f:
                                    f.write(z.read(f"word/media/{filename}"))
                                mappings[f"Hình {counter}"] = f"images/{safe_name}/{dest}"
                                counter += 1
                            except Exception as ex:
                                print(f"[KM] Lỗi trích xuất ảnh: {ex}")
    except Exception as e:
        print(f"[KM] Warning: Không thể trích xuất ảnh DOCX: {e}")
    
    return mappings


def parse_srt(file_path: str) -> str:
    """Làm sạch file phụ đề SRT"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}', '', content)
    lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().isdigit()]
    return "\n".join(lines)


def parse_text(file_path: str) -> str:
    """Đọc file text/markdown"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


# ==================== KNOWLEDGE CRUD ====================

def ingest_document(
    file_path: str,
    title: str = None,
    category: str = CATEGORY_CORE,
    description: str = "",
    created_by: str = "admin",
    db: Session = None
) -> dict:
    """
    Nạp tài liệu mới vào hệ thống RAG.
    
    Pipeline: Parse file → Semantic chunk → Generate embeddings → Lưu DB
    
    Returns: {"status": "success/error", "message": "...", "details": {...}}
    """
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File không tồn tại."}

    should_close = False
    if db is None:
        db = get_db_session()
        should_close = True

    filename = os.path.basename(file_path)
    file_ext = os.path.splitext(filename)[1].lower()
    
    if not title:
        title = os.path.splitext(filename)[0].replace('_', ' ')

    # Source name chuẩn hóa
    doc_source = f"{category}/{filename}"

    try:
        # 1. Parse file
        print(f"[KM] Đang xử lý: {filename} ({file_ext})")
        raw_text = ""
        image_mappings = {}

        if file_ext == '.pdf':
            raw_text = parse_pdf(file_path)
        elif file_ext == '.docx':
            raw_text, image_mappings = parse_docx(file_path)
        elif file_ext == '.srt':
            raw_text = parse_srt(file_path)
        elif file_ext in ('.txt', '.md'):
            raw_text = parse_text(file_path)
        else:
            return {"status": "error", "message": f"Định dạng {file_ext} không được hỗ trợ."}

        if not raw_text.strip():
            return {"status": "error", "message": "Tài liệu trống."}

        # 2. Kiểm tra tài liệu đã tồn tại chưa
        doc = db.query(Document).filter(Document.source == doc_source).first()
        
        if doc:
            # Tạo version mới
            doc.current_version += 1
            version = DocumentVersion(
                document_id=doc.id,
                version=doc.current_version,
                raw_text=raw_text,
                change_summary=f"Cập nhật từ file {filename}",
                changed_by=created_by
            )
            db.add(version)
            
            # Xóa chunks cũ
            db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).delete()
            db.query(ImageMapping).filter(ImageMapping.document_id == doc.id).delete()
            
            doc.title = title
            doc.raw_text = raw_text
            doc.description = description
            doc.updated_at = func.now()
            action = "UPDATE"
        else:
            # Tạo tài liệu mới
            doc = Document(
                title=title,
                source=doc_source,
                category=category,
                description=description,
                file_type=file_ext.lstrip('.'),
                raw_text=raw_text,
                created_by=created_by
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            
            # Tạo version đầu tiên
            version = DocumentVersion(
                document_id=doc.id,
                version=1,
                raw_text=raw_text,
                change_summary="Phiên bản gốc",
                changed_by=created_by
            )
            db.add(version)
            action = "CREATE"

        db.commit()
        db.refresh(doc)

        # 3. Semantic chunking
        chunks = semantic_chunk(raw_text)
        print(f"[KM] Đã chia thành {len(chunks)} chunks.")

        # 4. Generate embeddings & save chunks
        inserted = 0
        for i, chunk_data in enumerate(chunks):
            vector = get_embedding(chunk_data["text"])
            chunk_obj = KnowledgeChunk(
                document_id=doc.id,
                chunk_index=i,
                text=chunk_data["text"],
                embedding=vector,
                chunk_metadata=chunk_data.get("metadata", {})
            )
            db.add(chunk_obj)
            inserted += 1
            
            # Commit theo batch để tránh memory overflow
            if inserted % 30 == 0:
                db.commit()
                time.sleep(0.2)  # Tránh rate limit embedding API

        # 5. Save image mappings
        img_count = 0
        for hinh_key, img_path in image_mappings.items():
            db.add(ImageMapping(document_id=doc.id, hinh_key=hinh_key, img_rel_path=img_path))
            img_count += 1

        # Update chunk count
        doc.chunk_count = inserted
        db.commit()

        # 6. Audit log
        log_document_action(action, doc.id, actor=created_by, details={
            "title": title, "chunks": inserted, "images": img_count,
            "category": category, "file_type": file_ext
        }, db=db)

        print(f"[KM] Nạp thành công! {inserted} chunks, {img_count} ảnh.")
        return {
            "status": "success",
            "message": f"Nạp tài liệu thành công!",
            "details": {
                "doc_id": doc.id,
                "title": title,
                "chunks": inserted,
                "images": img_count,
                "version": doc.current_version
            }
        }

    except Exception as e:
        db.rollback()
        print(f"[KM] Lỗi nạp tài liệu: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if should_close:
            db.close()


def toggle_document(doc_id: int, is_active: bool, actor: str = "admin", db: Session = None) -> bool:
    """Bật/tắt tài liệu khỏi RAG (không xóa)"""
    should_close = db is None
    if db is None:
        db = get_db_session()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.is_active = is_active
            db.commit()
            status = "ACTIVATE" if is_active else "DEACTIVATE"
            log_document_action(status, doc_id, actor=actor, db=db)
            return True
        return False
    finally:
        if should_close:
            db.close()


def delete_document(doc_id: int, actor: str = "admin", db: Session = None) -> bool:
    """Xóa tài liệu và tất cả chunks liên quan"""
    should_close = db is None
    if db is None:
        db = get_db_session()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            title = doc.title
            db.delete(doc)  # CASCADE sẽ xóa chunks, versions, images
            db.commit()
            log_document_action("DELETE", doc_id, actor=actor, details={"title": title}, db=db)
            return True
        return False
    finally:
        if should_close:
            db.close()


def get_all_documents(db: Session, category: str = None, active_only: bool = False) -> list:
    """Lấy danh sách tài liệu"""
    query = db.query(Document)
    if category:
        query = query.filter(Document.category == category)
    if active_only:
        query = query.filter(Document.is_active == True)
    return query.order_by(Document.updated_at.desc()).all()


def get_document_detail(db: Session, doc_id: int) -> dict:
    """Lấy chi tiết tài liệu kèm versions và chunks"""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return None
    
    versions = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_id
    ).order_by(DocumentVersion.version.desc()).all()
    
    chunks = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.document_id == doc_id
    ).order_by(KnowledgeChunk.chunk_index).all()
    
    return {
        "document": doc,
        "versions": versions,
        "chunks": chunks,
        "chunk_count": len(chunks)
    }
