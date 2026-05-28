import socket
import threading

from shared.logger import setup_logger
from server.client_handler import ClientHandler
from server.connection_manager import ConnectionManager
from server.router import RequestRouter


class DistResServer:
    """
    Main TCP server for DistRes.

    Responsibilities:
    - Create the server socket
    - Bind to an IP address and port
    - Listen for incoming clients
    - Accept connections
    - Start one thread per client
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        self.host = host
        self.port = port
        self.logger = setup_logger("DistResServer")

        self.server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        self.connection_manager = ConnectionManager()
        self.router = RequestRouter()
        self.running = False

    def start(self) -> None:
        """
        Starts the TCP server.

        bind()
        Assigns the server to a host and port.

        listen()
        Puts the socket into listening mode.

        accept()
        Waits for client connections.
        """

        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()

        self.running = True

        self.logger.info(
            f"DistRes server listening on {self.host}:{self.port}"
        )

        try:
            while self.running:
                client_socket, client_address = self.server_socket.accept()

                handler = ClientHandler(
                    client_socket=client_socket,
                    client_address=client_address,
                    connection_manager=self.connection_manager,
                    router=self.router
                )

                client_thread = threading.Thread(
                    target=handler.run,
                    daemon=True
                )

                client_thread.start()

                self.logger.info(
                    f"Started thread for client from {client_address}"
                )

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")

        finally:
            self.stop()

    def stop(self) -> None:
        """
        Stops the server.
        """

        self.running = False

        try:
            self.server_socket.close()
        except Exception:
            pass

        self.logger.info("DistRes server stopped")