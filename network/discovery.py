import socket
import json
import ipaddress

DISCOVERY_PORT = 37020
DISCOVERY_TIMEOUT = 2.0


def get_broadcast_address():
    """Tự tìm broadcast address của mạng LAN hiện tại."""

    hostname = socket.gethostname()

    try:
        local_ip = socket.gethostbyname(hostname)

        # Nếu lấy được IP LAN bình thường
        if not local_ip.startswith("127."):
            network = ipaddress.IPv4Network(
                f"{local_ip}/24",
                strict=False
            )

            return str(network.broadcast_address)

    except Exception:
        pass

    return "255.255.255.255"


def discover_devices():
    request = json.dumps({
        "type": "DROIDLINK_DISCOVERY_REQUEST"
    }).encode("utf-8")

    devices = {}

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_BROADCAST,
        1
    )

    sock.settimeout(DISCOVERY_TIMEOUT)

    try:
        sock.bind(("0.0.0.0", 0))

        broadcast_address = get_broadcast_address()

        print(
            f"Discovery broadcast: "
            f"{broadcast_address}:{DISCOVERY_PORT}"
        )

        sock.sendto(
            request,
            (broadcast_address, DISCOVERY_PORT)
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