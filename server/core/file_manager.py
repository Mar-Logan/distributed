"""
Server-owned shared file manager.

This class coordinates read/write access to ProductSpecification.txt. It keeps
the resource state on the server, exposes snapshots for the CLI, and tracks
queued file access requests.
"""

import threading
import time

from server.core.linked_queue import ThreadSafeLinkedQueue
from server.core.rwlock import RWLock


class FileManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.rwlock = RWLock()
        self.request_queue = ThreadSafeLinkedQueue()

        self._state_lock = threading.Lock()
        self.active_readers = []
        self.active_writer = None

    def request_read(self, user):
        """
        Attempts to grant read mode.
        """

        with self._state_lock:
            if user in self.active_readers:
                return {
                    "status": "granted",
                    "content": self.read_file(),
                    "already_holding": True
                }

            if self.active_writer == user:
                return {
                    "status": "access_denied",
                    "reason": "Leave write mode before requesting read mode."
                }

            if self._can_grant_read_now(user):
                if self.rwlock.try_acquire_read():
                    self.active_readers.append(user)
                    self._remove_user_requests(user, "read")
                    return {
                        "status": "granted",
                        "content": self.read_file(),
                        "already_holding": False
                    }

            position = self._queue_request(user, "read")
            return {
                "status": "queued",
                "mode": "read",
                "queue_position": position
            }

    def request_write(self, user):
        """
        Attempts to grant write mode.

        """

        with self._state_lock:
            if self.active_writer == user:
                return {
                    "status": "granted",
                    "content": self.read_file(),
                    "already_holding": True
                }

            if user in self.active_readers:
                self._stop_reading_locked(user)

            if self._can_grant_write_now(user):
                if self.rwlock.try_acquire_write(user):
                    self.active_writer = user
                    self._remove_all_user_requests(user)
                    return {
                        "status": "granted",
                        "content": self.read_file(),
                        "already_holding": False
                    }

            position = self._queue_request(user, "write")
            return {
                "status": "queued",
                "mode": "write",
                "queue_position": position
            }

    def commit_write(self, user, content):
        """
        Writes content to the shared file and releases write mode.
        """

        with self._state_lock:
            if self.active_writer != user:
                return {
                    "status": "access_denied",
                    "reason": "You do not currently hold write mode."
                }

            self.write_file(content)
            self.active_writer = None
            self.rwlock.release_write(user)
            self._remove_user_requests(user, "write")

            return {
                "status": "written",
                "content_length": len(content)
            }

    def grant_next_queued_requests(self):
        """
        Grants the next queued request(s), FIFO order.
        """

        grants = []

        with self._state_lock:
            while True:
                head = self.request_queue.peek()

                if head is None:
                    break

                user = head["user"]
                mode = head["mode"]

                if mode == "write":
                    if not self._can_grant_write_now(user):
                        break

                    if not self.rwlock.try_acquire_write(user):
                        break

                    self.active_writer = user
                    self._remove_user_requests(user, "write")
                    grants.append({
                        "user": user,
                        "mode": "write",
                        "content": self.read_file()
                    })
                    break

                if mode == "read":
                    if not self._can_grant_read_now(user):
                        break

                    if not self.rwlock.try_acquire_read():
                        break

                    if user not in self.active_readers:
                        self.active_readers.append(user)

                    self._remove_user_requests(user, "read")
                    grants.append({
                        "user": user,
                        "mode": "read",
                        "content": self.read_file()
                    })
                    continue

                break

        return grants

    def stop_reading(self, user):
        """Releases read mode for a user."""

        with self._state_lock:
            self._stop_reading_locked(user)
            self._remove_user_requests(user, "read")

    def stop_writing(self, user):
        """Releases write mode for a user."""

        with self._state_lock:
            if self.active_writer == user:
                self.active_writer = None
                self.rwlock.release_write(user)

            self._remove_user_requests(user, "write")

    def release_all_for_user(self, user):
        """Releases active and queued file access for a user."""

        with self._state_lock:
            if user in self.active_readers:
                self._stop_reading_locked(user)

            if self.active_writer == user:
                self.active_writer = None
                self.rwlock.release_write(user)

            removed = self.request_queue.remove_all_matches(
                lambda item: item["user"] == user
            )

            return removed

    def read_file(self):
        """Reads and returns the current shared file contents."""

        with open(self.file_path, "r", encoding="utf-8") as file:
            return file.read()

    def write_file(self, content):
        """Writes normalised content to the shared file."""

        normalised = content.replace("\r\n", "\n").replace("\r", "\n")

        with open(self.file_path, "w", encoding="utf-8", newline="\n") as file:
            file.write(normalised)

    def get_file_status(self):
        """Returns Idle, Reading, or Updating."""

        with self._state_lock:
            if self.active_writer is not None:
                return "Updating"
            if self.active_readers:
                return "Reading"
            return "Idle"

    def get_active_readers(self):
        """Returns a copy of active readers."""

        with self._state_lock:
            return list(self.active_readers)

    def get_active_writer(self):
        """Returns the active writer, if any."""

        with self._state_lock:
            return self.active_writer

    def get_queue_snapshot(self):
        """Returns a copy of queued read/write requests."""

        return self.request_queue.to_list()

    def _stop_reading_locked(self, user):
        if user in self.active_readers:
            self.active_readers.remove(user)
            self.rwlock.release_read()

    def _queue_request(self, user, mode):
        item = {
            "user": user,
            "mode": mode,
            "timestamp": round(time.time(), 3)
        }

        self.request_queue.enqueue_if_missing(
            item,
            lambda existing: (
                existing["user"] == user and existing["mode"] == mode
            )
        )

        snapshot = self.request_queue.to_list()
        for index, queued_item in enumerate(snapshot, start=1):
            if queued_item["user"] == user and queued_item["mode"] == mode:
                return index

        return None

    def _remove_user_requests(self, user, mode):
        self.request_queue.remove_all_matches(
            lambda item: item["user"] == user and item["mode"] == mode
        )

    def _remove_all_user_requests(self, user):
        self.request_queue.remove_all_matches(
            lambda item: item["user"] == user
        )

    def _can_grant_read_now(self, user):
        if self.active_writer is not None:
            return False

        head = self.request_queue.peek()

        if head is None:
            return True

        if head["user"] == user and head["mode"] == "read":
            return True

        return not self._has_queued_writer()

    def _can_grant_write_now(self, user):
        if self.active_writer is not None or self.active_readers:
            return False

        head = self.request_queue.peek()

        if head is None:
            return True

        return head["user"] == user and head["mode"] == "write"

    def _has_queued_writer(self):
        return any(
            item["mode"] == "write"
            for item in self.request_queue.to_list()
        )
