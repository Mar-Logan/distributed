from shared.protocol import create_message
from server.services.distres_service import DistResService


class RequestRouter:
    """
    Routes incoming JSON messages to server-side DistRes logic.
    """

    def __init__(self, connection_manager, service=None):
        self.connection_manager = connection_manager
        self.service = service or DistResService()

    def route(self, client_id: int, message: dict) -> dict:
        """Routes one client message and returns one direct response."""

        message_type = message.get("type")
        payload = message.get("payload", {})

        if message_type == "ping":
            return self.handle_ping(client_id)

        if message_type == "hello":
            return self.handle_hello(client_id, payload)

        if message_type == "server_status":
            return self.handle_server_status(client_id)

        if message_type == "login_request":
            return self.handle_login(client_id, payload)

        if message_type == "logout_request":
            return self.handle_logout(client_id)

        if message_type == "read_file_request":
            return self.handle_read_file(client_id)

        if message_type == "write_file_request":
            return self.handle_write_file_request(client_id)

        if message_type == "write_file_commit":
            return self.handle_write_file_commit(client_id, payload)

        if message_type == "leave_file_mode_request":
            return self.handle_leave_file_mode(client_id)

        if message_type == "system_state_request":
            return self.handle_system_state(client_id)

        if message_type == "subscribe_updates":
            return self.handle_subscribe(client_id)

        if message_type == "unsubscribe_updates":
            return self.handle_unsubscribe(client_id)

        return self.handle_unknown_message(client_id, message_type)

    def cleanup_client(self, client_id: int) -> None:
        """Releases server-owned resources when a socket disconnects."""

        result = self.service.cleanup_client(client_id)
        self._notify_promoted_client(result)
        self._notify_file_grants()

    def handle_ping(self, client_id: int) -> dict:
        return create_message(
            "pong",
            {
                "client_id": client_id,
                "message": "Server received ping successfully"
            }
        )

    def handle_hello(self, client_id: int, payload: dict) -> dict:
        client_name = payload.get("client_name", "Unknown Client")

        return create_message(
            "hello_ack",
            {
                "client_id": client_id,
                "message": f"Hello {client_name}, connected to DistRes server"
            }
        )

    def handle_server_status(self, client_id: int) -> dict:
        connected_clients = self.connection_manager.get_connected_clients()

        return create_message(
            "server_status_response",
            {
                "client_id": client_id,
                "server": "DistRes TCP Server",
                "status": "running",
                "connected_clients": len(connected_clients),
                "clients": {
                    str(key): f"{value[0]}:{value[1]}"
                    for key, value in connected_clients.items()
                }
            }
        )

    def handle_login(self, client_id: int, payload: dict) -> dict:
        login_payload = self.service.login(client_id, payload)

        return create_message(
            "login_response",
            login_payload
        )

    def handle_logout(self, client_id: int) -> dict:
        result = self.service.logout(client_id)
        self._notify_promoted_client(result)
        self._notify_file_grants()

        return create_message(
            "logout_response",
            result["response"]
        )

    def handle_read_file(self, client_id: int) -> dict:
        result = self.service.read_file(client_id)
        return create_message(result["type"], result["payload"])

    def handle_write_file_request(self, client_id: int) -> dict:
        result = self.service.request_write(client_id)
        return create_message(result["type"], result["payload"])

    def handle_write_file_commit(self, client_id: int, payload: dict) -> dict:
        result = self.service.commit_write(client_id, payload)
        response = create_message(result["type"], result["payload"])

        if result["type"] == "write_file_commit_response":
            self._publish_resource_updated(result["payload"])
            self._notify_file_grants()

        return response

    def handle_leave_file_mode(self, client_id: int) -> dict:
        response = create_message(
            "leave_file_mode_response",
            self.service.leave_file_mode(client_id)
        )
        self._notify_file_grants()
        return response

    def handle_system_state(self, client_id: int) -> dict:
        return create_message(
            "system_state_response",
            {
                "success": True,
                "state": self.service.get_system_state(client_id)
            }
        )

    def handle_subscribe(self, client_id: int) -> dict:
        return create_message(
            "subscribe_updates",
            self.service.subscribe(client_id)
        )

    def handle_unsubscribe(self, client_id: int) -> dict:
        return create_message(
            "unsubscribe_updates",
            self.service.unsubscribe(client_id)
        )

    def handle_unknown_message(self, client_id: int, message_type: str) -> dict:
        return create_message(
            "error",
            {
                "client_id": client_id,
                "error": f"Unknown message type: {message_type}"
            }
        )

    def _publish_resource_updated(self, commit_payload):
        notification = create_message(
            "resource_updated",
            {
                "message": "ProductSpecification.txt was updated.",
                "updated_by": commit_payload.get("user"),
                "content_length": commit_payload.get("content_length"),
                "state": self.service.get_system_state()
            }
        )

        self.connection_manager.broadcast(
            notification,
            recipients=self.service.get_subscriber_ids()
        )

    def _notify_promoted_client(self, result):
        promoted_client_id = result.get("promoted_client_id")
        promoted_payload = result.get("promoted_payload")

        if promoted_client_id is None or promoted_payload is None:
            return

        payload = dict(promoted_payload)
        payload.pop("client_id", None)

        self.connection_manager.send_to_client(
            promoted_client_id,
            create_message("login_response", payload)
        )

    def _notify_file_grants(self):
        for grant in self.service.grant_queued_file_requests():
            self.connection_manager.send_to_client(
                grant["client_id"],
                create_message(grant["type"], grant["payload"])
            )
