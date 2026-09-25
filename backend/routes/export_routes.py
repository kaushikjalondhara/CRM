"""
CRM Export Routes
Endpoints for exporting data to CSV, Excel, and PDF.
"""

from flask import Blueprint, request, send_file, jsonify, g
from backend.services.export_service import export_data
from backend.services.pdf_service import generate_invoice_pdf
from backend.utils.decorators import login_required

export_blueprint = Blueprint("export", __name__, url_prefix="/api/export")


@export_blueprint.route("/<module>", methods=["GET"])
@login_required
def export_module(module):
    """
    GET /api/export/<module>?format=csv|xlsx|pdf
    Exports filtered dataset as file attachment.
    """
    fmt = request.args.get("format", "csv").lower().strip()
    filters = {
        "search": request.args.get("search", ""),
        "status": request.args.get("status"),
        "assigned_to": request.args.get("assigned_to", type=int),
        "start_date": request.args.get("start_date"),
        "end_date": request.args.get("end_date"),
        "invoice_id": request.args.get("invoice_id", type=int)
    }

    buf, filename, mimetype, err = export_data(
        module=module,
        export_format=fmt,
        filters=filters,
        current_user=g.current_user
    )

    if err:
        return jsonify({"success": False, "message": err}), 400

    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype
    )


@export_blueprint.route("/invoices/<int:invoice_id>/pdf", methods=["GET"])
@login_required
def download_invoice_pdf(invoice_id):
    """
    GET /api/export/invoices/<id>/pdf
    Direct shortcut for downloading invoice PDF.
    """
    buf, filename, err = generate_invoice_pdf(invoice_id)
    if err or not buf:
        return jsonify({"success": False, "message": err or "Failed to generate PDF"}), 400

    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )
