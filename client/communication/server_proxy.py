from shared.protocol import create_message


class ServerProxy:
    """
    Client-side proxy for DistRes server messages.

    The CLI calls these methods instead of building JSON dictionaries itself.
    """

    def __init__(self, client):
        self.client = client

    def send_hello(self, client_name):
        return self.client.send_request(
            create_message(
                "hello",
                {
                    "client_name": client_name
                }
            )
        )

    def send_ping(self):
        return self.client.send_request(
            create_message("ping", {})
        )

    def request_server_status(self):
        return self.client.send_request(
            create_message("server_status", {})
        )

    def login(self, user_id, username):
        return self.client.send_request(
            create_message(
                "login_request",
                {
                    "user_id": user_id,
                    "username": username
                }
            )
        )

    def logout(self):
        return self.client.send_request(
            create_message("logout_request", {})
        )

    def read_file(self):
        return self.client.send_request(
            create_message("read_file_request", {})
        )

    def request_write_mode(self):
        return self.client.send_request(
            create_message("write_file_request", {})
        )

    def commit_write(self, content):
        return self.client.send_request(
            create_message(
                "write_file_commit",
                {
                    "content": content
                }
            )
        )

    def leave_file_mode(self):
        return self.client.send_request(
            create_message("leave_file_mode_request", {})
        )

    def request_system_state(self):
        return self.client.send_request(
            create_message("system_state_request", {})
        )

    def subscribe_updates(self):
        return self.client.send_request(
            create_message("subscribe_updates", {})
        )

    def unsubscribe_updates(self):
        return self.client.send_request(
            create_message("unsubscribe_updates", {})
        )
