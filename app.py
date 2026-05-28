"""
Flask web frontend for DistRes.

This app keeps the previous browser pages, but it no longer owns the shared
resources. It acts as a web adapter that sends JSON newline-delimited TCP
messages to the DistRes server.
"""

import uuid

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from web.web_client_registry import web_client_registry


app = Flask(__name__)
app.secret_key = "key"


def get_web_client(create=True):
    """Returns the TCP client associated with the current browser session."""

    web_client_id = session.get("web_client_id")

    if web_client_id is None:
        if not create:
            return None

        web_client_id = str(uuid.uuid4())
        session["web_client_id"] = web_client_id

    return web_client_registry.get_or_create(web_client_id)


def remove_web_client():
    """Removes the TCP client associated with the browser session."""

    web_client_id = session.get("web_client_id")

    if web_client_id:
        web_client_registry.remove(web_client_id)


def tcp_request(message_type, payload=None, expected_types=None, timeout=5):
    """Sends a TCP message to DistRes and waits for the expected response."""

    client = get_web_client()
    response = client.request(
        message_type,
        payload=payload or {},
        expected_types=expected_types,
        timeout=timeout
    )

    if response is None:
        raise TimeoutError(f"No TCP response for {message_type}")

    return response


def process_promotions():
    """Consumes async login_response messages for waiting-user promotion."""

    client = get_web_client(create=False)
    if client is None:
        return False

    promoted = False

    for message in client.pop_messages({"login_response"}):
        payload = message.get("payload", {})

        if payload.get("success") and payload.get("status") == "active":
            session["login_status"] = "active"
            session["user"] = payload.get("user")
            session["distres_session_token"] = payload.get("session_token")
            promoted = True

    return promoted


def collect_notifications():
    """Returns queued browser notifications from asynchronous TCP messages."""

    client = get_web_client(create=False)
    if client is None:
        return []

    notifications = []

    for message in client.pop_messages({
        "resource_updated",
        "login_response",
        "file_access_granted"
    }):
        message_type = message.get("type")
        payload = message.get("payload", {})

        if message_type == "login_response":
            if payload.get("success") and payload.get("status") == "active":
                session["login_status"] = "active"
                session["user"] = payload.get("user")
                session["distres_session_token"] = payload.get("session_token")
                notifications.append({
                    "type": "promotion",
                    "message": payload.get(
                        "message",
                        "A system slot is now available."
                    )
                })

        if message_type == "resource_updated":
            notifications.append({
                "type": "resource_updated",
                "message": payload.get(
                    "message",
                    "ProductSpecification.txt was updated."
                ),
                "updated_by": payload.get("updated_by")
            })

        if message_type == "file_access_granted":
            mode = payload.get("mode")
            session["file_mode"] = mode

            notifications.append({
                "type": "file_access_granted",
                "mode": mode,
                "message": payload.get(
                    "message",
                    "Queued file access has now been granted."
                )
            })

    return notifications


def require_logged_in():
    """Returns False if the browser session has no DistRes login."""

    return bool(session.get("web_client_id") and session.get("user"))


def current_state():
    """Fetches a system_state_response payload from the DistRes server."""

    response = tcp_request(
        "system_state_request",
        expected_types={"system_state_response", "error"}
    )

    if response.get("type") == "error":
        raise RuntimeError(response.get("payload", {}).get("error", "Server error"))

    return response.get("payload", {}).get("state", {})


def file_queue_labels(file_queue):
    """Formats queue entries for display in the old dashboard template."""

    labels = []

    for item in file_queue or []:
        labels.append(f"{item.get('user')} ({item.get('mode')})")

    return labels


def render_dashboard(message=None):
    """Renders the dashboard using state from the TCP server."""

    state = current_state()

    return render_template(
        "dashboard.html",
        current_user=session.get("user"),
        login_status=session.get("login_status", "active"),
        active_users=state.get("active_users", []),
        waiting_users=state.get("waiting_users", []),
        file_status=state.get("file_status", "Idle"),
        active_readers=state.get("active_readers", []),
        active_writer=state.get("active_writer"),
        file_queue=file_queue_labels(state.get("file_queue", [])),
        message=message
    )


