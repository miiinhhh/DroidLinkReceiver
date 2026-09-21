APP_STYLE = """
QMainWindow {
    background: #0f1115;
}

QWidget {
    color: #f3f4f6;
    font-family: "Segoe UI";
    font-size: 14px;
}

QFrame#sidebar {
    background: #171a21;
    border-right: 1px solid #292e38;
}

QLabel#logo {
    font-size: 22px;
    font-weight: 700;
}

QLabel#subtitle {
    color: #8b93a1;
    font-size: 12px;
}

QLabel#section {
    color: #737c8c;
    font-size: 11px;
    font-weight: 700;
}

QFrame#deviceCard {
    background: #1e232c;
    border: 1px solid #303744;
    border-radius: 12px;
}

QFrame#deviceCard:hover {
    border: 1px solid #4b5563;
}

QLabel#deviceName {
    font-size: 14px;
    font-weight: 600;
}

QLabel#deviceInfo {
    color: #929baa;
    font-size: 12px;
}

QLabel#online {
    color: #45d483;
    font-size: 12px;
    font-weight: 600;
}

QPushButton {
    background: #242a34;
    border: 1px solid #343b48;
    border-radius: 9px;
    padding: 9px 14px;
}

QPushButton:hover {
    background: #2c333f;
}

QPushButton#primary {
    background: #4f7cff;
    border: none;
    font-weight: 600;
}

QPushButton#primary:hover {
    background: #628cff;
}

QPushButton#danger {
    background: #b83d4d;
    border: none;
    font-weight: 600;
}

QPushButton#danger:hover {
    background: #ca4a5b;
}

QPushButton#nav {
    text-align: left;
    background: transparent;
    border: none;
    color: #aeb6c4;
    padding: 11px 12px;
}

QPushButton#nav:hover {
    background: #20252e;
    color: #ffffff;
}

QPushButton#nav[selected="true"] {
    background: #252c38;
    color: #ffffff;
}

QLabel#pageTitle {
    font-size: 26px;
    font-weight: 700;
}

QLabel#pageSubtitle {
    color: #8b93a1;
}

QFrame#contentCard {
    background: #171b22;
    border: 1px solid #292f3a;
    border-radius: 14px;
}

QLabel#preview {
    background: #0a0c10;
    border: 1px solid #252a33;
    border-radius: 12px;
    color: #687180;
}

QLabel#status {
    color: #8f98a7;
}

QStatusBar {
    background: #11141a;
    color: #7f8897;
}
"""
