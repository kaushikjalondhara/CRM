import os
import sys
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request

from flask_cors import CORS


# Ensure root and backend directories are on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from backend.config import Config, config_by_name
    from backend.routes.auth_routes import auth_blueprint
    from backend.routes.user_routes import user_blueprint
    from backend.routes.dashboard_routes import dashboard_blueprint
    from backend.routes.customer_routes import customer_blueprint
    from backend.routes.lead_routes import lead_blueprint
    from backend.routes.deal_routes import deal_blueprint
    from backend.routes.task_routes import task_blueprint
    from backend.routes.call_routes import call_blueprint
    from backend.routes.meeting_routes import meeting_blueprint
    from backend.routes.product_routes import product_blueprint
    from backend.routes.invoice_routes import invoice_blueprint
    from backend.routes.payment_routes import payment_blueprint
    from backend.routes.email_routes import email_blueprint
    from backend.routes.notification_routes import notification_blueprint
    from backend.routes.report_routes import report_blueprint
    from backend.routes.role_routes import role_blueprint
    from backend.routes.settings_routes import settings_blueprint
    from backend.routes.search_routes import search_blueprint
    from backend.routes.export_routes import export_blueprint
    from backend.routes.calendar_routes import calendar_blueprint
    from backend.routes.audit_routes import audit_blueprint
    from backend.routes.document_routes import document_blueprint
    from backend.routes.backup_routes import backup_blueprint
    from backend.routes.import_routes import import_blueprint
    from backend.routes.reminder_routes import reminder_blueprint
except ImportError:
    from config import Config, config_by_name
    from routes.auth_routes import auth_blueprint
    from routes.user_routes import user_blueprint
    from routes.dashboard_routes import dashboard_blueprint
    from routes.customer_routes import customer_blueprint
    from routes.lead_routes import lead_blueprint
    from routes.deal_routes import deal_blueprint
    from routes.task_routes import task_blueprint
    from routes.call_routes import call_blueprint
    from routes.meeting_routes import meeting_blueprint
    from routes.product_routes import product_blueprint
    from routes.invoice_routes import invoice_blueprint
    from routes.payment_routes import payment_blueprint
    from routes.email_routes import email_blueprint
    from routes.notification_routes import notification_blueprint
    from routes.report_routes import report_blueprint
    from routes.role_routes import role_blueprint
    from routes.settings_routes import settings_blueprint
    from routes.search_routes import search_blueprint
    from routes.export_routes import export_blueprint
    from routes.calendar_routes import calendar_blueprint
    from routes.audit_routes import audit_blueprint
    from routes.document_routes import document_blueprint
    from routes.backup_routes import backup_blueprint
    from routes.import_routes import import_blueprint
    from routes.reminder_routes import reminder_blueprint


import datetime
import decimal
from flask.json.provider import DefaultJSONProvider


