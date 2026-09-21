import socket


class DroidLinkConnection:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect((self.ip, self.port))
        self.sock.settimeout(None)

    def start_stream(self):
        if self.sock is None:
            raise RuntimeError("Not connected")

        self.sock.sendall(b"START_STREAM\n")

    def close(self):
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            try:
                self.sock.close()
            except OSError:
                pass

            self.sock = None
