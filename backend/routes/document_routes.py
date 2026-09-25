"""
CRM Document Routes
Endpoints for uploading, listing, downloading, and deleting files.
"""

from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, g
from backend.services.document_service import (
    save_document,
    list_documents,
    get_document,
    delete_document,
    BASE_DIR
)
from backend.utils.decorators import login_required

document_blueprint = Blueprint("documents", __name__, url_prefix="/api/documents")


@document_blueprint.route("/upload", methods=["POST"])
@login_required
def upload_file():
    """
    POST /api/documents/upload
    Multipart upload with entity_type and entity_id.
    """
    file_obj = request.files.get("file")
    entity_type = request.form.get("entity_type", "customer").lower().strip()
    entity_id = request.form.get("entity_id", type=int)
    notes = request.form.get("notes")

    if not entity_id:
        return jsonify({"success": False, "message": "entity_id is required"}), 400

    doc, err = save_document(
        file_obj=file_obj,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=g.current_user["id"],
        notes=notes
    )

    if err:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({
        "success": True,
        "message": "File uploaded successfully",
        "document": doc
    }), 201


@document_blueprint.route("", methods=["GET"])
@login_required
def get_documents():
    """
    GET /api/documents?entity_type=...&entity_id=...
    Lists documents for a specific entity or globally.
    """
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id", type=int)

    docs = list_documents(entity_type=entity_type, entity_id=entity_id)
    return jsonify({
        "success": True,
        "documents": docs,
        "count": len(docs)
    }), 200


@document_blueprint.route("/<int:doc_id>/download", methods=["GET"])
@login_required
def download_file(doc_id):
    """
    GET /api/documents/<id>/download
    Download document file securely.
    """
    doc, err = get_document(doc_id)
    if err or not doc:
        return jsonify({"success": False, "message": err or "Document not found"}), 404

    file_path = BASE_DIR / doc["file_path"]
    if not file_path.exists():
        return jsonify({"success": False, "message": "File not found on storage server"}), 404

    return send_file(
        str(file_path),
        as_attachment=True,
        download_name=doc["original_name"]
    )


@document_blueprint.route("/<int:doc_id>", methods=["DELETE"])
@login_required
def remove_document(doc_id):
    """DELETE /api/documents/<id> - Delete document."""
    ok, err = delete_document(doc_id, user_id=g.current_user["id"])
    if not ok:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({
        "success": True,
        "message": "Document deleted successfully"
    }), 200
