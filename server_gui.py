import asyncio
import os
import socket
import subprocess
import shutil
import sys
import threading
from typing import Optional


def get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(*relative_parts: str) -> str:
    return os.path.join(get_base_dir(), *relative_parts)

from aiohttp import web
from PyQt6.QtCore import Qt, QTimer, QRegularExpression
from PyQt6.QtGui import QIcon, QPixmap, QRegularExpressionValidator, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)

from server import make_app

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8000


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            return sock.getsockname()[0]
    except Exception:
        return '127.0.0.1'


def get_adb_path():
    adb_path = shutil.which('adb')
    if adb_path:
        return adb_path

    base = os.path.dirname(__file__)
    candidate = os.path.join(base, 'static', 'adb', 'adb.exe')
    if os.path.isfile(candidate):
        return candidate

    return None


def run_adb_command(adb_path: str, args: list[str], *, check: bool = True, timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    command = [adb_path, *args]
    kwargs = {
        'text': True,
        'stdout': subprocess.PIPE,
        'stderr': subprocess.STDOUT,
    }
    if timeout is not None:
        kwargs['timeout'] = timeout
    if os.name == 'nt':
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if check:
        return subprocess.run(command, check=True, **kwargs)
    return subprocess.run(command, check=False, **kwargs)


def get_adb_device_name(adb_path: str, serial: str) -> Optional[str]:
    try:
        completed = run_adb_command(
            adb_path,
            ['-s', serial, 'shell', 'settings', 'get', 'global', 'device_name'],
            timeout=2.0,
        )
        name = completed.stdout.strip()
        return name if name else None
    except Exception:
        return None


class ServerThread(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.started = threading.Event()
        self.error: Optional[Exception] = None
        self.runner: Optional[web.AppRunner] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
    
    def run(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            app = make_app()
            self.runner = web.AppRunner(app)
            self.loop.run_until_complete(self.runner.setup())
            site = web.TCPSite(self.runner, self.host, self.port)
            self.loop.run_until_complete(site.start())
            self.started.set()
            self.loop.run_forever()
            self.loop.run_until_complete(self.runner.cleanup())
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
        except Exception as exc:
            self.error = exc
            self.started.set()
        finally:
            if self.loop and not self.loop.is_closed():
                self.loop.close()

    def stop(self):
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)


class HowToUseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('How to Use BachiTouch')
        self.setModal(True)
        self.setFixedSize(480, 540)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(10)

        button_row = QHBoxLayout()
        self.button_wifi = QPushButton('WIFI / PC Hotspot')
        self.button_usb = QPushButton('USB (Android)')
        self.button_open = QPushButton('Opening / Common')
        for btn in (self.button_wifi, self.button_usb, self.button_open):
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button_row.addWidget(btn)

        self.layout.addLayout(button_row)

        self.content_box = QLabel()
        self.content_box.setWordWrap(True)
        self.content_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.content_box.setStyleSheet(
            'QLabel { background: #121212; color: #eee; border: 1px solid #333; border-radius: 10px; padding: 10px; font-family: "Segoe UI", Arial, sans-serif; }'
        )
        self.content_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.layout.addWidget(self.content_box)

        self.button_close = QPushButton('Close')
        self.button_close.clicked.connect(self.accept)
        self.layout.addWidget(self.button_close)

        self.button_wifi.clicked.connect(lambda: self.show_section('wifi'))
        self.button_usb.clicked.connect(lambda: self.show_section('usb'))
        self.button_open.clicked.connect(lambda: self.show_section('open'))

        self.sections = {
            'wifi': (
                'WIFI / Hotspot Usage',
                '1. Start the server with the desired Host IP and Port. (Default is recommended.)\n\n'
                '2. If using Wi-Fi/hotspot, connect your mobile device to the same network.\n\n'
                '   You can also start a hotspot on this host PC and connect your device to it.\n\n'
                '3. Use the Mobile Device URL shown in the GUI on your phone.\n\n',
                'Note: This is the only way for iOS devices to connect.\n\n',
                'Note 2: Doing stuff like wired connection for iOS is too cumbersome and me is too lazy for that lol.',
            ),
            'usb': (
                'USB (Android) Usage',
                '1. Enable USB debugging on your Android device.\n\n'
                '2. Connect the device to the PC via USB cable.\n\n'
                '3. Enable "Connect by USB" in the GUI.\n\n'
                '4. The app will automatically use localhost and adb reverse to forward traffic.\n\n'
                '5. If the device is unauthorized, You will be prompted to authorize it.\n\n',
                '6. Use the Android Device URL shown in the GUI on your Android device browser.\n\n',
                'Note: Make sure your Android device is properly connected and recognized by ADB.',
            ),
            'open': (
                'Opening BachiTouch on Device & Common Steps',
                '1. On your device, open the URL shown in the GUI.\n\n'
                '2. Configure the drum key mappings on your phone.\n\n'
                '3. Tap the drum zones to send key presses to the PC.\n\n'
                '4. If the game needs focus, make sure the game window is active.\n\n'
                '5. Use the connected devices list to confirm ADB authorization status for USB mode.\n\n',
                'Made by Eurilism. Everything is literally vibecoded with Github Copilot lmao :DDD'
            ),
        }

        self.show_section('wifi')

    def show_section(self, section: str):
        self.button_wifi.setChecked(section == 'wifi')
        self.button_usb.setChecked(section == 'usb')
        self.button_open.setChecked(section == 'open')
        title, text = self.sections[section]
        self.content_box.setText(f'{title}\n\n{text}')
    


class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('BachiTouch Server')
        # Fixed-size window (non-resizable) with shorter width and sufficient height
        self.setFixedSize(480, 800)

        icon_path = get_resource_path('static', 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.server_thread: Optional[ServerThread] = None
        self.adb_reversed = False
        self.adb_port: Optional[int] = None
        self.usb_monitor_thread: Optional[threading.Thread] = None
        self.usb_monitor_stop = threading.Event()
        self.usb_unauthorized_prompted = False
        self.usb_devices: list[tuple[str, str, Optional[str]]] = []
        self.usb_device_lock = threading.Lock()
        self.pending_warning: Optional[tuple[str, str]] = None
        # when we programmatically change the USB checkbox, suppress the user confirm dialog
        self._suppress_usb_confirm = False

        self.init_ui()
        self.apply_style()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.on_status_tick)
        self.status_timer.start(200)

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        # ensure items are placed from the top so the icon doesn't center vertically
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # fixed icon at top
        icon_path = get_resource_path('static', 'icon-big.png')
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                label = QLabel()
                label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setFixedHeight(180)
                label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                main_layout.addWidget(label)

        # scrollable area for controls so icon remains visible when content grows
        controls_widget = QWidget()
        controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)

        settings_group = QGroupBox('Server Settings')
        settings_layout = QFormLayout()
        settings_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        settings_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        settings_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        settings_layout.setHorizontalSpacing(16)
        settings_layout.setVerticalSpacing(8)
        settings_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.host_input = QLineEdit(DEFAULT_HOST)
        self.host_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.host_input.setMinimumWidth(320)
        self.host_input.setFixedHeight(32)
        # allow only digits, periods, colons and slashes in the host input
        host_re = QRegularExpression(r'^[0-9\.:/]*$')
        host_validator = QRegularExpressionValidator(host_re, self.host_input)
        self.host_input.setValidator(host_validator)

        # Port input with a small "Set default" button to its right
        self.port_input = QLineEdit(str(DEFAULT_PORT))
        self.port_input.setMaximumWidth(140)
        self.port_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.port_input.setFixedHeight(32)
        # port should be digits only
        port_re = QRegularExpression(r'^\d*$')
        port_validator = QRegularExpressionValidator(port_re, self.port_input)
        self.port_input.setValidator(port_validator)

        port_row = QWidget()
        port_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # ensure the port row background is transparent so inputs match the groupbox
        port_row.setStyleSheet('background: transparent;')
        port_row_layout = QHBoxLayout(port_row)
        port_row_layout.setContentsMargins(0, 0, 0, 0)
        port_row_layout.setSpacing(8)
        # align controls to the left of the available field space
        port_row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        port_row_layout.addWidget(self.port_input)
        self.port_default_button = QPushButton('Set default')
        self.port_default_button.setFixedHeight(28)
        self.port_default_button.setFixedWidth(96)
        # match the primary button style (red) for consistency
        self.port_default_button.setStyleSheet('background: #b22222; color: white; border-radius: 8px; padding: 6px 10px;')
        self.port_default_button.clicked.connect(self.set_port_default)
        port_row_layout.addWidget(self.port_default_button)

        settings_layout.addRow('Server IP:', self.host_input)
        settings_layout.addRow('Port:', port_row)
        settings_group.setLayout(settings_layout)
        controls_layout.addWidget(settings_group)

        # USB row: checkbox with small help button to its right
        usb_row = QHBoxLayout()
        usb_row.setSpacing(8)
        self.usb_checkbox = QCheckBox('Connect by USB (Android)')
        self.usb_checkbox.toggled.connect(self.on_usb_toggled)
        usb_row.addWidget(self.usb_checkbox)
        self.help_button = QPushButton('?')
        # make the help button compact and aligned with the checkbox
        self.help_button.setFixedSize(28, 28)
        # remove extra padding from global QPushButton styles so the text is visible
        self.help_button.setStyleSheet('padding: 0px; margin: 0px; background: #b22222; color: white; border-radius: 6px;')
        self.help_button.clicked.connect(self.show_usb_help)
        usb_row.addWidget(self.help_button)
        usb_row.addStretch()
        controls_layout.addLayout(usb_row)

        # Start/stop button row (no help button here)
        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.start_button = QPushButton('Start Server')
        self.start_button.clicked.connect(self.toggle_server)
        button_row.addWidget(self.start_button)
        controls_layout.addLayout(button_row)

        status_group = QGroupBox('Server Status')
        status_layout = QVBoxLayout()
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel('Status:'))
        self.status_label = QLabel('Stopped')
        self.status_label.setObjectName('statusLabel')
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_layout.addLayout(status_row)
        status_group.setLayout(status_layout)
        controls_layout.addWidget(status_group)

        url_group = QGroupBox('Connection URLs')
        url_layout = QVBoxLayout()
        self.host_label = QLabel('Host PC URL:')
        self.host_url_label = QLabel('')
        self.host_url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.mobile_label = QLabel('Mobile Device URL:')
        self.mobile_url_label = QLabel('')
        self.mobile_url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        url_layout.addWidget(self.host_label)
        url_layout.addWidget(self.host_url_label)
        url_layout.addWidget(self.mobile_label)
        url_layout.addWidget(self.mobile_url_label)
        url_group.setLayout(url_layout)
        controls_layout.addWidget(url_group)

        self.device_group = QGroupBox('Connected Devices')
        self.device_group.setVisible(False)
        device_layout = QVBoxLayout()
        self.device_list = QListWidget()
        # Make the device list shorter so it won't take much vertical space
        self.device_list.setMinimumHeight(50)
        self.device_list.setMaximumHeight(100)
        self.device_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.device_list.setStyleSheet(
            'QListWidget { background: #1c1c1c; color: #f5f5f5; border: none; border-radius: 8px; padding: 6px; }'
            'QListWidget::item { background: transparent; color: #f5f5f5; padding: 8px; }'
            'QListWidget::item:selected { background: #2a2a2a; color: #fff; }'
            'QListWidget::item:hover { background: #2a2a2a; }'
        )
        self.device_list.setAlternatingRowColors(False)
        self.device_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        device_layout.addWidget(self.device_list)
        self.device_group.setLayout(device_layout)
        controls_layout.addWidget(self.device_group)

        self.helper_label = QLabel('Use localhost for host PC or the LAN URL for tablets/phones.')
        self.helper_label.setWordWrap(True)
        self.helper_label.setStyleSheet('color: #666;')
        controls_layout.addWidget(self.helper_label)

        self.how_to_button = QPushButton('How to Use')
        self.how_to_button.clicked.connect(self.show_how_to_use)
        controls_layout.addWidget(self.how_to_button)
        controls_layout.addStretch()

        # Place controls directly so everything is visible without scrolling
        main_layout.addWidget(controls_widget)

    def on_usb_toggled(self, checked: bool):
        """Handle USB checkbox toggles: disable/restore host input and stop server when disabling USB while running."""
        # If this toggle change was initiated programmatically and suppression is set,
        # clear the suppression flag and continue without prompting the user.
        if getattr(self, '_suppress_usb_confirm', False):
            self._suppress_usb_confirm = False
            # proceed with normal state changes (no confirm)
        else:
            # if user is turning USB off while server is running, confirm
            if not checked and self.server_thread and self.server_thread.is_alive():
                resp = QMessageBox.question(
                    self,
                    'Disable USB Connection?',
                    'Disabling "Connect by USB" will stop the running server. Do you want to continue?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if resp != QMessageBox.StandardButton.Yes:
                    # user cancelled: restore the checkbox to checked state without prompting
                    self._suppress_usb_confirm = True
                    self.usb_checkbox.setChecked(True)
                    return
        if checked:
            # remember previous host value so we can restore it when USB is turned off
            try:
                self._previous_host_value = self.host_input.text()
            except Exception:
                self._previous_host_value = DEFAULT_HOST
            # set to localhost to disable LAN access and disable editing
            self.host_input.setText('127.0.0.1')
            self.host_input.setEnabled(False)
            # if the server is already running, restart it on localhost
            if self.server_thread and self.server_thread.is_alive():
                self.stop_server()
                self.start_server()
        else:
            # re-enable host input and restore previous value if available
            self.host_input.setEnabled(True)
            if hasattr(self, '_previous_host_value') and self._previous_host_value:
                self.host_input.setText(self._previous_host_value)
        # If USB is being turned off while the server is running, stop the server
        if not checked and self.server_thread and self.server_thread.is_alive():
            self.stop_server()
        # Update URLs and other UI state
        self.update_urls()

    def relayout(self):
        """Adjust the window size to fit content, clamped to screen available height."""
        try:
            QApplication.processEvents()
            self.adjustSize()
            screen = QApplication.primaryScreen()
            if screen:
                max_h = int(screen.availableGeometry().height() * 0.9)
                # enforce minimums
                min_w, min_h = 480, 380
                new_w = max(self.width(), min_w)
                new_h = min(max(self.height(), min_h), max_h)
                self.resize(new_w, new_h)
        except Exception:
            pass

    def set_port_default(self):
        """Set the port input back to the DEFAULT_PORT value."""
        try:
            self.port_input.setText(str(DEFAULT_PORT))
        except Exception:
            pass

    def apply_style(self):
        self.setStyleSheet(
            """
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                background: #161616;
                color: #eee;
            }
            QGroupBox {
                background: #1c1c1c;
                border: 1px solid #333;
                border-radius: 10px;
                margin-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QPushButton {
                background: #b22222;
                color: white;
                border-radius: 10px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #9e1a1a;
            }
            QPushButton:disabled {
                background: #666;
            }
            QLineEdit {
                border: 1px solid #333;
                border-radius: 8px;
                padding: 6px;
                background: #1c1c1c;
                color: #eee;
            }
            QLineEdit:focus {
                border: 1px solid #5a5a5a;
                background: #212121;
            }
            QCheckBox {
                padding: 4px;
                color: #eee;
            }
            QLabel#statusLabel {
                color: #42a5f5;
                font-weight: 600;
            }
            QLabel {
                color: #eee;
                background: transparent;
            }
            """
        )

    def on_status_tick(self):
        if self.pending_warning:
            title, message = self.pending_warning
            self.pending_warning = None
            QMessageBox.warning(self, title, message)

        if not self.server_thread:
            return

        if not self.server_thread.started.is_set():
            return

        if self.server_thread.error:
            self.show_error('Server Error', str(self.server_thread.error))
            self.finish_stop()
            return

        if self.server_thread.is_alive():
            self.status_label.setText('Running')
            if self.start_button.text() != 'Stop Server':
                self.start_button.setText('Stop Server')
                self.start_button.setEnabled(True)
            self.update_urls()
            self.refresh_device_list()

    def toggle_server(self):
        if self.server_thread and self.server_thread.is_alive():
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        host = self.host_input.text().strip() or DEFAULT_HOST
        port = self.get_port()

        if port is None:
            self.show_error('Invalid Port', 'Port must be a number between 1 and 65535.')
            return

        self.server_thread = ServerThread(host, port)
        self.server_thread.start()
        self.status_label.setText('Starting...')
        self.start_button.setEnabled(False)

    def stop_server(self):
        if not self.server_thread:
            return

        port = self.get_port() or DEFAULT_PORT
        self.server_thread.stop()
        self.server_thread.join(timeout=2.0)
        self.finish_stop(port)

    def finish_stop(self, port: int = DEFAULT_PORT):
        self.server_thread = None
        self.stop_usb_monitor()
        self.stop_adb_reverse(port)
        self.status_label.setText('Stopped')
        self.start_button.setText('Start Server')
        self.start_button.setEnabled(True)
        self.host_url_label.setText('')
        self.mobile_url_label.setText('')
        self.mobile_label.setVisible(True)
        self.mobile_url_label.setVisible(True)
        self.helper_label.setText('Use localhost for host PC or the LAN URL for tablets/phones.')
        # Clear and hide device list when server stops, even if USB mode is checked
        with self.usb_device_lock:
            self.usb_devices = []
        self.device_list.clear()
        self.device_group.setVisible(False)
        # ensure window shrinks to reflect hidden device list
        self.relayout()

    def get_port(self) -> Optional[int]:
        try:
            port_value = int(self.port_input.text().strip() or str(DEFAULT_PORT))
            if 1 <= port_value <= 65535:
                return port_value
        except ValueError:
            pass
        return None

    def update_urls(self):
        if not self.server_thread:
            self.host_url_label.setText('')
            self.mobile_url_label.setText('')
            return

        host = self.host_input.text().strip() or DEFAULT_HOST
        port = self.get_port() or DEFAULT_PORT
        lan_ip = get_local_ip()

        if host in ('0.0.0.0', '::', ''):
            host_url = f'http://localhost:{port}'
            mobile_url = f'http://{lan_ip}:{port}'
        else:
            host_url = f'http://{host}:{port}'
            mobile_url = host_url

        if self.usb_checkbox.isChecked():
            self.host_label.setText('Android Device URL:')
            self.host_url_label.setText(f'http://localhost:{port}')
            self.mobile_label.setVisible(False)
            self.mobile_url_label.setVisible(False)
            self.helper_label.setText('')
            if self.server_thread and self.server_thread.is_alive():
                self.start_usb_monitor(port)
        else:
            self.host_label.setText('Host PC URL:')
            self.host_url_label.setText(host_url)
            self.mobile_label.setVisible(True)
            self.mobile_url_label.setVisible(True)
            self.mobile_url_label.setText(mobile_url)
            self.stop_usb_monitor()
            self.stop_adb_reverse(port)
            self.helper_label.setText('Use localhost for host PC or the LAN URL for tablets/phones.')
            self.update_device_list([])
        # adjust window size after changing visible content
        self.relayout()

    def start_adb_reverse(self, port: int):
        if self.adb_reversed and self.adb_port == port:
            return

        adb_path = get_adb_path()
        if not adb_path:
            self.show_error(
                'ADB Not Found',
                'ADB is not installed or not on PATH, and static/adb/adb.exe was not found. Please install Android platform tools or place adb.exe in the static/adb folder.',
            )
            # programmatic change - don't prompt the user
            self._suppress_usb_confirm = True
            self.usb_checkbox.setChecked(False)
            self.update_urls()
            return

        try:
            run_adb_command(adb_path, ['reverse', f'tcp:{port}', f'tcp:{port}'])
            self.adb_reversed = True
            self.adb_port = port
        except subprocess.CalledProcessError as exc:
            self.show_error('ADB Reverse Failed', f'Could not set up USB reverse port forwarding.\n\n{exc.stdout}')
            self._suppress_usb_confirm = True
            self.usb_checkbox.setChecked(False)
            self.update_urls()
        except Exception as exc:
            self.show_error('ADB Error', f'Unexpected error while running adb:\n{exc}')
            self._suppress_usb_confirm = True
            self.usb_checkbox.setChecked(False)
            self.update_urls()

    def stop_adb_reverse(self, port: int):
        if not self.adb_reversed:
            return

        adb_path = get_adb_path()
        if not adb_path:
            self.adb_reversed = False
            self.adb_port = None
            return

        try:
            run_adb_command(adb_path, ['reverse', '--remove', f'tcp:{port}'], check=False)
        except Exception:
            pass
        finally:
            self.adb_reversed = False
            self.adb_port = None

    def start_usb_monitor(self, port: int):
        if self.usb_monitor_thread and self.usb_monitor_thread.is_alive():
            return

        adb_path = get_adb_path()
        if not adb_path:
            self.show_error(
                'ADB Not Found',
                'ADB is not installed or not on PATH, and static/adb/adb.exe was not found. Please install Android platform tools or place adb.exe in the static/adb folder.',
            )
            self._suppress_usb_confirm = True
            self.usb_checkbox.setChecked(False)
            self.update_urls()
            return

        self.usb_monitor_stop.clear()
        self.usb_unauthorized_prompted = False
        self.usb_monitor_thread = threading.Thread(target=self._usb_monitor_loop, args=(port,), daemon=True)
        self.usb_monitor_thread.start()

    def stop_usb_monitor(self):
        self.usb_monitor_stop.set()
        if self.usb_monitor_thread and self.usb_monitor_thread.is_alive():
            self.usb_monitor_thread.join(timeout=1.0)
        self.usb_monitor_thread = None
        self.usb_monitor_stop.clear()
        self.usb_unauthorized_prompted = False

    def _usb_monitor_loop(self, port: int):
        adb_path = get_adb_path()
        if not adb_path:
            return

        while not self.usb_monitor_stop.is_set() and self.server_thread and self.server_thread.is_alive() and self.usb_checkbox.isChecked():
            try:
                completed = run_adb_command(adb_path, ['devices'])
                output = completed.stdout
            except Exception:
                devices = []
            else:
                devices = []
                for line in output.splitlines()[1:]:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        serial, state = parts[0], parts[1]
                        name = get_adb_device_name(adb_path, serial) if state == 'device' else None
                        devices.append((serial, state, name))

            with self.usb_device_lock:
                self.usb_devices = devices

            authorized_device = any(state == 'device' for _, state, _ in devices)
            unauthorized_device = any(state == 'unauthorized' for _, state, _ in devices)

            if authorized_device:
                self._ensure_adb_reverse(port)
            elif unauthorized_device:
                if not self.usb_unauthorized_prompted:
                    self.usb_unauthorized_prompted = True
                    self.pending_warning = (
                        'Authorize USB Debugging',
                        'An Android device was detected in unauthorized mode.\n\nPlease allow USB debugging authorization on the device.\nIf the prompt does not appear, unplug and replug the USB cable.',
                    )
                self.stop_adb_reverse(port)
            else:
                self.stop_adb_reverse(port)

            self.usb_monitor_stop.wait(5.0)

    def _ensure_adb_reverse(self, port: int):
        if not self.adb_reversed or self.adb_port != port:
            self.start_adb_reverse(port)

    def refresh_device_list(self):
        if not self.usb_checkbox.isChecked():
            self.device_group.setVisible(False)
            self.update_device_list([])
            self.relayout()
            return

        with self.usb_device_lock:
            devices = list(self.usb_devices)
        self.update_device_list(devices)
        self.relayout()

    def update_device_list(self, devices: list[tuple[str, str, Optional[str]]]):
        self.device_list.clear()
        if not devices:
            item = QListWidgetItem('No USB devices detected.')
            item.setForeground(QColor('#999999'))
            self.device_list.addItem(item)
            self.device_group.setVisible(self.usb_checkbox.isChecked())
            return

        self.device_group.setVisible(True)
        for serial, state, name in devices:
            display_name = name or serial
            status_text = 'authorized' if state == 'device' else state
            item = QListWidgetItem(f'{display_name} — {status_text}')
            # color status: green for authorized, red for unauthorized, default for others
            if status_text == 'authorized':
                item.setForeground(QColor('#4caf50'))
            elif status_text == 'unauthorized':
                item.setForeground(QColor('#f44336'))
            else:
                item.setForeground(QColor('#f5f5f5'))
            self.device_list.addItem(item)

    def show_error(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def show_usb_help(self):
        QMessageBox.information(
            self,
            'USB Connection Help',
            'To connect your Android device over USB:\n\n'
            '1. Enable USB debugging on the Android device.\n'
            '2. Connect the phone to the PC with USB.\n'
            '3. Allow USB debugging when prompted.\n'
            '4. Enable "Connect by USB" in the GUI.\n'
            '5. Start the server.\n\n'
            'Note: Enabling/Disabling USB mode will restart/stop the server if it is running.\n\n'
            'The GUI will automatically run adb reverse to forward port traffic.\n'
            'If adb is unavailable or the reverse command fails, USB mode will be disabled.\n\n'
            'On the phone, open the url found in the GUI.\n'
        )

    def show_how_to_use(self):
        dialog = HowToUseDialog(self)
        dialog.exec()

    def closeEvent(self, event):
        if self.server_thread and self.server_thread.is_alive():
            self.stop_server()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = ServerGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
