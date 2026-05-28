"""
Non-blocking readers-writer lock for server-owned resources.

In the TCP version, request handlers should return a JSON response instead of getting stuck inside
a lock, so this lock exposes try-acquire operations.
"""

import threading


class RWLock:
    def __init__(self):
        self._lock = threading.Lock()
        self._readers = 0
        self._writer = None

    def try_acquire_read(self):
        """Attempts to acquire read access without blocking."""

        with self._lock:
            if self._writer is not None:
                return False

            self._readers += 1
            return True

    def release_read(self):
        """Releases one reader."""

        with self._lock:
            if self._readers > 0:
                self._readers -= 1

    def try_acquire_write(self, user):
        """Attempts to acquire exclusive write access without blocking."""

        with self._lock:
            if self._writer is not None or self._readers > 0:
                return False

            self._writer = user
            return True

    def release_write(self, user=None):
        """Releases the active writer."""

        with self._lock:
            if user is None or self._writer == user:
                self._writer = None

    def get_reader_count(self):
        """Returns the number of active readers."""

        with self._lock:
            return self._readers

    def get_writer(self):
        """Returns the active writer, if any."""

        with self._lock:
            return self._writer
