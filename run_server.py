from server.server import DistResServer


if __name__ == "__main__":
    server = DistResServer(
        host="127.0.0.1",
        port=9000
    )

    server.start()