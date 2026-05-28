from client.core.distres_client import DistResClient
from client.core.receive_handler import ReceiveHandler
from client.core.retry_manager import RetryManager

from client.communication.server_proxy import ServerProxy

from client.ui.client_cli import ClientCLI


def main():

    client = DistResClient()

    retry_manager = RetryManager()  

    connected = retry_manager.attempt_connection(client)

    if not connected:

        print("Unable to connect to server")

        return

    receive_handler = ReceiveHandler(client)

    receive_handler.start()

    proxy = ServerProxy(client)

    cli = ClientCLI(proxy, receive_handler)

    try:

        cli.start()

    finally:

        client.disconnect()


if __name__ == "__main__":

    main()