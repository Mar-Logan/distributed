"""
Server-side registry of TCP clients used by Flask browser sessions.

The Flask session cookie stores only a generated web_client_id. The actual
socket object stays in this process-level registry.
"""

import threading
import os

from web.web_distres_client import WebDistResClient


class WebClientRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients = {}

    def get_or_create(self, web_client_id):
        """Returns the TCP client for a browser session."""

        with self._lock:
            client = self._clients.get(web_client_id)

            if client is None or not client.running:
                client = WebDistResClient(
                    host=os.getenv("DISTRES_HOST", "127.0.0.1"),
                    port=int(os.getenv("DISTRES_PORT", "9000")),
                    name=f"FlaskWebClient-{web_client_id}"
                )
                client.connect()
                self._clients[web_client_id] = client

            return client

    def get(self, web_client_id):
        """Returns a registered TCP client without creating one."""

        with self._lock:
            return self._clients.get(web_client_id)

    def remove(self, web_client_id):
        """Disconnects and removes a registered TCP client."""

        with self._lock:
            client = self._clients.pop(web_client_id, None)

        if client is not None:
            client.disconnect()


web_client_registry = WebClientRegistry()
