class ReceiveHandler:

    def __init__(self, client):
        self.client = client
        self.thread = None
        self.latest_messages = []

    def start(self):
        import threading

        self.thread = threading.Thread(
            target=self.receive_loop,
            daemon=True
        )
        self.thread.start()

    def receive_loop(self):
        while self.client.running:
            response = self.client.receive_response()

            if response is None:
                continue

            self.latest_messages.append(response)

    def get_pending_messages(self):
        messages = self.latest_messages.copy()
        self.latest_messages.clear()
        return messages