def ensure_active_or_redirect():
    """Checks whether the browser session is an active DistRes user."""

    if not require_logged_in():
        return redirect(url_for("login"))

    process_promotions()

    if session.get("login_status") != "active":
        return redirect(url_for("waiting"))

    return None


@app.route("/", methods=["GET", "POST"])
def login():
    """Logs a browser user into DistRes through the TCP server."""

    if request.method == "POST":
        remove_web_client()
        session.clear()

        user_id = request.form.get("id", "").strip()
        username = request.form.get("username", "").strip()
        try:
            response = tcp_request(
                "login_request",
                payload={
                    "user_id": user_id,
                    "username": username
                },
                expected_types={"login_response", "error"}
            )

        except Exception as error:
            remove_web_client()
            session.clear()
            return render_template(
                "login.html",
                error=f"Could not reach DistRes TCP server: {error}"
            )

        if response.get("type") == "error":
            return render_template(
                "login.html",
                error=response.get("payload", {}).get("error", "Server error")
            )

        payload = response.get("payload", {})

        if not payload.get("success"):
            remove_web_client()
            session.clear()
            return render_template(
                "login.html",
                error=payload.get("reason", "Login failed.")
            )

        session["user"] = payload.get("user")
        session["login_status"] = payload.get("status")
        session["distres_session_token"] = payload.get("session_token")
        session["file_mode"] = None

        try:
            tcp_request(
                "subscribe_updates",
                expected_types={"subscribe_updates", "access_denied", "error"}
            )
        except Exception:
            pass

        if session["login_status"] == "active":
            return redirect(url_for("dashboard"))

        return redirect(url_for("waiting"))

    return render_template("login.html")


@app.route("/waiting")
def waiting():
    """Shows the waiting queue page for authenticated waiting users."""

    if not require_logged_in():
        return redirect(url_for("login"))

    process_promotions()

    if session.get("login_status") == "active":
        return redirect(url_for("dashboard"))

    return render_template("waiting.html", current_user=session.get("user"))


@app.route("/queue-status")
def queue_status():
    """Returns waiting/active status for frontend polling."""

    if not require_logged_in():
        return jsonify({"status": "not_logged_in"})

    if process_promotions() or session.get("login_status") == "active":
        return jsonify({"status": "active"})

    try:
        state = current_state()
    except Exception:
        return jsonify({"status": "server_unavailable"})

    user = session.get("user")
    active_users = state.get("active_users", [])
    waiting_users = state.get("waiting_users", [])

    if user in active_users:
        session["login_status"] = "active"
        return jsonify({"status": "active"})

    position = (
        waiting_users.index(user) + 1
        if user in waiting_users else None
    )

    return jsonify({
        "status": "waiting",
        "position": position
    })


@app.route("/dashboard")
def dashboard():
    """Renders live DistRes state through the old dashboard page."""

    redirect_response = ensure_active_or_redirect()
    if redirect_response is not None:
        return redirect_response

    if session.get("file_mode") is not None:
        try:
            tcp_request(
                "leave_file_mode_request",
                expected_types={"leave_file_mode_response", "error"}
            )
        finally:
            session["file_mode"] = None

    try:
        return render_dashboard()
    except Exception as error:
        remove_web_client()
        session.clear()
        return render_template(
            "login.html",
            error=f"DistRes TCP server is unavailable: {error}"
        )


@app.route("/system-state")
def system_state():
    """Returns live system state to dashboard polling."""

    if not require_logged_in():
        return jsonify({"error": "not_authorised"}), 403

    process_promotions()

    if session.get("login_status") != "active":
        return jsonify({"error": "not_active"}), 403

    try:
        state = current_state()
    except Exception as error:
        return jsonify({"error": str(error)}), 503

    return jsonify({
        "active_users": state.get("active_users", []),
        "waiting_users": state.get("waiting_users", []),
        "file_status": state.get("file_status", "Idle"),
        "active_readers": state.get("active_readers", []),
        "active_writer": state.get("active_writer"),
        "file_queue": file_queue_labels(state.get("file_queue", []))
    })


