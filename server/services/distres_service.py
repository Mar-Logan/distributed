"""
Application/logic layer for DistRes.

The router deals with message types, while this service owns the distributed
resource rules:

- authentication against server-side SQLite
- active/waiting session control
- shared file read/write coordination
- disconnect cleanup
- pub-sub subscription state
"""

import uuid
from pathlib import Path

from shared.logger import setup_logger
from server.core.file_manager import FileManager
from server.core.pubsub_manager import PubSubManager
from server.core.semaphore_manager import SemaphoreManager
from server.core.session_manager import SessionManager
from server.data.auth_repository import validate_credentials


class DistResService:
    def __init__(self, max_active_users=4, file_path=None):
        project_root = Path(__file__).resolve().parents[2]
        shared_file = file_path or project_root / "ProductSpecification.txt"

        self.logger = setup_logger("DistResService")
        self.session_manager = SessionManager()
        self.semaphore_manager = SemaphoreManager(
            max_active_users=max_active_users,
            session_manager=self.session_manager
        )
        self.file_manager = FileManager(shared_file)
        self.pubsub_manager = PubSubManager()

    def login(self, client_id, payload):
        """Authenticates a client and places it into active or waiting state."""

        existing = self.session_manager.get_session_for_client(client_id)
        if existing is not None:
            return {
                "success": False,
                "status": existing["status"],
                "reason": "This TCP client is already logged in.",
                "session_token": existing["session_token"],
                "state": self.get_system_state(client_id)
            }

        user_id = payload.get("user_id") or payload.get("id")
        username = payload.get("username")
        password = payload.get("password")

        stored_user = validate_credentials(
            user_id=user_id,
            username=username,
            password=password
        )

        if stored_user is None:
            return {
                "success": False,
                "status": "denied",
                "reason": "Invalid credentials.",
                "state": self.get_system_state(client_id)
            }

        display_user = self._format_user(stored_user)
        session_token = str(uuid.uuid4())
        login_status = self.semaphore_manager.request_login(
            session_token=session_token,
            user=display_user,
            client_id=client_id
        )

        if login_status == "duplicate":
            return {
                "success": False,
                "status": "duplicate",
                "reason": "This user is already logged in or waiting.",
                "state": self.get_system_state(client_id)
            }

        self.logger.info(
            f"Client {client_id} logged in as {display_user} ({login_status})"
        )

        return {
            "success": True,
            "status": login_status,
            "session_token": session_token,
            "user": display_user,
            "state": self.get_system_state(client_id)
        }

    def logout(self, client_id):
        """Logs out a client and releases any server-owned resources."""

        session = self.session_manager.get_session_for_client(client_id)
        if session is None:
            self.pubsub_manager.unsubscribe(client_id)
            return {
                "response": {
                    "success": False,
                    "reason": "Client is not logged in.",
                    "state": self.get_system_state(client_id)
                },
                "promoted_client_id": None,
                "promoted_payload": None
            }

        user = session["user"]
        session_token = session["session_token"]

        self.file_manager.release_all_for_user(user)
        self.pubsub_manager.unsubscribe(client_id)

        promoted_token = self.semaphore_manager.logout_session(session_token)
        promoted_payload = self._build_promotion_payload(promoted_token)

        self.logger.info(f"Client {client_id} logged out ({user})")

        return {
            "response": {
                "success": True,
                "message": "Logged out successfully.",
                "user": user,
                "state": self.get_system_state(client_id)
            },
            "promoted_client_id": (
                promoted_payload.get("client_id") if promoted_payload else None
            ),
            "promoted_payload": promoted_payload
        }

    def cleanup_client(self, client_id):
        """
        Releases all server state owned by a disconnected client.

        This is used when the socket closes without an explicit logout.
        """

        session = self.session_manager.get_session_for_client(client_id)
        self.pubsub_manager.unsubscribe(client_id)

        if session is None:
            return {
                "promoted_client_id": None,
                "promoted_payload": None
            }

        user = session["user"]
        self.file_manager.release_all_for_user(user)

        promoted_token = self.semaphore_manager.logout_session(
            session["session_token"]
        )
        promoted_payload = self._build_promotion_payload(promoted_token)

        self.logger.info(
            f"Cleaned up disconnected client {client_id} ({user})"
        )

        return {
            "promoted_client_id": (
                promoted_payload.get("client_id") if promoted_payload else None
            ),
            "promoted_payload": promoted_payload
        }

    def grant_queued_file_requests(self):
        """
        Grants queued file requests that can now run.

        Returns messages ready for the router to send asynchronously to the
        clients that were waiting.
        """

        grants = self.file_manager.grant_next_queued_requests()
        messages = []

        for grant in grants:
            session = self.session_manager.find_session_by_user(grant["user"])

            if session is None or session["status"] != "active":
                self.file_manager.release_all_for_user(grant["user"])
                continue

            client_id = session["client_id"]
            mode = grant["mode"]

            messages.append({
                "client_id": client_id,
                "type": "file_access_granted",
                "payload": {
                    "success": True,
                    "mode": mode,
                    "user": grant["user"],
                    "content": grant["content"],
                    "already_holding": False,
                    "queued_grant": True,
                    "message": (
                        "Queued file access has now been granted."
                    ),
                    "state": self.get_system_state(client_id)
                }
            })

        return messages

    def read_file(self, client_id):
        """Handles a read_file_request message."""

        allowed = self._require_active_session(client_id)
        if not allowed["allowed"]:
            return {
                "type": "access_denied",
                "payload": allowed
            }

        user = allowed["session"]["user"]
        result = self.file_manager.request_read(user)

        if result["status"] == "granted":
            return {
                "type": "read_file_response",
                "payload": {
                    "success": True,
                    "mode": "read",
                    "user": user,
                    "content": result["content"],
                    "already_holding": result["already_holding"],
                    "state": self.get_system_state(client_id)
                }
            }

        if result["status"] == "queued":
            return {
                "type": "queued",
                "payload": {
                    "success": False,
                    "request": "read_file_request",
                    "mode": "read",
                    "queue_position": result["queue_position"],
                    "reason": "The file is currently locked for writing or a writer is queued.",
                    "state": self.get_system_state(client_id)
                }
            }

        return {
            "type": "access_denied",
            "payload": {
                "success": False,
                "reason": result["reason"],
                "state": self.get_system_state(client_id)
            }
        }

    def request_write(self, client_id):
        """Handles a write_file_request message."""

        allowed = self._require_active_session(client_id)
        if not allowed["allowed"]:
            return {
                "type": "access_denied",
                "payload": allowed
            }

        user = allowed["session"]["user"]
        result = self.file_manager.request_write(user)

        if result["status"] == "granted":
            return {
                "type": "write_file_response",
                "payload": {
                    "success": True,
                    "mode": "write",
                    "user": user,
                    "content": result["content"],
                    "already_holding": result["already_holding"],
                    "state": self.get_system_state(client_id)
                }
            }

        return {
            "type": "queued",
            "payload": {
                "success": False,
                "request": "write_file_request",
                "mode": "write",
                "queue_position": result["queue_position"],
                "reason": "The file is currently being read or written.",
                "state": self.get_system_state(client_id)
            }
        }

    def commit_write(self, client_id, payload):
        """Handles a write_file_commit message."""

        allowed = self._require_active_session(client_id)
        if not allowed["allowed"]:
            return {
                "type": "access_denied",
                "payload": allowed
            }

        user = allowed["session"]["user"]
        content = payload.get("content", "")
        result = self.file_manager.commit_write(user, content)

        if result["status"] == "written":
            self.logger.info(f"{user} updated ProductSpecification.txt")
            return {
                "type": "write_file_commit_response",
                "payload": {
                    "success": True,
                    "message": "File updated successfully.",
                    "user": user,
                    "content_length": result["content_length"],
                    "state": self.get_system_state(client_id)
                }
            }

        return {
            "type": "access_denied",
            "payload": {
                "success": False,
                "reason": result["reason"],
                "state": self.get_system_state(client_id)
            }
        }

    def leave_file_mode(self, client_id):
        """Releases read/write/queued file state for the current client."""

        session = self.session_manager.get_session_for_client(client_id)

        if session is None:
            return {
                "success": False,
                "reason": "Client is not logged in.",
                "state": self.get_system_state(client_id)
            }

        removed = self.file_manager.release_all_for_user(session["user"])

        return {
            "success": True,
            "message": "Released file mode and queued file requests.",
            "removed_queued_requests": removed,
            "state": self.get_system_state(client_id)
        }

    def subscribe(self, client_id):
        """Subscribes a logged-in client to resource update notifications."""

        session = self.session_manager.get_session_for_client(client_id)
        if session is None:
            return {
                "success": False,
                "reason": "Login required before subscribing.",
                "state": self.get_system_state(client_id)
            }

        self.pubsub_manager.subscribe(client_id)
        return {
            "success": True,
            "message": "Subscribed to resource updates.",
            "state": self.get_system_state(client_id)
        }

    def unsubscribe(self, client_id):
        """Unsubscribes a client from resource update notifications."""

        self.pubsub_manager.unsubscribe(client_id)
        return {
            "success": True,
            "message": "Unsubscribed from resource updates.",
            "state": self.get_system_state(client_id)
        }

    def get_subscriber_ids(self):
        """Returns active pub-sub subscribers."""

        return self.pubsub_manager.get_subscribers()

    def get_system_state(self, client_id=None):
        """Builds a complete state snapshot for clients and logs."""

        session = (
            self.session_manager.get_session_for_client(client_id)
            if client_id is not None else None
        )

        return {
            "current_user": session["user"] if session else None,
            "current_status": session["status"] if session else "anonymous",
            "active_users": self.session_manager.get_active_users(),
            "waiting_users": self.session_manager.get_waiting_users(),
            "file_status": self.file_manager.get_file_status(),
            "active_readers": self.file_manager.get_active_readers(),
            "active_writer": self.file_manager.get_active_writer(),
            "file_queue": self.file_manager.get_queue_snapshot(),
            "subscribers": sorted(self.pubsub_manager.get_subscribers())
        }

    def _require_active_session(self, client_id):
        session = self.session_manager.get_session_for_client(client_id)

        if session is None:
            return {
                "allowed": False,
                "success": False,
                "reason": "Login required.",
                "state": self.get_system_state(client_id)
            }

        if session["status"] != "active":
            return {
                "allowed": False,
                "success": False,
                "reason": "Your session is waiting for an active slot.",
                "state": self.get_system_state(client_id)
            }

        return {
            "allowed": True,
            "session": session
        }

    def _build_promotion_payload(self, promoted_token):
        if promoted_token is None:
            return None

        promoted_session = self.session_manager.get_session(promoted_token)
        if promoted_session is None:
            return None

        return {
            "success": True,
            "status": "active",
            "promoted": True,
            "session_token": promoted_token,
            "client_id": promoted_session["client_id"],
            "user": promoted_session["user"],
            "message": "A system slot is now available. You are active.",
            "state": self.get_system_state(promoted_session["client_id"])
        }

    def _format_user(self, stored_user):
        user_id = stored_user.get("id")
        username = stored_user.get("username", "unknown")

        if user_id:
            return f"{user_id} - {username}"

        return username
