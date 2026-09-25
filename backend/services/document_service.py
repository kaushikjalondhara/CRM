"""
CRM Document Management Service
Secure upload, validation, storage, and retrieval of documents for Customers, Leads, Invoices, and Deals.
"""

import os
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from database.database import execute_query
from backend.services.activity_service import log_activity
from backend.services.audit_service import log_audit

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DOCUMENTS_FOLDER = BASE_DIR / "uploads" / "documents"

ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'png', 'jpg', 'jpeg', 'txt', 'csv'
}
PROHIBITED_EXTENSIONS = {
    'exe', 'bat', 'sh', 'py', 'js', 'php', 'vbs', 'cmd', 'ps1', 'msi', 'bin', 'com'
}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB


def _ensure_documents_dir():
    """Ensure upload directory exists."""
    os.makedirs(DOCUMENTS_FOLDER, exist_ok=True)


def is_allowed_file(filename: str) -> bool:
    """Validate file extension against security whitelists."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS and ext not in PROHIBITED_EXTENSIONS


def save_document(file_obj, entity_type: str, entity_id: int, user_id: int | None = None, notes: str | None = None) -> tuple[dict | None, str | None]:
    """
    Validate, securely save, and index a file document.
    """
    _ensure_documents_dir()

    if not file_obj or not file_obj.filename:
        return None, "No file provided"

    raw_filename = file_obj.filename
    if not is_allowed_file(raw_filename):
        return None, f"File type not permitted. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"

    ext = raw_filename.rsplit(".", 1)[1].lower()
    safe_orig = secure_filename(raw_filename)
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    dest_path = DOCUMENTS_FOLDER / unique_name

    try:
        file_obj.save(str(dest_path))
        file_size = os.path.getsize(dest_path)
    except Exception as ex:
        return None, f"Failed to save file: {str(ex)}"

    if file_size > MAX_FILE_SIZE:
        try:
            os.remove(dest_path)
        except Exception:
            pass
        return None, "File exceeds maximum permitted size of 16MB"

    rel_path = f"uploads/documents/{unique_name}"

    sql = """
        INSERT INTO documents (entity_type, entity_id, file_name, original_name, file_path, file_type, file_size, uploaded_by, notes, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """
    res, err = execute_query(sql, (
        entity_type, entity_id, unique_name, safe_orig, rel_path, ext, file_size, user_id, notes
    ), commit=True)

    if err:
        try:
            os.remove(dest_path)
        except Exception:
            pass
        return None, err

    doc_id = res.get("last_id") if isinstance(res, dict) else res
    log_activity(user_id, entity_type, entity_id, "document_uploaded", f"Uploaded document '{safe_orig}' ({round(file_size/1024, 1)} KB)")
    log_audit(user_id, "upload", "document", doc_id, None, {"name": safe_orig, "size": file_size, "entity": entity_type, "entity_id": entity_id})

    return {
        "id": doc_id,
        "original_name": safe_orig,
        "file_name": unique_name,
        "file_type": ext,
        "file_size": file_size,
        "created_at": None
    }, None


def list_documents(entity_type: str | None = None, entity_id: int | None = None) -> list:
    """List documents optionally filtered by entity."""
    where = []
    params = []

    if entity_type:
        where.append("d.entity_type = %s")
        params.append(entity_type)
    if entity_id:
        where.append("d.entity_id = %s")
        params.append(entity_id)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = f"""
        SELECT d.id, d.entity_type, d.entity_id, d.file_name, d.original_name,
               d.file_path, d.file_type, d.file_size, d.uploaded_by, d.notes, d.created_at,
               u.first_name, u.last_name
        FROM documents d
        LEFT JOIN users u ON d.uploaded_by = u.id
        {where_sql}
        ORDER BY d.id DESC
    """
    rows, _ = execute_query(sql, tuple(params), fetch_all=True)

    docs = []
    for r in (rows or []):
        uname = f"{r['first_name']} {r['last_name']}".strip() if r.get("first_name") else "Staff"
        docs.append({
            "id": r["id"],
            "entity_type": r["entity_type"],
            "entity_id": r["entity_id"],
            "file_name": r["file_name"],
            "original_name": r["original_name"],
            "file_type": r["file_type"],
            "file_size": r["file_size"],
            "uploaded_by_name": uname,
            "notes": r.get("notes") or "",
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r.get("created_at") else None
        })
    return docs


def get_document(doc_id: int) -> tuple[dict | None, str | None]:
    """Retrieve metadata of a single document."""
    sql = "SELECT id, entity_type, entity_id, file_name, original_name, file_path, file_type, file_size FROM documents WHERE id = %s"
    r, err = execute_query(sql, (doc_id,), fetch_one=True)
    if err or not r:
        return None, err or "Document not found"
    return r, None


def delete_document(doc_id: int, user_id: int | None = None) -> tuple[bool, str | None]:
    """Remove a document from database and filesystem."""
    doc, err = get_document(doc_id)
    if err or not doc:
        return False, "Document not found"

    # Remove file on disk
    file_path = BASE_DIR / doc["file_path"]
    try:
        if file_path.exists():
            os.remove(file_path)
    except Exception:
        pass

    sql = "DELETE FROM documents WHERE id = %s"
    _, err = execute_query(sql, (doc_id,), commit=True)
    if err:
        return False, err

    log_audit(user_id, "delete", "document", doc_id, {"name": doc["original_name"]}, None)
    return True, None
