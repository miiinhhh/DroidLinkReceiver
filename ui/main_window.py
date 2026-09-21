import socket
import struct
import subprocess

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QMessageBox,
)

from network.discovery import discover_devices
from network.connection import DroidLinkConnection
from ui.styles import APP_STYLE


FFPLAY_COMMAND = [
    "ffplay",
    "-loglevel", "warning",
    "-f", "h264",
    "-fflags", "nobuffer",
    "-flags", "low_delay",
    "-framedrop",
    "-window_title", "DroidLink",
    "pipe:0",
]


class DiscoveryWorker(QThread):

    finished_devices = Signal(list)

    def run(self):
        devices = discover_devices()
        self.finished_devices.emit(devices)


class StreamWorker(QThread):

    error = Signal(str)
    status = Signal(str)

    def __init__(self, sock):
        super().__init__()

        self.sock = sock
        self.running = True
        self.ffplay = None

    def recv_exact(self, size):

        data = b""

        while len(data) < size and self.running:

            chunk = self.sock.recv(
                size - len(data)
            )

            if not chunk:
                raise ConnectionError(
                    "Android disconnected"
                )

            data += chunk

        return data

    def send_to_ffplay(self, data):

        if self.ffplay and self.ffplay.stdin:

            self.ffplay.stdin.write(data)
            self.ffplay.stdin.flush()

    def run(self):

        try:

            self.status.emit(
                "Waiting for H.264 stream..."
            )

            # SPS
            sps_size = struct.unpack(
                ">I",
                self.recv_exact(4)
            )[0]

            if sps_size <= 0 or sps_size > 1024 * 1024:
                raise ValueError(
                    f"Invalid SPS size: {sps_size}"
                )

            sps = self.recv_exact(
                sps_size
            )

            # PPS
            pps_size = struct.unpack(
                ">I",
                self.recv_exact(4)
            )[0]

            if pps_size <= 0 or pps_size > 1024 * 1024:
                raise ValueError(
                    f"Invalid PPS size: {pps_size}"
                )

            pps = self.recv_exact(
                pps_size
            )

            self.status.emit(
                "H.264 connected"
            )

            # Start ffplay
            self.ffplay = subprocess.Popen(
                FFPLAY_COMMAND,
                stdin=subprocess.PIPE
            )

            self.send_to_ffplay(
                self.to_annex_b(sps)
            )

            self.send_to_ffplay(
                self.to_annex_b(pps)
            )

            frame_count = 0

            while self.running:

                size_data = self.recv_exact(4)

                packet_size = struct.unpack(
                    ">I",
                    size_data
                )[0]

                if (
                    packet_size <= 0
                    or packet_size > 10 * 1024 * 1024
                ):
                    raise ValueError(
                        f"Invalid H.264 packet size: {packet_size}"
                    )

                packet = self.recv_exact(
                    packet_size
                )

                self.send_to_ffplay(
                    self.to_annex_b(packet)
                )

                frame_count += 1

                if frame_count % 30 == 0:

                    self.status.emit(
                        f"Streaming... {frame_count} frames"
                    )

        except Exception as e:

            if self.running:

                self.error.emit(
                    str(e)
                )

        finally:

            self.running = False

            if self.ffplay:

                try:

                    if self.ffplay.stdin:
                        self.ffplay.stdin.close()

                except Exception:
                    pass

                try:

                    self.ffplay.terminate()
                    self.ffplay.wait(
                        timeout=2
                    )

                except Exception:

                    try:
                        self.ffplay.kill()

                    except Exception:
                        pass

                self.ffplay = None

    def to_annex_b(self, data):

        # Already Annex-B
        if data.startswith(
            b"\x00\x00\x00\x01"
        ):
            return data

        if data.startswith(
            b"\x00\x00\x01"
        ):
            return data

        # AVCC -> Annex-B
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
                break

            result += b"\x00\x00\x00\x01"

            result += data[
                offset:offset + nal_size
            ]

            offset += nal_size

        if result:
            return bytes(result)

        return data

    def stop(self):

        self.running = False

        try:
            self.sock.shutdown(
                socket.SHUT_RDWR
            )

        except Exception:
            pass


