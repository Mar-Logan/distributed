"""
Thread-safe linked-list queue for file access request tracking.
"""

import threading


class QueueNode:
    def __init__(self, value):
        self.value = value
        self.next = None


class ThreadSafeLinkedQueue:
    def __init__(self):
        self._lock = threading.Lock()
        self.head = None
        self.tail = None
        self.size = 0

    def enqueue(self, value):
        """Adds a value to the end of the queue."""

        with self._lock:
            node = QueueNode(value)

            if self.tail is None:
                self.head = node
                self.tail = node
            else:
                self.tail.next = node
                self.tail = node

            self.size += 1

    def enqueue_if_missing(self, value, predicate):
        """Adds a value only when no existing item matches the predicate."""

        with self._lock:
            current = self.head
            while current is not None:
                if predicate(current.value):
                    return False
                current = current.next

            node = QueueNode(value)

            if self.tail is None:
                self.head = node
                self.tail = node
            else:
                self.tail.next = node
                self.tail = node

            self.size += 1
            return True

    def remove_first_match(self, predicate):
        """Removes and returns the first item matching the predicate."""

        with self._lock:
            previous = None
            current = self.head

            while current is not None:
                if predicate(current.value):
                    if previous is None:
                        self.head = current.next
                    else:
                        previous.next = current.next

                    if current == self.tail:
                        self.tail = previous

                    self.size -= 1
                    return current.value

                previous = current
                current = current.next

            return None

    def peek(self):
        """Returns a copy of the front item without removing it."""

        with self._lock:
            if self.head is None:
                return None

            return dict(self.head.value)

    def remove_all_matches(self, predicate):
        """Removes all matching items and returns the removed values."""

        removed = []

        with self._lock:
            previous = None
            current = self.head

            while current is not None:
                if predicate(current.value):
                    removed.append(current.value)

                    if previous is None:
                        self.head = current.next
                    else:
                        previous.next = current.next

                    if current == self.tail:
                        self.tail = previous

                    self.size -= 1
                    current = current.next
                    continue

                previous = current
                current = current.next

        return removed

    def to_list(self):
        """Returns a snapshot list of queue items."""

        with self._lock:
            values = []
            current = self.head

            while current is not None:
                values.append(dict(current.value))
                current = current.next

            return values
