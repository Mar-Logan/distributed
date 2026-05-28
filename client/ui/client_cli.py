class ClientCLI:

    def __init__(self, proxy, receive_handler):
        self.proxy = proxy
        self.receive_handler = receive_handler

    def show_pending_messages(self):
        messages = self.receive_handler.get_pending_messages()

        for message in messages:
            message_type = message.get("type")
            payload = message.get("payload", {})

            print()
            print("=" * 45)
            print("SERVER MESSAGE RECEIVED")
            print("=" * 45)
            print(f"Type    : {message_type}")
            print(f"Payload : {payload}")
            print("=" * 45)

    def start(self):
        while True:
            self.show_pending_messages()

            print()
            print("=== DistRes Client Menu ===")
            print("1. Send Hello")
            print("2. Ping Server")
            print("3. Request Server Status")
            print("4. Exit")

            choice = input("Select option: ")

            if choice == "1":
                name = input("Enter client name: ")
                self.proxy.send_hello(name)

            elif choice == "2":
                self.proxy.send_ping()

            elif choice == "3":
                self.proxy.request_server_status()

            elif choice == "4":
                break

            else:
                print("Invalid option")