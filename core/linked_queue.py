"""
Thread-safe linked-list queue used for file access request tracking.

Stores pending read/write requests in FIFO order using linked nodes.
"""

import threading


class QueueNode:
    """Single linked-list node used by the queue."""
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
        """Adds a new value to the end of the queue."""
        with self._lock:
            new_node = QueueNode(value)

            if self.tail is None:
                self.head = new_node
                self.tail = new_node
            else:
                self.tail.next = new_node
                self.tail = new_node

            self.size += 1

    def dequeue(self):
        """Removes and returns the value at the front of the queue."""
        with self._lock:
            if self.head is None:
                return None

            value = self.head.value
            self.head = self.head.next

            if self.head is None:
                self.tail = None

            self.size -= 1
            return value

    def remove_first_match(self, predicate):
        """
        Removes the first queue item that matches the predicate.

        Useful for removing a granted read/write request from the pending queue.
        """
        with self._lock:
            prev = None
            current = self.head

            while current is not None:
                if predicate(current.value):
                    if prev is None:
                        self.head = current.next
                    else:
                        prev.next = current.next

                    if current == self.tail:
                        self.tail = prev

                    self.size -= 1
                    return current.value

                prev = current
                current = current.next

            return None

    def to_list(self):
        """Returns a snapshot of the queue contents."""
        with self._lock:
            values = []
            current = self.head

            while current is not None:
                values.append(current.value)
                current = current.next

            return values

    def is_empty(self):
        """Checks whether the queue is empty."""
        with self._lock:
            return self.head is None