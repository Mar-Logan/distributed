import socket
from shared.logger import setup_logger
from shared.protocol import receive_message, send_message, create_message
from server.router import RequestRouter
from server.connection_manager import ConnectionManager


class ClientHandler:
    """
    Handles one connected client.

    Each client gets its own ClientHandler instance.
    Each ClientHandler runs inside its own thread.
    """

    def __init__(
        self,
        client_socket: socket.socket,
        client_address: tuple[str, int],
        connection_manager: ConnectionManager,
        router: RequestRouter
    ):
        self.client_socket = client_socket
        self.client_address = client_address
        self.connection_manager = connection_manager
        self.router = router
        self.logger = setup_logger("ClientHandler")
        self.client_id = self.connection_manager.register_client(client_address)
        self.running = True

    def run(self) -> None:
        """
        Main client handling loop.

        This loop:
        1. Waits for data from the client
        2. Converts TCP data into JSON messages
        3. Routes each message
        4. Sends a response
        5. Handles disconnects cleanly
        """

        self.logger.info(
            f"Client {self.client_id} connected from {self.client_address}"
        )

        send_message(
            self.client_socket,
            create_message(
                "connection_ack",
                {
                    "client_id": self.client_id,
                    "message": "Connected to DistRes server"
                }
            )
        )

        buffer = ""

        try:
            while self.running:
                data = self.client_socket.recv(4096)

                if not data:
                    self.logger.info(
                        f"Client {self.client_id} disconnected"
                    )
                    break

                messages, buffer = receive_message(buffer, data)

                for message in messages:
                    self.logger.debug(
                        f"Received from client {self.client_id}: {message}"
                    )

                    response = self.router.route(self.client_id, message)

                    send_message(self.client_socket, response)

                    self.logger.debug(
                        f"Sent to client {self.client_id}: {response}"
                    )

        except ConnectionResetError:
            self.logger.warning(
                f"Client {self.client_id} connection reset unexpectedly"
            )

        except Exception as error:
            self.logger.error(
                f"Error handling client {self.client_id}: {error}"
            )

            try:
                send_message(
                    self.client_socket,
                    create_message(
                        "error",
                        {
                            "error": "Internal server error"
                        }
                    )
                )
            except Exception:
                pass

        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """
        Cleans up after a client disconnects.

        This is important because distributed systems must not keep stale
        clients in the server state.
        """

        self.running = False
        self.connection_manager.remove_client(self.client_id)

        try:
            self.client_socket.close()
        except Exception:
            pass

        self.logger.info(
            f"Cleaned up client {self.client_id}"
        )