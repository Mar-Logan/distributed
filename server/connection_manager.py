import threading
from typing import Dict, Tuple


class ConnectionManager:
    """
    Stores information about currently connected clients.
    """

    def __init__(self):
        self._clients: Dict[int, Tuple[str, int]] = {}
        self._lock = threading.Lock()
        self._next_client_id = 1

    def register_client(self, address: Tuple[str, int]) -> int:
        """
        Registers a new client and returns a unique client ID.

        A lock is used because multiple clients may connect at the same time.
        Without the lock, two threads could accidentally receive the same ID.
        """

        with self._lock:
            client_id = self._next_client_id
            self._next_client_id += 1
            self._clients[client_id] = address
            return client_id

    def remove_client(self, client_id: int) -> None:
        """
        Removes a disconnected client from the active client list.
        """

        with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]

    def get_connected_clients(self) -> Dict[int, Tuple[str, int]]:
        """
        Returns a copy of connected clients.

        A copy is returned so external code cannot accidentally modify
        the internal dictionary.
        """

        with self._lock:
            return dict(self._clients)