import socket
import time

from shared.protocol import send_message, receive_message, create_message


def run_test_client(client_name: str):
    """
    Simple test client for Step 1.

    This connects to the DistRes server, sends test messages,
    prints the responses, and disconnects.
    """

    host = "127.0.0.1"
    port = 9000

    client_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    client_socket.connect((host, port))

    buffer = ""

    data = client_socket.recv(4096)
    messages, buffer = receive_message(buffer, data)

    for message in messages:
        print("SERVER:", message)

    send_message(
        client_socket,
        create_message(
            "hello",
            {
                "client_name": client_name
            }
        )
    )

    data = client_socket.recv(4096)
    messages, buffer = receive_message(buffer, data)

    for message in messages:
        print("SERVER:", message)

    send_message(
        client_socket,
        create_message("ping")
    )

    data = client_socket.recv(4096)
    messages, buffer = receive_message(buffer, data)

    for message in messages:
        print("SERVER:", message)

    send_message(
        client_socket,
        create_message("server_status")
    )

    data = client_socket.recv(4096)
    messages, buffer = receive_message(buffer, data)

    for message in messages:
        print("SERVER:", message)

    time.sleep(1)

    client_socket.close()


if __name__ == "__main__":
    run_test_client("Test Client A")