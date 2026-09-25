"""
CRM Email Routes
API endpoints for email logs, composing emails, and email templates.
"""

from flask import Blueprint, request, jsonify, g
from backend.utils.decorators import login_required
from backend.services.email_service import (
    list_emails,
    get_email,
    compose_email,
    list_templates,
    get_template,
    create_template,
    update_template,
    delete_template,
    is_smtp_configured
)

email_blueprint = Blueprint("emails", __name__, url_prefix="/api/emails")


# -------------------------------------------------------------
# Template Endpoints
# -------------------------------------------------------------

@email_blueprint.route("/templates", methods=["GET"])
@login_required
def get_templates():
    """GET /api/emails/templates - List all email templates."""
    templates, err = list_templates()
    if err:
        return jsonify({"success": False, "message": "Failed to fetch email templates"}), 500
    return jsonify({"success": True, "templates": templates}), 200


@email_blueprint.route("/templates/<int:template_id>", methods=["GET"])
@login_required
def get_single_template(template_id):
    """GET /api/emails/templates/<id> - Get single email template."""
    tmpl, err = get_template(template_id)
    if err:
        return jsonify({"success": False, "message": err}), 404
    return jsonify({"success": True, "template": tmpl}), 200


@email_blueprint.route("/templates", methods=["POST"])
@login_required
def add_template():
    """POST /api/emails/templates - Create new email template."""
    data = request.get_json() or {}
    user_id = g.user["id"]
    tmpl_id, err = create_template(data, user_id=user_id)
    if err:
        return jsonify({"success": False, "message": err}), 400

    tmpl, _ = get_template(tmpl_id)
    return jsonify({"success": True, "message": "Template created successfully", "template": tmpl}), 201


@email_blueprint.route("/templates/<int:template_id>", methods=["PUT"])
@login_required
def edit_template(template_id):
    """PUT /api/emails/templates/<id> - Update existing email template."""
    data = request.get_json() or {}
    user_id = g.user["id"]
    ok, err = update_template(template_id, data, user_id=user_id)
    if err:
        return jsonify({"success": False, "message": err}), 400

    tmpl, _ = get_template(template_id)
    return jsonify({"success": True, "message": "Template updated successfully", "template": tmpl}), 200


@email_blueprint.route("/templates/<int:template_id>", methods=["DELETE"])
@login_required
def remove_template(template_id):
    """DELETE /api/emails/templates/<id> - Delete an email template."""
    user_id = g.user["id"]
    ok, err = delete_template(template_id, user_id=user_id)
    if not ok:
        return jsonify({"success": False, "message": err or "Failed to delete template"}), 400
    return jsonify({"success": True, "message": "Template deleted successfully"}), 200


# -------------------------------------------------------------
# Email Logging & Compose Endpoints
# -------------------------------------------------------------

@email_blueprint.route("", methods=["GET"])
@login_required
def get_emails():
    """
    GET /api/emails
    List emails with search, customer_id, lead_id, deal_id, status filters.
    """
    search = request.args.get("search")
    customer_id = request.args.get("customer_id")
    customer_id = int(customer_id) if customer_id and customer_id.isdigit() else None
    lead_id = request.args.get("lead_id")
    lead_id = int(lead_id) if lead_id and lead_id.isdigit() else None
    deal_id = request.args.get("deal_id")
    deal_id = int(deal_id) if deal_id and deal_id.isdigit() else None
    status = request.args.get("status")
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))

    data, err = list_emails(
        search=search, customer_id=customer_id, lead_id=lead_id,
        deal_id=deal_id, status=status, page=page, per_page=per_page
    )
    if err:
        return jsonify({"success": False, "message": "Failed to fetch emails"}), 500

    return jsonify({"success": True, "data": data}), 200


@email_blueprint.route("/<int:email_id>", methods=["GET"])
@login_required
def get_one_email(email_id):
    """GET /api/emails/<id> - View single email details."""
    email, err = get_email(email_id)
    if err:
        return jsonify({"success": False, "message": err}), 404
    return jsonify({"success": True, "email": email}), 200


@email_blueprint.route("", methods=["POST"])
@login_required
def send_email():
    """
    POST /api/emails
    Compose email. In development mode (SMTP not configured), safely saves as draft with clear notice.
    """
    data = request.get_json() or {}
    user_id = g.user["id"]
    result, err = compose_email(data, user_id=user_id)
    if err:
        return jsonify({"success": False, "message": err}), 400

    email_record, _ = get_email(result["email_id"])
    return jsonify({
        "success": True,
        "message": result["message"],
        "email": email_record,
        "is_smtp_configured": result["is_smtp_configured"]
    }), 201


@email_blueprint.route("/smtp-status", methods=["GET"])
@login_required
def check_smtp():
    """GET /api/emails/smtp-status - Check if SMTP is configured."""
    configured = is_smtp_configured()
    return jsonify({
        "success": True,
        "is_smtp_configured": configured,
        "message": "SMTP is ready for sending" if configured else "Email sending is not configured (missing SMTP settings in .env)"
    }), 200
