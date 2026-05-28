"""
Thread-safe publish-subscribe subscription tracking.
"""

import threading


class PubSubManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers = set()

    def subscribe(self, client_id):
        """Adds a client to the update subscriber set."""

        with self._lock:
            self._subscribers.add(client_id)

    def unsubscribe(self, client_id):
        """Removes a client from the update subscriber set."""

        with self._lock:
            self._subscribers.discard(client_id)

    def get_subscribers(self):
        """Returns a snapshot of subscribed client IDs."""

        with self._lock:
            return set(self._subscribers)