class CustomJSONProvider(DefaultJSONProvider):
    def default(self, o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        if isinstance(o, datetime.time):
            return o.strftime("%H:%M:%S")
        if isinstance(o, datetime.timedelta):
            total_seconds = int(o.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super().default(o)


def create_app(config_class=None):
    """
    Application factory pattern to create and configure the Flask app.
    """
    frontend_dir = BASE_DIR / "frontend"
    app = Flask(__name__, static_folder=str(frontend_dir), static_url_path="")
    app.json_provider_class = CustomJSONProvider
    app.json = CustomJSONProvider(app)

    # Load configuration
    if config_class is None:
        env_name = os.getenv("FLASK_ENV", "development")
        config_class = config_by_name.get(env_name, Config)

    app.config.from_object(config_class)

    # Configure CORS
    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*")}})

    # Register blueprints
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(user_blueprint)
    app.register_blueprint(dashboard_blueprint)
    app.register_blueprint(customer_blueprint)
    app.register_blueprint(lead_blueprint)
    app.register_blueprint(deal_blueprint)
    app.register_blueprint(task_blueprint)
    app.register_blueprint(call_blueprint)
    app.register_blueprint(meeting_blueprint)
    app.register_blueprint(product_blueprint)
    app.register_blueprint(invoice_blueprint)
    app.register_blueprint(payment_blueprint)
    app.register_blueprint(email_blueprint)
    app.register_blueprint(notification_blueprint)
    app.register_blueprint(report_blueprint)
    app.register_blueprint(role_blueprint)
    app.register_blueprint(settings_blueprint)
    app.register_blueprint(search_blueprint)
    app.register_blueprint(export_blueprint)
    app.register_blueprint(calendar_blueprint)
    app.register_blueprint(audit_blueprint)
    app.register_blueprint(document_blueprint)
    app.register_blueprint(backup_blueprint)
    app.register_blueprint(import_blueprint)
    app.register_blueprint(reminder_blueprint)

    # Start automated reminder background daemon
    try:
        from backend.services.reminder_service import start_reminder_scheduler
        start_reminder_scheduler()
    except Exception:
        pass

    # API discovery endpoint
    @app.route("/api", methods=["GET"])
    @app.route("/api/", methods=["GET"])
    def api_discovery():
        return jsonify({
            "name": "CRM API",
            "version": "1.0.0",
            "status": "online",
            "endpoints": {
                "health": "/api/health",
                "auth_login": "/api/auth/login",
                "auth_logout": "/api/auth/logout",
                "auth_me": "/api/auth/me"
            }
        }), 200

    # Required health-check endpoint
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "success": True,
            "message": "CRM API is running"
        }), 200

    # Static file serving for uploads (profile images, documents, templates)
    @app.route("/uploads/<path:filename>", methods=["GET"])
    def serve_uploaded_file(filename):
        uploads_dir = BASE_DIR / "uploads"
        return send_from_directory(uploads_dir, filename)

    # Root route for serving frontend index.html or API discovery
    @app.route("/", methods=["GET"])
    def index():
        if request.headers.get("Accept") == "application/json" or request.args.get("json"):
            return api_discovery()
        if (frontend_dir / "index.html").exists():
            return send_from_directory(frontend_dir, "index.html")
        return api_discovery()


    # Catch-all route to serve frontend HTML/CSS/JS pages and assets
    @app.route("/<path:path>", methods=["GET"])
    def serve_frontend(path):
        if path.startswith("api/"):
            return jsonify({
                "success": False,
                "error": "Endpoint not found",
                "message": "The requested API endpoint was not found"
            }), 404
        file_path = frontend_dir / path
        if file_path.exists() and file_path.is_file():
            return send_from_directory(frontend_dir, path)
        if (frontend_dir / "index.html").exists():
            return send_from_directory(frontend_dir, "index.html")
        return jsonify({
            "success": False,
            "error": "Not found"
        }), 404



    # Standardized API error handlers returning clean JSON
    @app.errorhandler(400)
    def bad_request_error(error):
        return jsonify({
            "success": False,
            "error": "Bad request",
            "message": str(getattr(error, "description", "Invalid request payload"))
        }), 400

    @app.errorhandler(401)
    def unauthorized_error(error):
        return jsonify({
            "success": False,
            "error": "Unauthorized",
            "message": "Authentication required to access this resource"
        }), 401

    @app.errorhandler(403)
    def forbidden_error(error):
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "You do not have permission to access this resource"
        }), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({
            "success": False,
            "error": "Endpoint not found",
            "message": "The requested API endpoint was not found"
        }), 404

    @app.errorhandler(405)
    def method_not_allowed_error(error):
        return jsonify({
            "success": False,
            "error": "Method not allowed",
            "message": "HTTP method not supported for this endpoint"
        }), 405

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected server error occurred"
        }), 500

    return app


app = create_app()

if __name__ == "__main__":
    port = app.config.get("PORT", 5000)
    host = app.config.get("HOST", "127.0.0.1")
    debug = app.config.get("DEBUG", True)
    app.run(host=host, port=port, debug=debug)
