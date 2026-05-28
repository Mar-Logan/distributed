from shared.protocol import create_message


class RequestRouter:
    """
    Routes incoming client messages to the correct handler function.

    This keeps the client handler simple.

    Instead of putting all logic inside the socket thread, the socket thread
    receives the message and passes it to the router.
    """

    def route(self, client_id: int, message: dict) -> dict:
        """
        Main routing method.

        Reads the message type and calls the correct handler.
        """

        message_type = message.get("type")
        payload = message.get("payload", {})

        if message_type == "ping":
            return self.handle_ping(client_id, payload)

        if message_type == "hello":
            return self.handle_hello(client_id, payload)

        if message_type == "server_status":
            return self.handle_server_status(client_id, payload)

        return self.handle_unknown_message(client_id, message_type)

    def handle_ping(self, client_id: int, payload: dict) -> dict:
        """
        Basic connectivity test.

        The client sends:
        {
            "type": "ping",
            "payload": {}
        }

        The server replies:
        {
            "type": "pong",
            "payload": {"client_id": 1}
        }
        """

        return create_message(
            "pong",
            {
                "client_id": client_id,
                "message": "Server received ping successfully"
            }
        )

    def handle_hello(self, client_id: int, payload: dict) -> dict:
        """
        Basic introduction message.

        This prepares the structure for future authentication.
        For now, the client can simply send its name.
        """

        client_name = payload.get("client_name", "Unknown Client")

        return create_message(
            "hello_ack",
            {
                "client_id": client_id,
                "message": f"Hello {client_name}, connected to DistRes server"
            }
        )

    def handle_server_status(self, client_id: int, payload: dict) -> dict:
        """
        Placeholder status request.

        Later, this can return:
        - active users
        - waiting users
        - file lock state
        - connected clients
        - pub-sub subscribers
        """

        return create_message(
            "server_status_response",
            {
                "client_id": client_id,
                "server": "DistRes TCP Server",
                "status": "running"
            }
        )

    def handle_unknown_message(self, client_id: int, message_type: str) -> dict:
        """
        Handles messages with unsupported request types.
        """

        return create_message(
            "error",
            {
                "client_id": client_id,
                "error": f"Unknown message type: {message_type}"
            }
        )