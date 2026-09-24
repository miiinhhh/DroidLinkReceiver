import socket
import struct
import subprocess
import threading
import os


class AudioReceiver:

    def __init__(self, ip, port=8081):
        self.ip = ip
        self.port = port

        self.sock = None
        self.running = False
        self.thread = None
        self.ffplay = None
        self.first_timestamp = None
        self.format_checked = False

    def connect(self):
        print(f"[Audio] Connecting to {self.ip}:{self.port}...")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)

        try:
            self.sock.connect((self.ip, self.port))

            print(
                f"[Audio] TCP connection successful "
                f"to {self.ip}:{self.port}"
            )

            self.sock.settimeout(None)

            ffplay_environment = os.environ.copy()
            ffplay_environment["SDL_AUDIODRIVER"] = "directsound"

            self.ffplay = subprocess.Popen(
                [
                    "ffplay",
                    "-hide_banner",
                    "-loglevel", "verbose",
                    "-nodisp",
                    "-vn",
                    "-volume", "100",
                    "-probesize", "32",
                    "-analyzeduration", "0",
                    "-f", "aac",
                    "-i", "pipe:0"
                ],
                stdin=subprocess.PIPE,
                env=ffplay_environment
            )

            self.running = True

            self.thread = threading.Thread(
                target=self._receive_loop,
                daemon=True
            )

            self.thread.start()

            print("[Audio] Receiver thread started")

        except Exception as e:
            print(f"[Audio] Connect error: {e}")
            self.close()
            raise

    def _receive_loop(self):
        try:
            while self.running:

                # 4 bytes length + 8 bytes timestamp
                header = self._recv_exact(12)

                if not header:
                    print("[Audio] Connection closed by Android")
                    break

                packet_length = struct.unpack(
                    ">I",
                    header[0:4]
                )[0]

                timestamp_ms = struct.unpack(
                    ">q",
                    header[4:12]
                )[0]

                if packet_length <= 0 or packet_length > 1024 * 1024:
                    print(
                        f"[Audio] Invalid packet size: "
                        f"{packet_length}"
                    )
                    break

                data = self._recv_exact(packet_length)

                if not data:
                    print("[Audio] Audio packet incomplete")
                    break

                if self.first_timestamp is None:
                    self.first_timestamp = timestamp_ms

                    print(
                        f"[Audio] Stream start timestamp: "
                        f"{timestamp_ms} ms"
                    )

                relative_timestamp = (
                    timestamp_ms - self.first_timestamp
                )

                print(
                    f"[Audio] timestamp={timestamp_ms} ms "
                    f"| relative={relative_timestamp} ms "
                    f"| AAC={len(data)} bytes"
                )

                if not self.format_checked:
                    self.format_checked = True
                    if len(data) < 2 or data[0] != 0xFF or (data[1] & 0xF6) != 0xF0:
                        print(
                            "[Audio] Payload khong co ADTS header. "
                            "Android co the dang gui AAC raw; ffplay se khong "
                            "giai ma duoc neu thieu AudioSpecificConfig. "
                            f"first_bytes={data[:8].hex()}"
                        )
                    else:
                        print("[Audio] AAC ADTS header detected")

                self.handle_audio_packet(
                    timestamp_ms,
                    data
                )

        except ConnectionError:
            print("[Audio] Connection closed")

        except OSError as e:
            if self.running:
                print(f"[Audio] Socket error: {e}")

        except Exception as e:
            print(f"[Audio] Receiver error: {e}")

        finally:
            self.running = False

    def handle_audio_packet(self, timestamp_ms, data):

        if not self.ffplay:
            return

        if not self.ffplay.stdin:
            return

        if self.ffplay.poll() is not None:
            print(
                f"[Audio] ffplay da thoat truoc khi nhan packet nay "
                f"(exit code {self.ffplay.returncode}). "
                "AAC dau vao bi tu choi hoac audio device khong mo duoc."
            )
            self.running = False
            return

        try:
            self.ffplay.stdin.write(data)
            self.ffplay.stdin.flush()

        except (BrokenPipeError, OSError):
            print("[Audio] ffplay closed")
            self.running = False

    def _recv_exact(self, size):

        data = bytearray()

        while len(data) < size:

            chunk = self.sock.recv(
                size - len(data)
            )

            if not chunk:
                return None

            data.extend(chunk)

        return bytes(data)

    def close(self):

        self.running = False

        if self.sock:

            try:
                self.sock.shutdown(
                    socket.SHUT_RDWR
                )
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

        self.thread = None
        self.first_timestamp = None
        self.format_checked = False

        print("[Audio] Closed")