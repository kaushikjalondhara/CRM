"""
CRM Task Routes
Endpoints for assigning, monitoring, and completing CRM tasks and action items.
"""

from flask import Blueprint, request, jsonify, g
from backend.services.task_service import (
    list_tasks,
    get_task_by_id,
    create_task,
    update_task,
    update_task_status,
    delete_task
)
from backend.utils.decorators import login_required, permission_required

task_blueprint = Blueprint("tasks", __name__, url_prefix="/api/tasks")


@task_blueprint.route("", methods=["GET"])
@login_required
@permission_required("tasks.view")
def get_tasks():
    """GET /api/tasks: List and filter tasks."""
    search = request.args.get("search")
    status = request.args.get("status")
    priority = request.args.get("priority")
    assigned_to = request.args.get("assigned_to", type=int)
    customer_id = request.args.get("customer_id", type=int)
    lead_id = request.args.get("lead_id", type=int)
    deal_id = request.args.get("deal_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 15, type=int)

    result = list_tasks(
        search=search, status=status, priority=priority,
        assigned_to=assigned_to, customer_id=customer_id,
        lead_id=lead_id, deal_id=deal_id, page=page, per_page=per_page
    )
    return jsonify(result), 200


@task_blueprint.route("", methods=["POST"])
@login_required
@permission_required("tasks.create")
def create():
    """POST /api/tasks: Schedule or assign a new task."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = create_task(data, user_id)
    return jsonify(result), status_code


@task_blueprint.route("/<int:task_id>", methods=["GET"])
@login_required
@permission_required("tasks.view")
def get_one(task_id):
    """GET /api/tasks/<id>: Retrieve single task."""
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({"success": False, "message": "Task not found"}), 404
    return jsonify({"success": True, "task": task}), 200


@task_blueprint.route("/<int:task_id>", methods=["PUT"])
@login_required
@permission_required("tasks.update")
def update(task_id):
    """PUT /api/tasks/<id>: Update task attributes."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = update_task(task_id, data, user_id)
    return jsonify(result), status_code


@task_blueprint.route("/<int:task_id>/status", methods=["PUT"])
@login_required
@permission_required("tasks.update")
def update_status(task_id):
    """PUT /api/tasks/<id>/status: Quick status change (e.g. mark completed)."""
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    user_id = g.current_user["id"]
    result, status_code = update_task_status(task_id, status, user_id)
    return jsonify(result), status_code


@task_blueprint.route("/<int:task_id>", methods=["DELETE"])
@login_required
@permission_required("tasks.delete")
def delete(task_id):
    """DELETE /api/tasks/<id>: Remove task."""
    user_id = g.current_user["id"]
    result, status_code = delete_task(task_id, user_id)
    return jsonify(result), status_code


@task_blueprint.route("/bulk-action", methods=["POST"])
@login_required
@permission_required("tasks.update")
def bulk_tasks():
    """POST /api/tasks/bulk-action: Batch delete, status, priority, or assign."""
    from backend.services.task_service import bulk_action_tasks
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    ids = payload.get("ids", [])
    value = payload.get("value")

    result, err = bulk_action_tasks(action=action, ids=ids, value=value, user_id=g.current_user["id"])
    if err:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({"success": True, "message": "Bulk action completed", "result": result}), 200

