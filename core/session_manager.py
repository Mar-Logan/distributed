"""
Tracks active and waiting user sessions for the whole application.

Each browser login gets a unique session token. The manager stores
the associated user identity and whether that session is active or waiting.
"""

import threading


class SessionManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.sessions = {}  # session_token -> {"user": ..., "status": ...}

    def create_session(self, session_token, user, status):
        """Stores a new session record."""
        with self._lock:
            self.sessions[session_token] = {
                "user": user,
                "status": status
            }

    def get_session(self, session_token):
        """Returns a copy of the stored session record, if it exists."""
        with self._lock:
            data = self.sessions.get(session_token)
            return dict(data) if data else None

    def remove_session(self, session_token):
        """Removes and returns a session record."""
        with self._lock:
            return self.sessions.pop(session_token, None)

    def update_status(self, session_token, status):
        """Updates a session's active/waiting state."""
        with self._lock:
            if session_token in self.sessions:
                self.sessions[session_token]["status"] = status
                return True
            return False

    def find_session_by_user(self, user):
        """Finds an existing session for a given user identity."""
        with self._lock:
            for token, data in self.sessions.items():
                if data["user"] == user:
                    return {
                        "session_token": token,
                        "user": data["user"],
                        "status": data["status"]
                    }
            return None

    def is_active_session(self, session_token):
        """Checks whether a session is currently active."""
        with self._lock:
            return (
                session_token in self.sessions and
                self.sessions[session_token]["status"] == "active"
            )

    def is_waiting_session(self, session_token):
        """Checks whether a session is currently waiting."""
        with self._lock:
            return (
                session_token in self.sessions and
                self.sessions[session_token]["status"] == "waiting"
            )

    def get_active_users(self):
        """Returns the list of users currently admitted to the system."""
        with self._lock:
            return [
                data["user"]
                for data in self.sessions.values()
                if data["status"] == "active"
            ]

    def get_waiting_users(self):
        """Returns the list of users currently in the login queue."""
        with self._lock:
            return [
                data["user"]
                for data in self.sessions.values()
                if data["status"] == "waiting"
            ]

    def get_waiting_session_tokens(self):
        """Returns queued session tokens in waiting order."""
        with self._lock:
            return [
                token
                for token, data in self.sessions.items()
                if data["status"] == "waiting"
            ]