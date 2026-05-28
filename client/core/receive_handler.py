import threading


class ReceiveHandler:
    """
    Background receiver for asynchronous server messages.

    Direct responses and pub-sub notifications arrive on the same TCP stream,
    so the CLI collects them here and displays them between menu actions.
    """

    def __init__(self, client):
        self.client = client
        self.thread = None
        self.latest_messages = []
        self.lock = threading.Lock()

    def start(self):
        self.thread = threading.Thread(
            target=self.receive_loop,
            daemon=True
        )
        self.thread.start()

    def receive_loop(self):
        while self.client.running:
            messages = self.client.receive_messages()

            if not messages:
                continue

            with self.lock:
                self.latest_messages.extend(messages)

    def get_pending_messages(self):
        with self.lock:
            messages = self.latest_messages.copy()
            self.latest_messages.clear()
            return messages
