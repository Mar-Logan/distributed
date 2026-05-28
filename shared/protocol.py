import json
import socket
from typing import Any, Dict, Optional


Message = Dict[str, Any]


MESSAGE_TYPES = {
    "connection_ack",
    "hello",
    "hello_ack",
    "ping",
    "pong",
    "server_status",
    "server_status_response",
    "login_request",
    "login_response",
    "logout_request",
    "logout_response",
    "read_file_request",
    "read_file_response",
    "write_file_request",
    "write_file_response",
    "write_file_commit",
    "write_file_commit_response",
    "leave_file_mode_request",
    "leave_file_mode_response",
    "system_state_request",
    "system_state_response",
    "subscribe_updates",
    "unsubscribe_updates",
    "resource_updated",
    "file_access_granted",
    "access_denied",
    "queued",
    "error",
}


def create_message(message_type: str, payload: Optional[dict] = None) -> Message:
    """
    Creates a standard DistRes message.

    Every message structure:

    {
        "type": "message_type",
        "payload": {...}
    }
    """

    return {
        "type": message_type,
        "payload": payload or {}
    }


def encode_message(message: Message) -> bytes:
    """
    Converts a Python dictionary into newline-delimited JSON bytes.

    TCP sockets send bytes, not Python dictionaries.
    message must be: Converted to JSON text, Given a newline delimiter, Encoded into bytes
    """

    json_text = json.dumps(message)
    return (json_text + "\n").encode("utf-8")


def decode_message(raw_message: str) -> Message:
    """
    Converts JSON text back into a Python dictionary.

    If invalid JSON is received, json.loads will raise an exception.
    That exception is handled by the client handler.
    """

    return json.loads(raw_message)


def send_message(sock: socket.socket, message: Message) -> None:
    """
    Sends one complete JSON message through a socket.
    """

    data = encode_message(message)
    sock.sendall(data)


def receive_message(buffer: str, data: bytes) -> tuple[list[Message], str]:
    """
    Processes incoming TCP data and extracts complete JSON messages.
    """

    buffer += data.decode("utf-8")

    messages = []

    while "\n" in buffer:
        raw_message, buffer = buffer.split("\n", 1)

        if raw_message.strip():
            messages.append(decode_message(raw_message))

    return messages, buffer
