import time

from client.core.connection_state import ConnectionState


class RetryManager:

    def __init__(self, max_attempts=3, retry_delay=2):

        self.max_attempts = max_attempts
        self.retry_delay = retry_delay

    def attempt_connection(self, client):

        for attempt in range(1, self.max_attempts + 1):

            print(f"Connection attempt {attempt}")

            if client.connect():
                return True

            time.sleep(self.retry_delay)

        return False

    def attempt_reconnection(self, client):
        """Attempts to reconnect a disconnected client."""

        client.state = ConnectionState.RECONNECTING
        return self.attempt_connection(client)
