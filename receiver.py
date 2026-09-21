import socket
import struct
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from discovery import discover_device

FFPLAY_COMMAND = [
    "ffplay",
    "-loglevel", "warning",
    "-f", "h264",
    "-fflags", "nobuffer",
    "-flags", "low_delay",
    "-framedrop",
    "-window_title", "DroidLink",
    "pipe:0"
]


def recv_exact(sock, size):
    data = bytearray()

    while len(data) < size:
        chunk = sock.recv(size - len(data))

        if not chunk:
            return None

        data.extend(chunk)

    return bytes(data)


def has_annex_b_start_code(data):
    return (
        data.startswith(b"\x00\x00\x00\x01")
        or data.startswith(b"\x00\x00\x01")
    )


def avcc_to_annex_b(data):
    """
    Chuyển H.264 AVCC:
        [4-byte NAL length][NAL]
        [4-byte NAL length][NAL]
        ...

    thành Annex-B:
        00 00 00 01 [NAL]
        00 00 00 01 [NAL]
        ...
    """

    result = bytearray()
    offset = 0

    while offset + 4 <= len(data):

        nal_size = struct.unpack(
            ">I",
            data[offset:offset + 4]
        )[0]

        offset += 4

        if nal_size <= 0:
            break

        if offset + nal_size > len(data):
            return None

        nal = data[offset:offset + nal_size]

        result.extend(b"\x00\x00\x00\x01")
        result.extend(nal)

        offset += nal_size

    if offset != len(data):
        return None

    return bytes(result)


def normalize_h264(data):
    """
    Chuẩn hóa dữ liệu H.264 về Annex-B.
    """

    if not data:
        return None

    # Đã là Annex-B
    if has_annex_b_start_code(data):
        return data

    # Thử coi là AVCC
    converted = avcc_to_annex_b(data)

    if converted:
        return converted

    # Fallback: coi toàn bộ data là một NAL
    return b"\x00\x00\x00\x01" + data


def send_h264(ffplay, data):
    """
    Chuẩn hóa H.264 rồi gửi vào stdin của ffplay.
    """

    normalized = normalize_h264(data)

    if normalized is None:
        return False

    try:
        ffplay.stdin.write(normalized)
        ffplay.stdin.flush()
        return True

    except (BrokenPipeError, OSError):
        return False


# ============================================================
# DEVICE DISCOVERY
# ============================================================

device = discover_device()

if device is None:
    print(
        "No DroidLink device found.",
        flush=True
    )
    sys.exit(1)


ANDROID_IP = device["ip"]
PORT = device["port"]

print(
    f"Connecting to {device['name']} "
    f"at {ANDROID_IP}:{PORT}...",
    flush=True
)


# ============================================================
# CONNECT TO ANDROID
# ============================================================

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

sock.connect((ANDROID_IP, PORT))

print(
    "Connected to DroidLink!",
    flush=True
)


# ============================================================
# REQUEST SCREEN STREAM
# ============================================================

print(
    "Requesting screen stream...",
    flush=True
)

try:
    sock.sendall(b"START_STREAM\n")
except (BrokenPipeError, OSError) as e:
    print(
        f"Failed to send START_STREAM: {e}",
        flush=True
    )
    sock.close()
    sys.exit(1)

print(
    "START_STREAM sent.",
    flush=True
)

print(
    "Waiting for Android to start screen capture...",
    flush=True
)

# ============================================================
# RECEIVE SPS
# ============================================================

print(
    "Waiting for SPS...",
    flush=True
)

header = recv_exact(sock, 4)

if header is None:
    print(
        "Connection closed while receiving SPS header.",
        flush=True
    )
    sock.close()
    sys.exit(1)

sps_size = struct.unpack(">I", header)[0]

sps = recv_exact(sock, sps_size)

if sps is None:
    print(
        "Connection closed while receiving SPS.",
        flush=True
    )
    sock.close()
    sys.exit(1)

print(
    f"SPS received: {len(sps)} bytes",
    flush=True
)


# ============================================================
# RECEIVE PPS
# ============================================================

header = recv_exact(sock, 4)

