"""
Server-side admission control using a counting semaphore.

Only a limited number of logged-in users are active at once. Extra users are
kept in a waiting state and promoted when active sessions leave.
"""

import threading


class SemaphoreManager:
    def __init__(self, max_active_users, session_manager):
        self.max_active_users = max_active_users
        self.semaphore = threading.Semaphore(max_active_users)
        self.lock = threading.Lock()
        self.session_manager = session_manager

    def request_login(self, session_token, user, client_id):

        with self.lock:
            existing = self.session_manager.find_session_by_user(user)
            if existing is not None:
                return "duplicate"

            if self.semaphore.acquire(blocking=False):
                self.session_manager.create_session(
                    session_token,
                    user,
                    "active",
                    client_id
                )
                return "active"

            self.session_manager.create_session(
                session_token,
                user,
                "waiting",
                client_id
            )
            return "waiting"

    def logout_session(self, session_token):
        """
        Removes a session and promotes the next waiting user if possible.

        Returns the promoted session token, or None if nobody was promoted.
        """

        with self.lock:
            session_data = self.session_manager.remove_session(session_token)
            if not session_data:
                return None

            if session_data["status"] == "active":
                self.semaphore.release()

            return self.promote_next_waiting_user()

    def promote_next_waiting_user(self):
        """Promotes the next waiting session if a slot is free."""

        if not self.semaphore.acquire(blocking=False):
            return None

        waiting_tokens = self.session_manager.get_waiting_session_tokens()

        if not waiting_tokens:
            self.semaphore.release()
            return None

        next_token = waiting_tokens[0]
        updated = self.session_manager.update_status(next_token, "active")

        if not updated:
            self.semaphore.release()
            return None

        return next_token