@app.route("/notifications")
def notifications():
    """Returns async DistRes notifications to browser polling."""

    if not require_logged_in():
        return jsonify({"notifications": []})

    return jsonify({
        "notifications": collect_notifications(),
        "login_status": session.get("login_status")
    })


@app.route("/document")
def document():
    """Requests read mode from DistRes and renders ProductSpecification.txt."""

    redirect_response = ensure_active_or_redirect()
    if redirect_response is not None:
        return redirect_response

    if session.get("file_mode") == "write":
        tcp_request(
            "leave_file_mode_request",
            expected_types={"leave_file_mode_response", "error"}
        )
        session["file_mode"] = None

    response = tcp_request(
        "read_file_request",
        expected_types={"read_file_response", "queued", "access_denied", "error"}
    )

    if response.get("type") == "read_file_response":
        payload = response.get("payload", {})
        session["file_mode"] = "read"
        return render_template("document.html", content=payload.get("content", ""))

    payload = response.get("payload", {})
    return render_dashboard(
        message=payload.get("reason", "The shared file is not available yet.")
    )


@app.route("/edit-document", methods=["GET", "POST"])
def edit_document():
    """Requests write mode and commits updates through DistRes TCP messages."""

    redirect_response = ensure_active_or_redirect()
    if redirect_response is not None:
        return redirect_response

    if request.method == "POST":
        if session.get("file_mode") != "write":
            write_response = tcp_request(
                "write_file_request",
                expected_types={
                    "write_file_response",
                    "queued",
                    "access_denied",
                    "error"
                }
            )

            if write_response.get("type") != "write_file_response":
                payload = write_response.get("payload", {})
                return render_dashboard(
                    message=payload.get("reason", "Write mode was not granted.")
                )

        commit_response = tcp_request(
            "write_file_commit",
            payload={"content": request.form.get("content", "")},
            expected_types={
                "write_file_commit_response",
                "access_denied",
                "error"
            }
        )

        if commit_response.get("type") == "write_file_commit_response":
            session["file_mode"] = None
            return redirect(url_for("dashboard"))

        payload = commit_response.get("payload", {})
        return render_dashboard(
            message=payload.get("reason", "The write commit was rejected.")
        )

    if session.get("file_mode") == "read":
        tcp_request(
            "leave_file_mode_request",
            expected_types={"leave_file_mode_response", "error"}
        )
        session["file_mode"] = None

    response = tcp_request(
        "write_file_request",
        expected_types={"write_file_response", "queued", "access_denied", "error"}
    )

    if response.get("type") == "write_file_response":
        payload = response.get("payload", {})
        session["file_mode"] = "write"
        return render_template(
            "edit_document.html",
            content=payload.get("content", "")
        )

    payload = response.get("payload", {})
    message = payload.get("reason", "Write mode is currently queued.")

    if response.get("type") == "queued":
        message = (
            f"{message} Keep this dashboard open; the editor will open "
            "automatically when you reach the front of the queue."
        )

    return render_dashboard(
        message=message
    )


@app.route("/leave-file-mode", methods=["POST"])
def leave_file_mode():
    """Releases read/write mode held by this browser session."""

    if not require_logged_in():
        return ("", 204)

    try:
        tcp_request(
            "leave_file_mode_request",
            expected_types={"leave_file_mode_response", "error"},
            timeout=2
        )
    except Exception:
        pass

    session["file_mode"] = None
    return ("", 204)


@app.route("/logout")
def logout():
    """Logs the browser user out of DistRes and removes the TCP adapter."""

    if session.get("web_client_id"):
        try:
            tcp_request(
                "logout_request",
                expected_types={"logout_response", "error"},
                timeout=3
            )
        except Exception:
            pass

    remove_web_client()
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True, threaded=True, use_reloader=False)
