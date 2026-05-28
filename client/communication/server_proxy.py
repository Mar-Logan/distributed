class ServerProxy:

    def __init__(self, client):

        self.client = client

    def send_hello(self, client_name):

        request = {
            "type": "hello",
            "payload": {
                "client_name": client_name
            }
        }

        self.client.send_request(request)

    def send_ping(self):

        request = {
            "type": "ping",
            "payload": {}
        }

        self.client.send_request(request)

    def request_server_status(self):

        request = {
            "type": "server_status",
            "payload": {}
        }

        self.client.send_request(request)