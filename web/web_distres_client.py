"""
TCP client adapter used by the Flask web frontend.

Browsers speak HTTP, while the DistRes server speaks newline-delimited JSON
over TCP. This adapter lets Flask routes send TCP messages to the DistRes
server without giving the browser direct access to server-owned resources.
"""

import socket
import threading
import time

from shared.logger import setup_logger
from shared.protocol import create_message, receive_message, send_message


class WebDistResClient:
    def __init__(self, host="127.0.0.1", port=9000, name="FlaskWebClient"):
        self.host = host
        self.port = port
        self.name = name
        self.socket = None
        self.running = False
        self.buffer = ""
        self.messages = []
        self.message_condition = threading.Condition()
        self.send_lock = threading.Lock()
        self.request_lock = threading.Lock()
        self.receiver_thread = None
        self.logger = setup_logger("WebDistResClient")

    def connect(self):
        """Connects to the DistRes TCP server and waits for connection_ack."""

        if self.running and self.socket is not None:
            return True

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(5)
        self.socket.connect((self.host, self.port))
        self.socket.settimeout(1)

        self.running = True
        self.receiver_thread = threading.Thread(
            target=self._receive_loop,
            daemon=True
        )
        self.receiver_thread.start()

        ack = self.wait_for({"connection_ack"}, timeout=3)
        if ack is None:
            self.disconnect()
            raise ConnectionError("DistRes server did not acknowledge connection.")

        self.logger.info(f"{self.name} connected to DistRes TCP server")
        return True

    def request(self, message_type, payload=None, expected_types=None, timeout=5):
        """
        Sends a request and waits for one of the expected response types.

        The request lock keeps overlapping HTTP requests from the same browser
        session from consuming each other's TCP responses.
        """

        self.ensure_connected()

        if expected_types is None:
            expected_types = set()
        elif isinstance(expected_types, str):
            expected_types = {expected_types}
        else:
            expected_types = set(expected_types)

        with self.request_lock:
            message = create_message(message_type, payload or {})

            try:
                with self.send_lock:
                    send_message(self.socket, message)
            except OSError as error:
                self.running = False
                raise ConnectionError(f"Failed to send TCP request: {error}") from error

            if not expected_types:
                return None

            return self.wait_for(expected_types, timeout=timeout)

    def wait_for(self, expected_types, timeout=5):
        """Waits until a queued message matches one of the expected types."""

        deadline = time.time() + timeout

        with self.message_condition:
            while time.time() < deadline:
                for index, message in enumerate(self.messages):
                    if message.get("type") in expected_types:
                        return self.messages.pop(index)

                remaining = deadline - time.time()
                if remaining <= 0:
                    break

                self.message_condition.wait(timeout=remaining)

        return None

    def pop_messages(self, message_types=None):
        """Removes and returns queued asynchronous messages."""

        if message_types is not None:
            message_types = set(message_types)

        with self.message_condition:
            selected = []
            retained = []

            for message in self.messages:
                if message_types is None or message.get("type") in message_types:
                    selected.append(message)
                else:
                    retained.append(message)

            self.messages = retained
            return selected

    def ensure_connected(self):
        """Reconnects if needed."""

        if self.running and self.socket is not None:
            return

        self.connect()

    def disconnect(self):
        """Closes the TCP connection."""

        self.running = False

        try:
            if self.socket is not None:
                self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            if self.socket is not None:
                self.socket.close()
        except OSError:
            pass

        self.socket = None

        with self.message_condition:
            self.message_condition.notify_all()

    def _receive_loop(self):
        while self.running:
            try:
                data = self.socket.recv(4096)

                if not data:
                    self.running = False
                    break

                messages, self.buffer = receive_message(self.buffer, data)

                if messages:
                    with self.message_condition:
                        self.messages.extend(messages)
                        self.message_condition.notify_all()

            except socket.timeout:
                continue

            except OSError:
                if self.running:
                    self.logger.warning("TCP receive loop stopped unexpectedly")
                self.running = False
                break

            except Exception as error:
                self.logger.error(f"TCP receive error: {error}")
                self.running = False
                break

        with self.message_condition:
            self.message_condition.notify_all()
