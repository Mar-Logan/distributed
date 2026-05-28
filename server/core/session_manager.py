"""
Thread-safe server-side session manager.

DistRes keeps all authoritative session state on the server. A client only
receives a session token as an identifier; it never stores the
authoritative active/waiting state directly.
"""

import threading


class SessionManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.sessions = {}

    def create_session(self, session_token, user, status, client_id):
        """Stores a new session record."""

        with self._lock:
            self.sessions[session_token] = {
                "user": user,
                "status": status,
                "client_id": client_id
            }

    def get_session(self, session_token):
        """Returns a copy of a session record, if it exists."""

        with self._lock:
            data = self.sessions.get(session_token)
            return dict(data) if data else None

    def get_session_token_for_client(self, client_id):
        """Finds the current session token for a connected client."""

        with self._lock:
            for token, data in self.sessions.items():
                if data["client_id"] == client_id:
                    return token
            return None

    def get_session_for_client(self, client_id):
        """Returns the current session record for a connected client."""

        with self._lock:
            for token, data in self.sessions.items():
                if data["client_id"] == client_id:
                    session = dict(data)
                    session["session_token"] = token
                    return session
            return None

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
                        "status": data["status"],
                        "client_id": data["client_id"]
                    }
            return None

    def is_active_session(self, session_token):
        """Checks whether a session is active."""

        with self._lock:
            return (
                session_token in self.sessions and
                self.sessions[session_token]["status"] == "active"
            )

    def get_active_users(self):
        """Returns users currently admitted to the system."""

        with self._lock:
            return [
                data["user"]
                for data in self.sessions.values()
                if data["status"] == "active"
            ]

    def get_waiting_users(self):
        """Returns users currently waiting for admission."""

        with self._lock:
            return [
                data["user"]
                for data in self.sessions.values()
                if data["status"] == "waiting"
            ]

    def get_waiting_session_tokens(self):
        """Returns waiting session tokens in insertion order."""

        with self._lock:
            return [
                token
                for token, data in self.sessions.items()
                if data["status"] == "waiting"
            ]
