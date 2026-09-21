import socket
import json

DISCOVERY_PORT = 37020
DISCOVERY_TIMEOUT = 2.0


def discover_devices():
    request = json.dumps({
        "type": "DROIDLINK_DISCOVERY_REQUEST"
    }).encode("utf-8")

    devices = {}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(DISCOVERY_TIMEOUT)

    try:
        sock.bind(("0.0.0.0", 0))

        # Mạng của bạn hiện tại: 192.168.1.x
        sock.sendto(
            request,
            ("192.168.1.255", DISCOVERY_PORT)
        )

        while True:
            try:
                data, address = sock.recvfrom(4096)
            except socket.timeout:
                break

            try:
                message = json.loads(
                    data.decode("utf-8")
                )
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

            if message.get("type") != "DROIDLINK_DISCOVERY":
                continue

            ip = address[0]

            devices[ip] = {
                "name": message.get(
                    "name",
                    "DroidLink"
                ),
                "ip": ip,
                "port": int(
                    message.get(
                        "port",
                        8080
                    )
                )
            }

    finally:
        sock.close()

    return list(devices.values())