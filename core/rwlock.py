"""
Reader-preference readers-writer lock.

Allows multiple readers concurrently when no writer is active.
Allows only one writer at a time, and writers must wait for readers to finish.
"""

import threading


class RWLock:
    def __init__(self):
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._readers = 0
        self._writer = None
        self._waiting_writers = 0
        """Blocks until read access is allowed, then increments reader count."""

    def acquire_read(self):
        """Attempts to acquire read access without blocking."""
        with self._condition:
            while self._writer is not None or self._waiting_writers > 0:
                self._condition.wait()
            self._readers += 1

    def release_read(self):
        """Releases one reader and wakes waiters if this was the last reader."""
        with self._condition:
            self._readers -= 1
            if self._readers == 0:
                self._condition.notify_all()

    def acquire_write(self, user):
        """Blocks until exclusive write access is available."""
        with self._condition:
            self._waiting_writers += 1
            while self._writer is not None or self._readers > 0:
                self._condition.wait()
            self._waiting_writers -= 1
            self._writer = user

    def release_write(self):
        """Releases the active writer and wakes waiting readers/writers."""
        with self._condition:
            self._writer = None
            self._condition.notify_all()

    def get_reader_count(self):
        """Returns the current number of active readers."""
        with self._lock:
            return self._readers

    def get_writer(self):
        """Returns the current active writer, if any."""
        with self._lock:
            return self._writer