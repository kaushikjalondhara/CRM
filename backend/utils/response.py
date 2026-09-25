from flask import jsonify

def api_response(success=True, message="", data=None, status_code=200):
    payload = {"success": success, "message": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status_code
