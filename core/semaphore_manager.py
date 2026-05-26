"""
Controls admission to the system using a counting semaphore.

Limits the number of active users, queues excess users,
and promotes the next waiting session when a slot is released.
"""

import threading


class SemaphoreManager:
    def __init__(self, max_active_users, session_manager):
        self.max_active_users = max_active_users
        self.semaphore = threading.Semaphore(max_active_users)
        self.lock = threading.Lock()
        self.session_manager = session_manager

    def request_login(self, session_token, user):
        """
        Attempts to admit a user into the active pool.

        Returns:
            active    -> user admitted immediately
            waiting   -> user queued
            duplicate -> user already has a live session
        """
        with self.lock:
            existing = self.session_manager.find_session_by_user(user)
            if existing is not None:
                return "duplicate"

            if self.semaphore.acquire(blocking=False):
                self.session_manager.create_session(session_token, user, "active")
                return "active"

            self.session_manager.create_session(session_token, user, "waiting")
            return "waiting"

    def logout_session(self, session_token):
        """
        Removes a session from the system and releases a user slot if needed.

        If the session was active, the next waiting user is promoted.
        """
        with self.lock:
            session_data = self.session_manager.remove_session(session_token)
            if not session_data:
                return

            if session_data["status"] == "active":
                self.semaphore.release()

            self.promote_next_waiting_user()

    def promote_next_waiting_user(self):
        """Promotes the next queued user if a semaphore slot is free."""
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