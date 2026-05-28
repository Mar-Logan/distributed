import json
import socket
from typing import Any, Dict, Optional


Message = Dict[str, Any]


def create_message(message_type: str, payload: Optional[dict] = None) -> Message:
    """
    Creates a standard DistRes message.

    Every message in the system follows the same structure:

    {
        "type": "message_type",
        "payload": {...}
    }

    This makes routing easier because the server can inspect the 'type'
    field and decide what action to perform.
    """

    return {
        "type": message_type,
        "payload": payload or {}
    }


def encode_message(message: Message) -> bytes:
    """
    Converts a Python dictionary into newline-delimited JSON bytes.

    TCP sockets send bytes, not Python dictionaries.
    message must be:
    1. Converted to JSON text
    2. Given a newline delimiter
    3. Encoded into bytes
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

    sendall() is used instead of send() because send() may only transmit
    part of the data. sendall() keeps sending until the full message has
    been passed to the operating system.
    """

    data = encode_message(message)
    sock.sendall(data)


def receive_message(buffer: str, data: bytes) -> tuple[list[Message], str]:
    """
    Processes incoming TCP data and extracts complete JSON messages.

    Because TCP is a stream, it may receive:
    - half a message
    - exactly one message
    - multiple messages together

    This function keeps an unfinished buffer and only returns complete
    newline-delimited JSON messages.
    """

    buffer += data.decode("utf-8")

    messages = []

    while "\n" in buffer:
        raw_message, buffer = buffer.split("\n", 1)

        if raw_message.strip():
            messages.append(decode_message(raw_message))

    return messages, buffer