class DeviceCard(QFrame):

    connect_clicked = Signal(dict)

    def __init__(self, device):

        super().__init__()

        self.device = device

        self.setObjectName(
            "deviceCard"
        )

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            14, 13, 14, 13
        )

        layout.setSpacing(5)

        top = QHBoxLayout()

        icon = QLabel("📱")
        icon.setFixedWidth(28)

        name = QLabel(
            device["name"]
        )

        name.setObjectName(
            "deviceName"
        )

        online = QLabel(
            "● Online"
        )

        online.setObjectName(
            "online"
        )

        top.addWidget(icon)
        top.addWidget(name)
        top.addStretch()
        top.addWidget(online)

        info = QLabel(
            f'{device["ip"]}:{device["port"]}'
        )

        info.setObjectName(
            "deviceInfo"
        )

        button = QPushButton(
            "Connect"
        )

        button.setObjectName(
            "primary"
        )

        button.clicked.connect(
            lambda: self.connect_clicked.emit(
                self.device
            )
        )

        bottom = QHBoxLayout()

        bottom.addWidget(info)
        bottom.addStretch()
        bottom.addWidget(button)

        layout.addLayout(top)
        layout.addLayout(bottom)


class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "DroidLink"
        )

        self.resize(
            1180,
            720
        )

        self.setMinimumSize(
            950,
            600
        )

        self.setStyleSheet(
            APP_STYLE
        )

        self.connection = None
        self.current_device = None

        self.discovery_worker = None
        self.stream_worker = None

        self.build_ui()

        self.statusBar().showMessage(
            "Ready"
        )

    def build_ui(self):

        root = QWidget()

        root_layout = QHBoxLayout(
            root
        )

        root_layout.setContentsMargins(
            0, 0, 0, 0
        )

        root_layout.setSpacing(0)

        root_layout.addWidget(
            self.build_sidebar()
        )

        self.pages = QStackedWidget()

        self.pages.addWidget(
            self.build_home_page()
        )

        self.pages.addWidget(
            self.build_mirror_page()
        )

        self.pages.addWidget(
            self.build_settings_page()
        )

        root_layout.addWidget(
            self.pages,
            1
        )

        self.setCentralWidget(
            root
        )

    def build_sidebar(self):

        sidebar = QFrame()

        sidebar.setObjectName(
            "sidebar"
        )

        sidebar.setFixedWidth(
            230
        )

        layout = QVBoxLayout(
            sidebar
        )

        layout.setContentsMargins(
            20, 24, 20, 20
        )

        layout.setSpacing(8)

        logo = QLabel(
            "◉ DroidLink"
        )

        logo.setObjectName(
            "logo"
        )

        subtitle = QLabel(
            "Android → Laptop"
        )

        subtitle.setObjectName(
            "subtitle"
        )

        layout.addWidget(logo)
        layout.addWidget(subtitle)

        layout.addSpacing(28)

        section = QLabel(
            "WORKSPACE"
        )

        section.setObjectName(
            "section"
        )

        layout.addWidget(
            section
        )

        home = QPushButton(
            "⌂   Devices"
        )

        home.setObjectName(
            "nav"
        )

        home.clicked.connect(
            lambda: self.pages.setCurrentIndex(0)
        )

        mirror = QPushButton(
            "▣   Screen Mirroring"
        )

        mirror.setObjectName(
            "nav"
        )

        mirror.clicked.connect(
            lambda: self.pages.setCurrentIndex(1)
        )

        settings = QPushButton(
            "⚙   Settings"
        )

        settings.setObjectName(
            "nav"
        )

        settings.clicked.connect(
            lambda: self.pages.setCurrentIndex(2)
        )

        layout.addWidget(home)
        layout.addWidget(mirror)
        layout.addWidget(settings)

        layout.addStretch()

        version = QLabel(
            "DroidLink Desktop\nMVP"
        )

        version.setObjectName(
            "subtitle"
        )

        layout.addWidget(
            version
        )

        return sidebar

    def build_home_page(self):

        page = QWidget()

        layout = QVBoxLayout(
            page
        )

        layout.setContentsMargins(
            34, 30, 34, 30
        )

        layout.setSpacing(18)

        header = QHBoxLayout()

        title_box = QVBoxLayout()

        title = QLabel(
            "Devices"
        )

        title.setObjectName(
            "pageTitle"
        )

        subtitle = QLabel(
            "Find and connect to Android devices on your local network."
        )

        subtitle.setObjectName(
            "pageSubtitle"
        )

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        refresh = QPushButton(
            "↻  Discover"
        )

        refresh.setObjectName(
            "primary"
        )

        refresh.clicked.connect(
            self.start_discovery
        )

        header.addLayout(
            title_box
        )

        header.addStretch()

        header.addWidget(
            refresh
        )

        layout.addLayout(
            header
        )

        card = QFrame()

        card.setObjectName(
            "contentCard"
        )

        card_layout = QVBoxLayout(
            card
        )

        card_layout.setContentsMargins(
            18, 18, 18, 18
        )

        self.device_list = QVBoxLayout()

        self.device_list.setSpacing(
            10
        )

        self.empty_label = QLabel(
            "No devices found.\n"
            "Click Discover to search for DroidLink devices."
        )

        self.empty_label.setObjectName(
            "pageSubtitle"
        )

        self.empty_label.setAlignment(
            Qt.AlignCenter
        )

        card_layout.addWidget(
            self.empty_label
        )

        card_layout.addLayout(
            self.device_list
        )

        card_layout.addStretch()

        layout.addWidget(
            card,
            1
        )

        return page

    def build_mirror_page(self):

        page = QWidget()

        layout = QVBoxLayout(
            page
        )

        layout.setContentsMargins(
            34, 30, 34, 30
        )

        layout.setSpacing(18)

        header = QHBoxLayout()

        title_box = QVBoxLayout()

        title = QLabel(
            "Screen Mirroring"
        )

        title.setObjectName(
            "pageTitle"
        )

        self.mirror_status = QLabel(
            "Not connected"
        )

        self.mirror_status.setObjectName(
            "pageSubtitle"
        )

        title_box.addWidget(title)
        title_box.addWidget(
            self.mirror_status
        )

        self.start_button = QPushButton(
            "Start Sharing"
        )

        self.start_button.setObjectName(
            "primary"
        )

        self.start_button.clicked.connect(
            self.start_sharing
        )

        self.stop_button = QPushButton(
            "Stop"
        )

        self.stop_button.setObjectName(
            "danger"
        )

        self.stop_button.setEnabled(
            False
        )

        self.stop_button.clicked.connect(
            self.stop_sharing
        )

        header.addLayout(
            title_box
        )

        header.addStretch()

        header.addWidget(
            self.start_button
        )

        header.addWidget(
            self.stop_button
        )

        layout.addLayout(
            header
        )

        preview_card = QFrame()

        preview_card.setObjectName(
            "contentCard"
        )

        preview_layout = QVBoxLayout(
            preview_card
        )

        preview_layout.setContentsMargins(
            18, 18, 18, 18
        )

        self.preview = QLabel(
            "Screen preview\n\n"
            "Connect to an Android device to begin."
        )

        self.preview.setObjectName(
            "preview"
        )

        self.preview.setAlignment(
            Qt.AlignCenter
        )

        self.preview.setMinimumHeight(
            450
        )

        preview_layout.addWidget(
            self.preview,
            1
        )

        stats = QHBoxLayout()

        self.device_status = QLabel(
            "Device: —"
        )

        self.fps_status = QLabel(
            "FPS: —"
        )

        self.network_status = QLabel(
            "Network: —"
        )

        stats.addWidget(
            self.device_status
        )

        stats.addStretch()

        stats.addWidget(
            self.fps_status
        )

        stats.addStretch()

        stats.addWidget(
            self.network_status
        )

        preview_layout.addLayout(
            stats
        )

        layout.addWidget(
            preview_card,
            1
        )

        return page

    def build_settings_page(self):

        page = QWidget()

        layout = QVBoxLayout(
            page
        )

        layout.setContentsMargins(
            34, 30, 34, 30
        )

        title = QLabel(
            "Settings"
        )

        title.setObjectName(
            "pageTitle"
        )

        subtitle = QLabel(
            "DroidLink desktop settings will be added here."
        )

        subtitle.setObjectName(
            "pageSubtitle"
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()

        return page

    def clear_devices(self):

        while self.device_list.count():

            item = self.device_list.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

    def start_discovery(self):

        if (
            self.discovery_worker
            and self.discovery_worker.isRunning()
        ):
            return

        self.clear_devices()

        self.empty_label.setText(
            "Searching for DroidLink devices..."
        )

        self.empty_label.show()

        self.statusBar().showMessage(
            "Discovering devices..."
        )

        self.discovery_worker = DiscoveryWorker()

        self.discovery_worker.finished_devices.connect(
            self.show_devices
        )

        self.discovery_worker.start()

    def show_devices(self, devices):

        self.clear_devices()

        if not devices:

            self.empty_label.show()

            self.empty_label.setText(
                "No devices found.\n"
                "Make sure DroidLink is open and both devices are on the same network."
            )

            self.statusBar().showMessage(
                "No devices found"
            )

            return

        self.empty_label.hide()

        for device in devices:

            card = DeviceCard(
                device
            )

            card.connect_clicked.connect(
                self.connect_device
            )

            self.device_list.addWidget(
                card
            )

        self.statusBar().showMessage(
            f"{len(devices)} device(s) found"
        )

    def connect_device(self, device):

        try:

            # Stop old stream
            if self.stream_worker:

                self.stream_worker.stop()

                self.stream_worker.wait(
                    1000
                )

                self.stream_worker = None

            # Close old connection
            if self.connection:

                self.connection.close()

                self.connection = None

            print(
                f"Connecting to "
                f"{device['ip']}:{device['port']}"
            )

            self.connection = DroidLinkConnection(
                device["ip"],
                device["port"]
            )

            self.connection.connect()

            print(
                "TCP connection successful"
            )

            self.current_device = device

            self.mirror_status.setText(
                f'Connected to {device["name"]} • {device["ip"]}'
            )

            self.device_status.setText(
                f'Device: {device["name"]}'
            )

            self.network_status.setText(
                f'Network: {device["ip"]}:{device["port"]}'
            )

            self.pages.setCurrentIndex(
                1
            )

            self.statusBar().showMessage(
                f'Connected to {device["name"]}'
            )

        except Exception as e:

            print(
                "Connection failed:",
                repr(e)
            )

            self.connection = None

            QMessageBox.critical(
                self,
                "Connection failed",
                f"Could not connect to "
                f"{device['name']}.\n\n{e}"
            )

            self.statusBar().showMessage(
                "Connection failed"
            )

    def start_sharing(self):

        if not self.connection:

            QMessageBox.warning(
                self,
                "Chưa kết nối",
                "Vui lòng kết nối với điện thoại trước."
            )

            return

        try:

            self.stream_worker = StreamWorker(
                self.connection.sock
            )

            self.stream_worker.status.connect(
                self.on_stream_status
            )

            self.stream_worker.error.connect(
                self.on_stream_error
            )

            self.stream_worker.start()

            self.connection.start_stream()

            self.start_button.setEnabled(
                False
            )

            self.stop_button.setEnabled(
                True
            )

            self.mirror_status.setText(
                "Đang chờ điện thoại bắt đầu chia sẻ..."
            )

            self.statusBar().showMessage(
                "Waiting for Android stream..."
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Share Error",
                str(e)
            )

            self.start_button.setEnabled(
                True
            )

            self.stop_button.setEnabled(
                False
            )

    def on_stream_status(self, message):

        self.mirror_status.setText(
            message
        )

        self.statusBar().showMessage(
            message
        )

        if message == "H.264 connected":

            self.preview.setText(
                "DroidLink is streaming..."
            )

    def on_stream_error(self, message):

        self.statusBar().showMessage(
            f"Stream error: {message}"
        )

        self.mirror_status.setText(
            "Stream stopped"
        )

        self.start_button.setEnabled(
            True
        )

        self.stop_button.setEnabled(
            False
        )

    def stop_sharing(self):

        if self.stream_worker:

            self.stream_worker.stop()

            self.stream_worker.wait(
                1000
            )

            self.stream_worker = None

        if self.connection:

            self.connection.close()

            self.connection = None

        self.start_button.setEnabled(
            True
        )

        self.stop_button.setEnabled(
            False
        )

        self.preview.setText(
            "Screen preview\n\n"
            "Connect to an Android device to begin."
        )

        self.mirror_status.setText(
            "Not connected"
        )

        self.device_status.setText(
            "Device: —"
        )

        self.network_status.setText(
            "Network: —"
        )

        self.statusBar().showMessage(
            "Disconnected"
        )

    def closeEvent(self, event):

        self.stop_sharing()

        event.accept()