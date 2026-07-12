import os
import sys
import re
import time
import json
import zipfile
from xml.etree import ElementTree
from sqlalchemy.orm import Session
from google import genai
from pypdf import PdfReader
from database import SessionLocal, IS_POSTGRES
import models
from rag_engine import get_embedding

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "taovanban_khoidang", "output")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")

# Cấu hình namespace XML để parse file docx
WORD_NAMESPACE = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
DRAWING_NAMESPACE = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
REL_NAMESPACE = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

def clean_srt(srt_path: str) -> str:
    """Làm sạch file SRT: bỏ số thứ tự, mốc thời gian và gộp thành văn bản liên tục"""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Loại bỏ mốc thời gian (ví dụ: 00:01:20,000 --> 00:01:23,000)
    content = re.sub(r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}', '', content)
    # Loại bỏ số thứ tự dòng srt
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        cleaned_lines.append(line)
        
    return "\n".join(cleaned_lines)

def parse_docx_and_extract_images(docx_path: str, doc_source_name: str) -> tuple:
    """
    Đọc text từ file DOCX và trích xuất hình ảnh, lập mapping Hình X -> Đường dẫn ảnh tĩnh.
    Hàm này kế thừa từ logic của extract_manual_images.py nhưng được đóng gói thành module.
    """
    from docx import Document as DocxDocument
    doc = DocxDocument(docx_path)
    
    # 1. Trích xuất text thô
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    raw_text = "\n".join(full_text)
    
    # 2. Bóc tách hình ảnh đính kèm
    # Tạo thư mục con chứa ảnh cho tài liệu này
    safe_folder_name = re.sub(r'[^a-zA-Z0-9]', '_', os.path.basename(docx_path).replace('.docx', ''))
    doc_image_dir = os.path.join(IMAGES_DIR, safe_folder_name)
    os.makedirs(doc_image_dir, exist_ok=True)
    
    image_mappings = {} # hinh_key -> rel_path
    
    try:
        # File Word (.docx) là một file ZIP
        with zipfile.ZipFile(docx_path) as z:
            # Đọc file mapping liên kết id ảnh với file ảnh thực tế
            rels_xml = z.read('word/_rels/document.xml.rels')
            rels_root = ElementTree.fromstring(rels_xml)
            
            id_to_file = {}
            for child in rels_root:
                r_id = child.attrib.get('Id')
                target = child.attrib.get('Target')
                if r_id and target and 'media' in target:
                    # target thường có dạng: media/image1.png
                    id_to_file[r_id] = os.path.basename(target)
            
            # Đọc cấu trúc tài liệu XML để tìm captions "Hình N" và ảnh đi liền
            doc_xml = z.read('word/document.xml')
            doc_root = ElementTree.fromstring(doc_xml)
            
            # Duyệt qua các paragraph chứa hình vẽ
            hinh_counter = 1
            for elem in doc_root.iter():
                # Tìm thẻ drawing biểu thị ảnh chèn
                if elem.tag.endswith('drawing'):
                    # Thử tìm rId của ảnh
                    blip_elems = [e for e in elem.iter() if e.tag.endswith('blip')]
                    if blip_elems:
                        r_id = blip_elems[0].attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                        if r_id and r_id in id_to_file:
                            filename = id_to_file[r_id]
                            zip_path = f"word/media/{filename}"
                            
                            # Lưu file ảnh ra thư mục static images
                            hinh_key = f"Hình {hinh_counter}"
                            img_ext = os.path.splitext(filename)[1] or '.png'
                            dest_filename = f"hinh_{hinh_counter}{img_ext}"
                            dest_path = os.path.join(doc_image_dir, dest_filename)
                            
                            try:
                                with open(dest_path, 'wb') as img_out:
                                    img_out.write(z.read(zip_path))
                                
                                rel_path = f"images/{safe_folder_name}/{dest_filename}"
                                image_mappings[hinh_key] = rel_path
                                hinh_counter += 1
                            except Exception as ex:
                                print(f"[Doc Ingest] Lỗi trích xuất ảnh {zip_path}: {ex}")
    except Exception as e:
        print(f"[Doc Ingest Warning] Không thể trích xuất ảnh từ Word: {e}")
        
    return raw_text, image_mappings

def chunk_text(text: str, chunk_size: int = 1500, chunk_overlap: int = 150) -> list:
    """Chia nhỏ văn bản theo ngữ nghĩa đề mục Markdown H3 (hoặc H2, H1)"""
    if not text.strip():
        return []
    
    lines = text.split('\n')
    sections = []
    current_section = {"lines": []}
    
    for line in lines:
        stripped = line.strip()
        # Phát hiện heading Markdown
        if stripped.startswith('#'):
            if current_section["lines"]:
                sections.append(current_section)
            current_section = {"lines": [line]}
        else:
            current_section["lines"].append(line)
            
    if current_section["lines"]:
        sections.append(current_section)
        
    if not sections:
        sections = [{"lines": lines}]
        
    chunks = []
    for section in sections:
        section_text = '\n'.join(section["lines"]).strip()
        if not section_text:
            continue
            
        # Nếu độ dài của toàn bộ section nhỏ hơn chunk_size, lưu trọn vẹn thành 1 chunk
        if len(section_text) <= chunk_size:
            chunks.append(section_text)
            continue
            
        # Nếu vượt quá chunk_size, chia nhỏ theo paragraphs
        paragraphs = [p.strip() for p in section_text.split('\n') if p.strip()]
        current_chunk_lines = []
        current_len = 0
        
        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > chunk_size and current_chunk_lines:
                chunks.append('\n'.join(current_chunk_lines))
                overlap_lines = current_chunk_lines[-2:] if len(current_chunk_lines) >= 2 else current_chunk_lines[-1:]
                current_chunk_lines = list(overlap_lines) + [para]
                current_len = sum(len(l) for l in current_chunk_lines)
            else:
                current_chunk_lines.append(para)
                current_len += para_len
                
        if current_chunk_lines:
            chunks.append('\n'.join(current_chunk_lines))
            
    return chunks

