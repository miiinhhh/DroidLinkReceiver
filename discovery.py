import socket
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed


STREAMING_PORT = 8080
SCAN_TIMEOUT = 0.15


def get_local_ip():
    """
    Lấy IP LAN của laptop.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


def get_subnet():
    """
    Ví dụ:
        192.168.1.4
    =>
        192.168.1.0/24
    """
    local_ip = get_local_ip()

    if local_ip == "127.0.0.1":
        return None

    parts = local_ip.split(".")

    if len(parts) != 4:
        return None

    subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"

    return ipaddress.ip_network(subnet, strict=False)


def check_device(ip):
    """
    Kiểm tra một IP có mở DroidLink TCP port 8080 hay không.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(SCAN_TIMEOUT)

    try:
        result = sock.connect_ex((str(ip), STREAMING_PORT))

        if result == 0:
            return {
                "name": "DroidLink",
                "ip": str(ip),
                "port": STREAMING_PORT
            }

    except Exception:
        pass

    finally:
        sock.close()

    return None


def discover_devices():
    """
    Quét toàn bộ subnet LAN để tìm DroidLink.
    """

    subnet = get_subnet()

    if subnet is None:
        print("Could not determine local subnet.", flush=True)
        return []

    local_ip = get_local_ip()

    print()
    print("======================================")
    print("DroidLink Device Discovery")
    print("======================================")
    print(f"Laptop IP : {local_ip}")
    print(f"Subnet    : {subnet}")
    print(f"Scanning  : TCP port {STREAMING_PORT}")
    print("======================================")
    print()

    devices = []

    hosts = [
        ip for ip in subnet.hosts()
        if str(ip) != local_ip
    ]

    with ThreadPoolExecutor(max_workers=50) as executor:

        futures = [
            executor.submit(check_device, ip)
            for ip in hosts
        ]

        for future in as_completed(futures):

            device = future.result()

            if device is not None:
                devices.append(device)

                print()
                print("=== DroidLink Device Found ===")
                print(f"Name : {device['name']}")
                print(f"IP   : {device['ip']}")
                print(f"Port : {device['port']}")
                print("==============================")
                print()

    if not devices:
        print()
        print("No DroidLink device found.")
        print()

    return devices


def discover_device():
    """
    Tương thích với receiver.py cũ.
    Trả về device đầu tiên tìm được.
    """

    devices = discover_devices()

    if not devices:
        return None

    return devices[0]