import socket
import threading
from dataclasses import dataclass
from typing import Dict, Tuple

from shared.protocol import send_message


@dataclass
class ClientConnection:
    socket: socket.socket
    address: Tuple[str, int]
    send_lock: threading.Lock


class ConnectionManager:
    """
    Stores information about currently connected clients.
    """

    def __init__(self):
        self._clients: Dict[int, ClientConnection] = {}
        self._lock = threading.Lock()
        self._next_client_id = 1

    def register_client(
        self,
        client_socket: socket.socket,
        address: Tuple[str, int]
    ) -> int:
        """
        Registers a new client and returns a unique client ID.
        """

        with self._lock:
            client_id = self._next_client_id
            self._next_client_id += 1
            self._clients[client_id] = ClientConnection(
                socket=client_socket,
                address=address,
                send_lock=threading.Lock()
            )
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
        """

        with self._lock:
            return {
                client_id: connection.address
                for client_id, connection in self._clients.items()
            }

    def get_client_count(self) -> int:
        """Returns the number of connected TCP clients."""

        with self._lock:
            return len(self._clients)

    def send_to_client(self, client_id: int, message: dict) -> bool:
        """
        Sends a message to one connected client.

        Each socket has its own send lock so direct responses and pub-sub
        notifications cannot write over each other on the same TCP stream.
        """

        with self._lock:
            connection = self._clients.get(client_id)

        if connection is None:
            return False

        try:
            with connection.send_lock:
                send_message(connection.socket, message)
            return True
        except Exception:
            return False

    def broadcast(
        self,
        message: dict,
        recipients=None,
        exclude_client_id: int | None = None
    ) -> None:
        """Sends a message to several connected clients."""

        if recipients is None:
            with self._lock:
                recipients = list(self._clients.keys())

        for client_id in list(recipients):
            if client_id == exclude_client_id:
                continue
            self.send_to_client(client_id, message)
