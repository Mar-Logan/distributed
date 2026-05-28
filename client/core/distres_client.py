import socket
import threading

from shared.protocol import send_message, receive_message

from client.core.connection_state import ConnectionState
from client.utils.client_logger import setup_logger


class DistResClient:

    def __init__(self, host="127.0.0.1", port=9000):

        self.host = host
        self.port = port

        self.socket = None
        self.receive_buffer = ""

        self.state = ConnectionState.DISCONNECTED
        self.logger = setup_logger()

        self.running = False
        self.lock = threading.Lock()

    def connect(self):

        try:
            self.logger.info(f"Connecting to server {self.host}:{self.port}")

            self.state = ConnectionState.CONNECTING

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)

            self.socket.connect((self.host, self.port))
            self.socket.settimeout(1)

            self.state = ConnectionState.CONNECTED
            self.running = True

            self.logger.info("Connected to DistRes server")

            return True

        except Exception as error:
            self.logger.error(f"Connection failed: {error}")
            self.state = ConnectionState.DISCONNECTED
            return False

    def send_request(self, request):

        try:
            if self.socket is None or not self.running:
                self.logger.warning("Cannot send request while disconnected")
                return False

            with self.lock:
                send_message(self.socket, request)
                self.logger.debug(f"Sent request: {request}")

            return True

        except Exception as error:
            self.logger.error(f"Send failed: {error}")
            self.disconnect()
            return False

    def receive_messages(self):

        try:
            if self.socket is None or not self.running:
                return []

            data = self.socket.recv(4096)

            if not data:
                self.logger.warning("Server closed the connection")
                self.disconnect()
                return []

            messages, self.receive_buffer = receive_message(
                self.receive_buffer,
                data
            )

            for message in messages:
                self.logger.debug(f"Received response: {message}")

            return messages

        except socket.timeout:
            return []

        except Exception as error:
            if self.running:
                self.logger.error(f"Receive failed: {error}")
                self.disconnect()
            return []

    def receive_response(self):
        """Compatibility helper that returns the first available message."""

        messages = self.receive_messages()
        if messages:
            return messages[0]
        return None

    def disconnect(self):

        if not self.running and self.socket is None:
            return

        if self.running:
            self.logger.info("Disconnecting from server")

        self.running = False
        self.state = ConnectionState.DISCONNECTED

        try:
            if self.socket:
                self.socket.shutdown(socket.SHUT_RDWR)

        except Exception:
            pass

        try:
            if self.socket:
                self.socket.close()

        except Exception:
            pass

        self.socket = None

        self.logger.info("Disconnected")
