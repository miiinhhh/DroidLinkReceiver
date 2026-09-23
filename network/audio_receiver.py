import socket
import struct
import subprocess
import threading


class AudioReceiver:
    def __init__(self, ip, port=8081):
        self.ip = ip
        self.port = port
        self.sock = None
        self.running = False
        self.thread = None
        self.ffplay = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect((self.ip, self.port))
        self.sock.settimeout(None)

        # AAC ADTS stream -> ffplay -> speaker
        self.ffplay = subprocess.Popen(
            [
                "ffplay",
                "-hide_banner",
                "-loglevel", "warning",
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-f", "aac",
                "-i", "pipe:0"
            ],
            stdin=subprocess.PIPE
        )

        self.running = True

        self.thread = threading.Thread(
            target=self._receive_loop,
            daemon=True
        )
        self.thread.start()

        print(f"[Audio] Connected to {self.ip}:{self.port}")

    def _receive_loop(self):
        try:
            while self.running:

                header = self._recv_exact(4)

                if not header:
                    break

                packet_length = struct.unpack(">I", header)[0]

                if packet_length <= 0 or packet_length > 1024 * 1024:
                    print(
                        f"[Audio] Invalid packet size: "
                        f"{packet_length}"
                    )
                    break

                data = self._recv_exact(packet_length)

                if not data:
                    break

                print(f"[Audio] AAC packet: {len(data)} bytes")

                if self.ffplay and self.ffplay.stdin:
                    try:
                        self.ffplay.stdin.write(data)
                        self.ffplay.stdin.flush()
                    except (BrokenPipeError, OSError):
                        print("[Audio] ffplay closed")
                        break

        except ConnectionError:
            print("[Audio] Connection closed")

        except Exception as e:
            print(f"[Audio] Receiver error: {e}")

        finally:
            self.running = False

    def _recv_exact(self, size):
        data = bytearray()

        while len(data) < size:
            chunk = self.sock.recv(size - len(data))

            if not chunk:
                return None

            data.extend(chunk)

        return bytes(data)

    def close(self):
        self.running = False

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

        if self.ffplay:
            try:
                if self.ffplay.stdin:
                    self.ffplay.stdin.close()
            except OSError:
                pass

            try:
                self.ffplay.terminate()
                self.ffplay.wait(timeout=2)
            except Exception:
                try:
                    self.ffplay.kill()
                except Exception:
                    pass

            self.ffplay = None

        print("[Audio] Closed")