"""
Controls concurrent access to ProductSpecification.txt.

Uses a readers-writer lock for safe file access, a thread-safe linked queue
for pending requests, and lock-protected state tracking for dashboard display.
"""

import threading
import time
from core.rwlock import RWLock
from core.linked_queue import ThreadSafeLinkedQueue


class FileManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.rwlock = RWLock()
        self.request_queue = ThreadSafeLinkedQueue()

        self._state_lock = threading.Lock()
        self.active_readers = []
        self.active_writer = None

    def start_reading(self, user):
        """
        Attempts to place a user into active read mode without blocking.

        The request is first added to the pending queue, then removed if read
        access is granted successfully.
        """
        self.request_queue.enqueue({
            "user": user,
            "mode": "read",
            "timestamp": time.time()
        })

        self.rwlock.acquire_read()

        self.request_queue.remove_first_match(
            lambda item: item["user"] == user and item["mode"] == "read"
        )

        with self._state_lock:
            if user not in self.active_readers:
                self.active_readers.append(user)

    def stop_reading(self, user):
        """Releases read mode only if this user is currently an active reader."""
        should_release = False

        with self._state_lock:
            if user in self.active_readers:
                self.active_readers.remove(user)
                should_release = True

        if should_release:
            self.rwlock.release_read()

    def start_writing(self, user):
        """
        Attempts to place a user into active write mode without blocking.

        Only one writer may hold the file at a time.
        """
        self.request_queue.enqueue({
            "user": user,
            "mode": "write",
            "timestamp": time.time()
        })

        self.rwlock.acquire_write(user)

        self.request_queue.remove_first_match(
            lambda item: item["user"] == user and item["mode"] == "write"
        )

        with self._state_lock:
            self.active_writer = user


    def stop_writing(self, user):
        """Releases write mode only if this user is the active writer."""
        should_release = False

        with self._state_lock:
            if self.active_writer == user:
                self.active_writer = None
                should_release = True

        if should_release:
            self.rwlock.release_write()

    def read_file(self):
        """Reads and returns the current file contents."""
        with open(self.file_path, "r", encoding="utf-8") as file:
            return file.read()

    def write_file(self, content):
        """
        Writes updated content to the file.

        Line endings are normalised to prevent blank-line expansion on Windows.
        """
        normalised = content.replace("\r\n", "\n").replace("\r", "\n")

        with open(self.file_path, "w", encoding="utf-8", newline="\n") as file:
            file.write(normalised)

    def get_file_status(self):
        """Returns Idle, Reading, or Updating based on current file state."""
        with self._state_lock:
            if self.active_writer is not None:
                return "Updating"
            if self.active_readers:
                return "Reading"
            return "Idle"

    def get_active_readers(self):
        """Returns the users currently reading the file."""
        with self._state_lock:
            return list(self.active_readers)

    def get_active_writer(self):
        """Returns the current writer, if any."""
        with self._state_lock:
            return self.active_writer

    def get_queue_snapshot(self):
        """Returns a snapshot of pending read/write requests."""
        return self.request_queue.to_list()