if header is None:
    print(
        "Connection closed while receiving PPS header.",
        flush=True
    )
    sock.close()
    sys.exit(1)

pps_size = struct.unpack(">I", header)[0]

pps = recv_exact(sock, pps_size)

if pps is None:
    print(
        "Connection closed while receiving PPS.",
        flush=True
    )
    sock.close()
    sys.exit(1)

print(
    f"PPS received: {len(pps)} bytes",
    flush=True
)


# ============================================================
# START FFPLAY
# ============================================================

print(
    "Starting ffplay...",
    flush=True
)

ffplay = subprocess.Popen(
    FFPLAY_COMMAND,
    stdin=subprocess.PIPE
)

time.sleep(0.2)

print(
    "Sending SPS/PPS to ffplay...",
    flush=True
)


# Send SPS
if not send_h264(ffplay, sps):
    print(
        "Failed to send SPS to ffplay.",
        flush=True
    )
    sys.exit(1)


# Send PPS
if not send_h264(ffplay, pps):
    print(
        "Failed to send PPS to ffplay.",
        flush=True
    )
    sys.exit(1)


print(
    "SPS/PPS sent.",
    flush=True
)

print(
    "Waiting for H.264 frames...",
    flush=True
)


# ============================================================
# RECEIVE VIDEO FRAMES
# ============================================================

packet_count = 0
total_bytes = 0

try:

    while True:

        # ----------------------------------------------------
        # Packet header
        # ----------------------------------------------------

        header = recv_exact(sock, 4)

        if header is None:

            print(
                "Connection closed.",
                flush=True
            )

            break


        # ----------------------------------------------------
        # Packet size
        # ----------------------------------------------------

        packet_size = struct.unpack(
            ">I",
            header
        )[0]


        # ----------------------------------------------------
        # Receive H.264 packet
        # ----------------------------------------------------

        data = recv_exact(
            sock,
            packet_size
        )
        print(
    f"Received frame #{packet_count + 1}, size={packet_size}",
    flush=True
)

        if data is None:

            print(
                "Connection closed while receiving frame.",
                flush=True
            )

            break


        packet_count += 1

        total_bytes += len(data)


        # ----------------------------------------------------
        # Debug
        # ----------------------------------------------------

        print(
            f"FRAME #{packet_count} | "
            f"size={len(data)} bytes | "
            f"total={total_bytes} bytes",
            flush=True
        )


        # ----------------------------------------------------
        # H.264 NAL type
        # ----------------------------------------------------

        normalized = normalize_h264(data)

        if normalized:

            # Tìm NAL header sau start code
            if normalized.startswith(b"\x00\x00\x00\x01"):

                if len(normalized) > 4:

                    nal_type = normalized[4] & 0x1F

                    print(
                        f"    NAL type: {nal_type}",
                        flush=True
                    )


        # ----------------------------------------------------
        # Send to ffplay
        # ----------------------------------------------------

        if not send_h264(ffplay, data):

            print(
                "FFplay process stopped.",
                flush=True
            )

            break


except KeyboardInterrupt:

    print(
        "\nStopping receiver...",
        flush=True
    )


finally:

    print(
        "Stopping receiver...",
        flush=True
    )

    # ============================
    # CLOSE TCP CONNECTION
    # ============================

    try:
        sock.shutdown(socket.SHUT_RDWR)
    except:
        pass

    try:
        sock.close()
    except:
        pass


    # ============================
    # CLOSE FFPLAY
    # ============================

    try:
        if ffplay.stdin:
            ffplay.stdin.close()
    except:
        pass


    # Cho ffplay một chút thời gian tự thoát
    try:
        ffplay.wait(timeout=1)

    except subprocess.TimeoutExpired:

        print(
            "FFplay did not exit. Terminating...",
            flush=True
        )

        try:
            ffplay.terminate()
            ffplay.wait(timeout=1)

        except subprocess.TimeoutExpired:

            print(
                "FFplay still running. Killing...",
                flush=True
            )

            try:
                ffplay.kill()
            except:
                pass

            try:
                ffplay.wait(timeout=1)
            except:
                pass


    print(
        "Receiver stopped.",
        flush=True
    )