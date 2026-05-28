import time


class ClientCLI:
    """
    Simple menu-driven terminal client for DistRes.
    """

    def __init__(self, proxy, receive_handler, client=None, retry_manager=None):
        self.proxy = proxy
        self.receive_handler = receive_handler
        self.client = client
        self.retry_manager = retry_manager
        self.client_id = None
        self.logged_in = False
        self.login_status = "anonymous"
        self.current_user = None
        self.file_mode = None

    def show_pending_messages(self):
        messages = self.receive_handler.get_pending_messages()

        for message in messages:
            self.handle_server_message(message)

    def handle_server_message(self, message):
        message_type = message.get("type")
        payload = message.get("payload", {})

        print()
        print("=" * 60)
        print(f"SERVER MESSAGE: {message_type}")
        print("=" * 60)

        if message_type == "connection_ack":
            self.client_id = payload.get("client_id")
            print(payload.get("message"))
            print(f"Client ID: {self.client_id}")

        elif message_type == "login_response":
            self._handle_login_response(payload)

        elif message_type == "logout_response":
            self._handle_logout_response(payload)

        elif message_type == "read_file_response":
            self.file_mode = "read"
            print("Read mode granted.")
            self._print_file_content(payload.get("content", ""))
            self._print_state(payload.get("state"))

        elif message_type == "write_file_response":
            self.file_mode = "write"
            print("Write mode granted.")
            self._print_file_content(payload.get("content", ""))
            print("Use menu option 6 to commit replacement content.")
            self._print_state(payload.get("state"))

        elif message_type == "write_file_commit_response":
            if payload.get("success"):
                self.file_mode = None
            print(payload.get("message", payload))
            self._print_state(payload.get("state"))

        elif message_type == "leave_file_mode_response":
            if payload.get("success"):
                self.file_mode = None
            print(payload.get("message", payload.get("reason")))
            self._print_state(payload.get("state"))

        elif message_type == "system_state_response":
            self._print_state(payload.get("state"))

        elif message_type == "queued":
            print(payload.get("reason", "Request queued."))
            print(f"Request: {payload.get('request')}")
            print(f"Mode: {payload.get('mode')}")
            print(f"Queue position: {payload.get('queue_position')}")
            self._print_state(payload.get("state"))

        elif message_type == "access_denied":
            print(payload.get("reason", "Access denied."))
            self._print_state(payload.get("state"))

        elif message_type == "resource_updated":
            print(payload.get("message", "Resource updated."))
            print(f"Updated by: {payload.get('updated_by')}")
            print(f"Content length: {payload.get('content_length')}")
            self._print_state(payload.get("state"))

        elif message_type == "file_access_granted":
            self.file_mode = payload.get("mode")
            print(payload.get("message", "Queued file access has been granted."))
            print(f"Mode: {self.file_mode}")
            self._print_file_content(payload.get("content", ""))
            if self.file_mode == "write":
                print("Use menu option 6 to commit replacement content.")
            self._print_state(payload.get("state"))

        elif message_type in ("subscribe_updates", "unsubscribe_updates"):
            print(payload.get("message", payload.get("reason")))
            self._print_state(payload.get("state"))

        elif message_type in ("pong", "hello_ack", "server_status_response"):
            self._print_payload(payload)

        elif message_type == "error":
            print(payload.get("error", payload))

        else:
            self._print_payload(payload)

        print("=" * 60)

    def start(self):
        try:
            while True:
                self.show_pending_messages()
                self.print_menu()

                choice = input("Select option: ").strip()

                if choice == "1":
                    if self.ensure_connected():
                        self.login()

                elif choice == "2":
                    if self.ensure_connected():
                        self.proxy.subscribe_updates()
                        self._brief_wait()

                elif choice == "3":
                    if self.ensure_connected():
                        self.proxy.request_system_state()
                        self._brief_wait()

                elif choice == "4":
                    if self.ensure_connected():
                        self.proxy.read_file()
                        self._brief_wait()

                elif choice == "5":
                    if self.ensure_connected():
                        self.proxy.request_write_mode()
                        self._brief_wait()

                elif choice == "6":
                    if self.ensure_connected():
                        self.commit_write()

                elif choice == "7":
                    if self.ensure_connected():
                        self.proxy.leave_file_mode()
                        self._brief_wait()

                elif choice == "8":
                    if self.ensure_connected():
                        self.proxy.logout()
                        self._brief_wait()

                elif choice == "9":
                    if self.ensure_connected():
                        self.proxy.send_ping()
                        self._brief_wait()

                elif choice == "10":
                    if self.ensure_connected():
                        self.proxy.request_server_status()
                        self._brief_wait()

                elif choice == "0":
                    self.clean_exit()
                    break

                else:
                    print("Invalid option")

        except KeyboardInterrupt:
            print()
            self.clean_exit()

    def print_menu(self):
        print()
        print("=== DistRes Client Menu ===")
        print(f"Client ID : {self.client_id}")
        print(f"User      : {self.current_user or '-'}")
        print(f"Status    : {self.login_status}")
        print(f"File mode : {self.file_mode or '-'}")
        print()
        print("1. Login")
        print("2. Subscribe to update notifications")
        print("3. View system state")
        print("4. Read shared file")
        print("5. Request write mode")
        print("6. Commit write")
        print("7. Leave file mode")
        print("8. Logout")
        print("9. Ping server")
        print("10. Server status")
        print("0. Exit")

    def login(self):
        user_id = input("User ID (example 1001): ").strip()
        username = input("Username (example alice): ").strip()

        self.proxy.login(user_id, username)
        self._brief_wait()

    def commit_write(self):
        if self.file_mode != "write":
            print("You need write mode before committing.")
            return

        print()
        print("Enter replacement file content.")
        print("Type .save on its own line to commit.")
        print("Type .cancel on its own line to cancel.")

        lines = []

        while True:
            line = input()

            if line == ".save":
                self.proxy.commit_write("\n".join(lines))
                self._brief_wait()
                return

            if line == ".cancel":
                print("Commit cancelled. Write mode is still held.")
                return

            lines.append(line)

    def clean_exit(self):
        if self.client is not None and not self.client.running:
            return

        if self.file_mode is not None:
            self.proxy.leave_file_mode()
            self._brief_wait()

        if self.logged_in:
            self.proxy.logout()
            self._brief_wait()

        self.show_pending_messages()

    def ensure_connected(self):
        if self.client is None or self.client.running:
            return True

        if self.retry_manager is None:
            print("Client is disconnected.")
            return False

        print("Client is disconnected. Attempting reconnection...")

        if not self.retry_manager.attempt_reconnection(self.client):
            print("Reconnection failed.")
            return False

        self.logged_in = False
        self.login_status = "anonymous"
        self.current_user = None
        self.file_mode = None
        self.receive_handler.start()
        self._brief_wait()
        print("Reconnected. Please log in again.")
        return True

    def _handle_login_response(self, payload):
        if payload.get("success"):
            self.logged_in = True
            self.login_status = payload.get("status", "unknown")
            self.current_user = payload.get("user")

            if payload.get("promoted"):
                print(payload.get("message"))
            else:
                print(f"Login successful. Status: {self.login_status}")

            print(f"User: {self.current_user}")
        else:
            print(payload.get("reason", "Login failed."))

        self._print_state(payload.get("state"))

    def _handle_logout_response(self, payload):
        if payload.get("success"):
            print(payload.get("message"))
        else:
            print(payload.get("reason", "Logout failed."))

        self.logged_in = False
        self.login_status = "anonymous"
        self.current_user = None
        self.file_mode = None
        self._print_state(payload.get("state"))

    def _print_state(self, state):
        if not state:
            return

        print()
        print("System state:")
        print(f"  Current user   : {state.get('current_user')}")
        print(f"  Current status : {state.get('current_status')}")
        print(f"  Active users   : {state.get('active_users')}")
        print(f"  Waiting users  : {state.get('waiting_users')}")
        print(f"  File status    : {state.get('file_status')}")
        print(f"  Active readers : {state.get('active_readers')}")
        print(f"  Active writer  : {state.get('active_writer')}")
        print(f"  File queue     : {state.get('file_queue')}")
        print(f"  Subscribers    : {state.get('subscribers')}")

    def _print_file_content(self, content):
        print()
        print("-" * 60)
        print(content)
        print("-" * 60)

    def _print_payload(self, payload):
        for key, value in payload.items():
            print(f"{key}: {value}")

    def _brief_wait(self):
        time.sleep(0.25)
        self.show_pending_messages()
