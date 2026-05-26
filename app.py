"""
Main Flask application for the concurrency system.

Handles login/logout, active user admission, waiting queue flow,
file access routes, and live state endpoints used by the frontend.
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from core.auth import validate_user
from core.session_manager import SessionManager
from core.semaphore_manager import SemaphoreManager
from core.file_manager import FileManager
import uuid
import time

app = Flask(__name__)
app.secret_key = "key"

# Shared managers hold the global system state for the running app.
session_manager = SessionManager()
semaphore_manager = SemaphoreManager(max_active_users=4, session_manager=session_manager)
file_manager = FileManager("ProductSpecification.txt")


@app.route("/", methods=["GET", "POST"])
def login():
    """
    Authenticates a user and attempts to place them into the active user pool.

    If a semaphore slot is free, the user becomes active immediately.
    Otherwise, the user is placed into the waiting queue.
    """
    if request.method == "POST":
        user_id = request.form.get("id", "").strip()
        username = request.form.get("username", "").strip()

        if not validate_user(user_id, username):
            return render_template("login.html", error="Invalid ID or username")

        user = f"{user_id} - {username}"
        session_token = str(uuid.uuid4())

        login_status = semaphore_manager.request_login(session_token, user)

        if login_status == "duplicate":
            return render_template(
                "login.html",
                error="This user is already logged in or already in the waiting queue."
            )

        session.clear()
        session["user"] = user
        session["session_token"] = session_token
        session["login_status"] = login_status

        if login_status == "active":
            return redirect(url_for("dashboard"))

        return redirect(url_for("waiting"))

    return render_template("login.html")


@app.route("/waiting")
def waiting():
    """
    Displays the waiting page for users who are queued for system access.

    Once promoted to active, the page redirects them to the dashboard.
    """
    session_token = session.get("session_token")
    user = session.get("user")

    if not session_token or not user:
        return redirect(url_for("login"))

    session_data = session_manager.get_session(session_token)
    if not session_data:
        session.clear()
        return redirect(url_for("login"))

    if session_data["status"] == "active":
        session["login_status"] = "active"
        return redirect(url_for("dashboard"))

    if session_data["status"] != "waiting":
        session.clear()
        return redirect(url_for("login"))

    return render_template("waiting.html", current_user=user)


@app.route("/queue-status")
def queue_status():
    """
    Returns the current queue position/state for the logged-in user.

    Used by frontend polling so waiting users can be promoted cleanly
    without hanging the original login request.
    """
    session_token = session.get("session_token")
    if not session_token:
        return jsonify({"status": "not_logged_in"})

    session_data = session_manager.get_session(session_token)
    if not session_data:
        session.clear()
        return jsonify({"status": "expired"})

    if session_data["status"] == "active":
        session["login_status"] = "active"
        return jsonify({"status": "active"})

    if session_data["status"] == "waiting":
        waiting_tokens = session_manager.get_waiting_session_tokens()
        position = waiting_tokens.index(session_token) + 1 if session_token in waiting_tokens else None
        return jsonify({
            "status": "waiting",
            "position": position
        })

    session.clear()
    return jsonify({"status": "expired"})


@app.route("/dashboard")
def dashboard():
    """
    Main system page for active users.

    Also clears any held file access mode when the user returns to the dashboard,
    so read/write locks are not left active accidentally.
    """
    session_token = session.get("session_token")
    user = session.get("user")

    if not session_token or not user:
        return redirect(url_for("login"))

    session_data = session_manager.get_session(session_token)
    if not session_data:
        session.clear()
        return redirect(url_for("login"))

    if session_data["status"] != "active":
        return redirect(url_for("waiting"))

    current_mode = session.get("file_mode")
    if current_mode == "read":
        file_manager.stop_reading(user)
        session["file_mode"] = None
    elif current_mode == "write":
        file_manager.stop_writing(user)
        session["file_mode"] = None

    return render_template(
        "dashboard.html",
        current_user=user,
        login_status="active",
        active_users=session_manager.get_active_users(),
        waiting_users=session_manager.get_waiting_users(),
        file_status=file_manager.get_file_status(),
        active_readers=file_manager.get_active_readers(),
        active_writer=file_manager.get_active_writer()
    )


@app.route("/system-state")
def system_state():
    """
    Returns the current live system state for dashboard polling.

    This includes active users, waiting users, current file mode,
    active readers, and the active writer.
    """
    session_token = session.get("session_token")
    if not session_token:
        return jsonify({"error": "not_authorised"}), 403

    session_data = session_manager.get_session(session_token)
    if not session_data:
        session.clear()
        return jsonify({"error": "expired"}), 403

    if session_data["status"] != "active":
        return jsonify({"error": "not_active"}), 403

    return jsonify({
        "active_users": session_manager.get_active_users(),
        "waiting_users": session_manager.get_waiting_users(),
        "file_status": file_manager.get_file_status(),
        "active_readers": file_manager.get_active_readers(),
        "active_writer": file_manager.get_active_writer()
    })


@app.route("/document")
def document():
    """
    Opens the shared file in read mode.

    Multiple readers are allowed concurrently. If a writer is active,
    the user is redirected to the file access status page instead of blocking.
    """
    session_token = session.get("session_token")
    user = session.get("user")

    if not session_token or not user:
        return redirect(url_for("login"))

    session_data = session_manager.get_session(session_token)
    if not session_data:
        session.clear()
        return redirect(url_for("login"))

    if session_data["status"] != "active":
        return redirect(url_for("waiting"))

    current_mode = session.get("file_mode")

    # If this session was writing, release write mode before switching to read.
    if current_mode == "write":
        file_manager.stop_writing(user)
        session["file_mode"] = None
        current_mode = None

    if current_mode != "read":
        file_manager.start_reading(user)
        session["file_mode"] = "read"

    content = file_manager.read_file()
    return render_template("document.html", content=content)

@app.route("/edit-document", methods=["GET", "POST"])
def edit_document():
    """
    Opens or saves the shared file in write mode.

    Only one writer is allowed at a time. If read/write access is unavailable,
    the user is redirected to the file access status page instead of blocking.
    """
    session_token = session.get("session_token")
    user = session.get("user")

    if not session_token or not user:
        return redirect(url_for("login"))

    session_data = session_manager.get_session(session_token)
    if not session_data:
        session.clear()
        return redirect(url_for("login"))

    if session_data["status"] != "active":
        return redirect(url_for("waiting"))

    current_mode = session.get("file_mode")

    if request.method == "POST":
        if current_mode != "write":
            file_manager.start_writing(user)
            session["file_mode"] = "write"

        new_content = request.form.get("content", "")
        file_manager.write_file(new_content)

        file_manager.stop_writing(user)
        session["file_mode"] = None

        return redirect(url_for("dashboard"))

    # Release read mode before requesting exclusive write access.
    if current_mode == "read":
        file_manager.stop_reading(user)
        session["file_mode"] = None
        current_mode = None

    if current_mode != "write":
        file_manager.start_writing(user)
        session["file_mode"] = "write"

    content = file_manager.read_file()
    return render_template("edit_document.html", content=content)

@app.route("/leave-file-mode", methods=["POST"])
def leave_file_mode():
    """
    Releases any active read/write mode held by this browser session.

    This is called when leaving the read/edit page so locks are not left behind.
    """
    session_token = session.get("session_token")
    user = session.get("user")

    if not session_token or not user:
        return ("", 204)

    mode = session.get("file_mode")

    if mode == "read":
        file_manager.stop_reading(user)
    elif mode == "write":
        file_manager.stop_writing(user)

    session["file_mode"] = None
    session["requested_file_mode"] = None
    return ("", 204)

@app.route("/logout")
def logout():
    """
    Logs the user out of both the browser session and the active system state.

    Any held file mode is released first, then the user slot is released
    back to the semaphore so the next queued user can be promoted.
    """
    session_token = session.get("session_token")
    user = session.get("user")

    if user:
        mode = session.get("file_mode")
        if mode == "read":
            file_manager.stop_reading(user)
        elif mode == "write":
            file_manager.stop_writing(user)

    if session_token:
        semaphore_manager.logout_session(session_token)

    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
     # threaded=True allows Flask's development server to handle concurrent requests.
    app.run(debug=True, threaded=True)