def ingest_document_file(file_path: str, title: str = None, no_split: bool = False) -> dict:
    """
    Xử lý nạp tài liệu mới từ file path: bóc tách text, sinh vector, và lưu vào CSDL.
    Hỗ trợ định dạng: .pdf, .docx, .srt, .txt
    """
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File không tồn tại."}
        
    filename = os.path.basename(file_path)
    file_ext = os.path.splitext(filename)[1].lower()
    
    # Xác định source name chuẩn hóa
    if file_ext == '.docx':
        doc_source = f"HDSD/Mobile/{filename}" # Hoặc thư mục tượng trưng
    else:
        doc_source = f"HDSD/Web/{filename}"
        
    if not title:
        title = os.path.splitext(filename)[0].replace('_', ' ')
        
    print(f"[*] Đang xử lý nạp tài liệu: {filename} (Định dạng: {file_ext})")
    
    # 1. Trích xuất văn bản thô và hình ảnh tùy định dạng
    raw_text = ""
    image_mappings = {}
    
    try:
        if file_ext == '.pdf':
            reader = PdfReader(file_path)
            pages_text = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            raw_text = "\n".join(pages_text)
            
        elif file_ext == '.docx':
            raw_text, image_mappings = parse_docx_and_extract_images(file_path, doc_source)
            
        elif file_ext == '.srt':
            raw_text = clean_srt(file_path)
            
        elif file_ext == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
        else:
            return {"status": "error", "message": f"Định dạng tệp {file_ext} không được hỗ trợ."}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi đọc nội dung file: {str(e)}"}
        
    if not raw_text.strip():
        return {"status": "error", "message": "Tài liệu trống, không thể trích xuất văn bản."}
        
    # Tự động phát hiện dòng chỉ thị no_split trong nội dung file Markdown/Text
    if "<!-- no_split -->" in raw_text or "no_split: true" in raw_text:
        no_split = True
        raw_text = raw_text.replace("<!-- no_split -->", "").replace("no_split: true", "")

    # 2. Thực hiện chunking
    if no_split:
        chunks = [raw_text.strip()]
    else:
        chunks = chunk_text(raw_text)
    print(f"[+] Đã chia nhỏ tài liệu thành {len(chunks)} chunks.")
    
    # 3. Ghi vào database và sinh vector
    db: Session = SessionLocal()
    try:
        # Tạo hoặc cập nhật Document
        doc = db.query(models.Document).filter(models.Document.source == doc_source).first()
        if doc:
            # Nếu tài liệu đã có, xóa các chunks cũ để ghi đè
            db.query(models.KnowledgeChunk).filter(models.KnowledgeChunk.document_id == doc.id).delete()
            db.query(models.ImageMapping).filter(models.ImageMapping.document_id == doc.id).delete()
            doc.title = title
            doc.updated_at = models.func.now()
        else:
            doc = models.Document(title=title, source=doc_source)
            db.add(doc)
            
        db.commit()
        db.refresh(doc)
        
        # Sinh embeddings và lưu các chunks
        inserted_chunks = 0
        batch_size = 30
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            print(f"  -> Sinh vector embeddings cho chunks {i+1} đến {i+len(batch)}...")
            
            # Gọi hàm sinh embedding
            for c_text in batch:
                vector = get_embedding(c_text)
                chunk_obj = models.KnowledgeChunk(
                    document_id=doc.id,
                    text=c_text,
                    embedding=vector
                )
                db.add(chunk_obj)
                inserted_chunks += 1
            db.commit()
            time.sleep(0.2) # Tránh rate limit
            
        # Lưu các mappings hình ảnh
        inserted_images = 0
        for hinh_key, img_rel_path in image_mappings.items():
            img_map = models.ImageMapping(
                document_id=doc.id,
                hinh_key=hinh_key,
                img_rel_path=img_rel_path
            )
            db.add(img_map)
            inserted_images += 1
        db.commit()
        
        print(f"[+] Nạp thành công! Đã thêm {inserted_chunks} chunks và {inserted_images} ảnh minh họa.")
        return {
            "status": "success",
            "message": f"Nạp tài liệu thành công!",
            "details": {
                "title": title,
                "chunks": inserted_chunks,
                "images": inserted_images
            }
        }
    except Exception as e:
        db.rollback()
        print(f"[!] Lỗi ghi dữ liệu nạp tri thức vào DB: {e}")
        return {"status": "error", "message": f"Lỗi ghi dữ liệu vào CSDL: {str(e)}"}
    finally:
        db.close()
