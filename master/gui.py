import time
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QLabel, QHBoxLayout,
    QLineEdit, QMessageBox, QGroupBox, QGridLayout, QFrame,
    QScrollArea, QPlainTextEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette

from modbus_client import ModbusClientA
from tcp_server import TCPServerForC
from utils import SignalEmitter, validate_pos_speed
from config import *


class LayerB_SCADASupervisor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAYER B - SCADA SUPERVISOR")
        self.setGeometry(100, 100, 1200, 900)
        
        # Thiết lập palette màu theo style SLAVE LAYER
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        self.setPalette(palette)

        # State variables
        self.current_position = 0
        self.current_speed = 0
        self.temperature = 0.0
        self.humidity = 0.0
        self.driver_alarm = False
        self.driver_inpos = False
        self.driver_running = False
        self.auto_state_code = 0
        self.sht20_enabled = True
        self.current_mode = 0
        self.step_enabled = False
        self.jog_state = 0

        # Statistics
        self.commands_from_c = 0
        self.status_updates = 0
        self.start_time = time.time()
        
        # Network components
        self.modbus_client = ModbusClientA()
        self.tcp_server = TCPServerForC()
        
        # Signals
        self.signals = SignalEmitter()
        self.signals.log_signal.connect(self.append_log)
        self.signals.status_update.connect(self.update_displays)
        self.signals.connection_signal.connect(self.update_connection_status)
        self.signals.forward_signal.connect(self.show_forward_animation)

        # UI
        self._build_ui()
        self._setup_connections()

        # Stats update timer
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_statistics)
        self.stats_timer.start(1000)
        
        # Auto-start TCP server
        self.start_server_for_c()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
        """)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        # 1. HEADER
        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.StyledPanel)
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                          stop:0 #2c3e50, stop:1 #34495e);
                border-radius: 10px;
                padding: 20px;
            }
        """)
        header_layout = QVBoxLayout()

        title_label = QLabel("SCADA SUPERVISOR - MONITOR & CONTROL")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 24pt;
                font-weight: bold;
                padding: 10px;
            }
        """)
        header_layout.addWidget(title_label)

        subtitle_label = QLabel("Layer B - Priority 2 - Device Supervisor")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                font-size: 12pt;
                padding: 5px;
            }
        """)
        header_layout.addWidget(subtitle_label)

        header_frame.setLayout(header_layout)
        layout.addWidget(header_frame)

        # 2. CONNECTION PANEL - theo style SLAVE LAYER
        conn_group = QGroupBox("MODBUS TCP CONNECTION")
        conn_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #2c3e50;
            }
        """)
        conn_layout = QVBoxLayout()

        # Connection info frame
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_frame.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        info_layout = QGridLayout()

        info_layout.addWidget(QLabel("Server Address:"), 0, 0)
        addr_label = QLabel(f"{A_HOST}:{A_MODBUS_PORT}")
        addr_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        info_layout.addWidget(addr_label, 0, 1)

        info_layout.addWidget(QLabel("Status:"), 1, 0)
        self.lbl_conn_status = QLabel("DISCONNECTED")
        self.lbl_conn_status.setStyleSheet("""
            font-weight: bold;
            font-size: 11pt;
            color: #e74c3c;
            padding: 4px 12px;
            border-radius: 4px;
            background: #ffebee;
        """)
        info_layout.addWidget(self.lbl_conn_status, 1, 1)

        info_frame.setLayout(info_layout)
        conn_layout.addWidget(info_frame)

        # Connection buttons frame
        btn_frame = QFrame()
        btn_layout = QHBoxLayout()

        self.btn_connect = QPushButton("CONNECT TO SERVER")
        self.btn_connect.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 6px;
                border: 2px solid #219653;
                font-size: 11pt;
                min-width: 180px;
            }
            QPushButton:hover {
                background: #219653;
            }
            QPushButton:pressed {
                background: #1e874b;
            }
            QPushButton:disabled {
                background: #95a5a6;
                border-color: #7f8c8d;
            }
        """)
        self.btn_connect.clicked.connect(self.connect_to_a)
        btn_layout.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("DISCONNECT")
        self.btn_disconnect.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 6px;
                border: 2px solid #c0392b;
                font-size: 11pt;
                min-width: 150px;
            }
            QPushButton:hover {
                background: #c0392b;
            }
            QPushButton:pressed {
                background: #a93226;
            }
            QPushButton:disabled {
                background: #95a5a6;
                border-color: #7f8c8d;
            }
        """)
        self.btn_disconnect.clicked.connect(self.disconnect_from_a)
        self.btn_disconnect.setEnabled(False)
        btn_layout.addWidget(self.btn_disconnect)

        btn_frame.setLayout(btn_layout)
        conn_layout.addWidget(btn_frame)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # 3. STATUS PANEL - 2 cột
        status_group = QGroupBox("SYSTEM STATUS")
        status_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: 2px solid #2ecc71;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #2c3e50;
            }
        """)
        status_layout = QGridLayout()

        # Column 1: Statistics
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        stats_frame.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        stats_layout = QGridLayout()

        stats_layout.addWidget(QLabel("Uptime:"), 0, 0)
        self.lbl_uptime = QLabel("00:00:00")
        self.lbl_uptime.setStyleSheet("font-weight: bold; font-size: 12pt; color: #2980b9;")
        stats_layout.addWidget(self.lbl_uptime, 0, 1)

        stats_layout.addWidget(QLabel("Commands forwarded:"), 1, 0)
        self.lbl_cmd_forwarded = QLabel("0")
        self.lbl_cmd_forwarded.setStyleSheet("font-weight: bold; font-size: 12pt; color: #9b59b6;")
        stats_layout.addWidget(self.lbl_cmd_forwarded, 1, 1)

        stats_layout.addWidget(QLabel("Status updates:"), 2, 0)
        self.lbl_status_updates = QLabel("0")
        self.lbl_status_updates.setStyleSheet("font-weight: bold; font-size: 12pt; color: #e67e22;")
        stats_layout.addWidget(self.lbl_status_updates, 2, 1)

        stats_frame.setLayout(stats_layout)
        status_layout.addWidget(stats_frame, 0, 0)

        # Column 2: Sensor Data
        sensor_frame = QFrame()
        sensor_frame.setFrameShape(QFrame.StyledPanel)
        sensor_frame.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        sensor_layout = QGridLayout()

        sensor_layout.addWidget(QLabel("Temperature:"), 0, 0)
        self.lbl_temp = QLabel("--.-°C")
        self.lbl_temp.setStyleSheet("""
            font-weight: bold;
            font-size: 14pt;
            color: #e74c3c;
            padding: 8px 16px;
            border-radius: 6px;
            background: white;
            border: 2px solid #ffcdd2;
        """)
        sensor_layout.addWidget(self.lbl_temp, 0, 1)

        sensor_layout.addWidget(QLabel("Humidity:"), 1, 0)
        self.lbl_humi = QLabel("--.-%")
        self.lbl_humi.setStyleSheet("""
            font-weight: bold;
            font-size: 14pt;
            color: #3498db;
            padding: 8px 16px;
            border-radius: 6px;
            background: white;
            border: 2px solid #bbdefb;
        """)
        sensor_layout.addWidget(self.lbl_humi, 1, 1)

        sensor_frame.setLayout(sensor_layout)
        status_layout.addWidget(sensor_frame, 0, 1)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 4. DEVICE STATUS PANEL
        device_group = QGroupBox("DEVICE STATUS")
        device_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: 2px solid #9b59b6;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #2c3e50;
            }
        """)
        device_layout = QGridLayout()

        # Motor status
        motor_frame = QFrame()
        motor_frame.setFrameShape(QFrame.StyledPanel)
        motor_frame.setStyleSheet("""
            QFrame {
                background: #f3e5f5;
                border: 1px solid #ce93d8;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        motor_layout = QGridLayout()

        motor_layout.addWidget(QLabel("Position:"), 0, 0)
        self.lbl_position = QLabel("0 pulse")
        self.lbl_position.setStyleSheet("font-weight: bold; font-size: 12pt; color: #2c3e50;")
        motor_layout.addWidget(self.lbl_position, 0, 1)

        motor_layout.addWidget(QLabel("Speed:"), 1, 0)
        self.lbl_speed = QLabel("0 pps")
        self.lbl_speed.setStyleSheet("font-weight: bold; font-size: 12pt; color: #2c3e50;")
        motor_layout.addWidget(self.lbl_speed, 1, 1)

        motor_frame.setLayout(motor_layout)
        device_layout.addWidget(motor_frame, 0, 0)

        # Driver status
        driver_frame = QFrame()
        driver_frame.setFrameShape(QFrame.StyledPanel)
        driver_frame.setStyleSheet("""
            QFrame {
                background: #e8f4fd;
                border: 1px solid #90caf9;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        driver_layout = QGridLayout()

        driver_layout.addWidget(QLabel("Alarm:"), 0, 0)
        self.lbl_alarm = QLabel("NO")
        self.lbl_alarm.setStyleSheet("font-weight: bold; font-size: 12pt; color: #27ae60;")
        driver_layout.addWidget(self.lbl_alarm, 0, 1)

        driver_layout.addWidget(QLabel("In Position:"), 1, 0)
        self.lbl_inpos = QLabel("NO")
        self.lbl_inpos.setStyleSheet("font-weight: bold; font-size: 12pt; color: #e74c3c;")
        driver_layout.addWidget(self.lbl_inpos, 1, 1)

        driver_layout.addWidget(QLabel("Running:"), 2, 0)
        self.lbl_running = QLabel("NO")
        self.lbl_running.setStyleSheet("font-weight: bold; font-size: 12pt; color: #f39c12;")
        driver_layout.addWidget(self.lbl_running, 2, 1)

        driver_frame.setLayout(driver_layout)
        device_layout.addWidget(driver_frame, 0, 1)

        # Control status
        control_frame = QFrame()
        control_frame.setFrameShape(QFrame.StyledPanel)
        control_frame.setStyleSheet("""
            QFrame {
                background: #fff3e0;
                border: 1px solid #ffcc80;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        control_layout = QGridLayout()

        control_layout.addWidget(QLabel("STEP:"), 0, 0)
        self.lbl_step_state = QLabel("OFF")
        self.lbl_step_state.setStyleSheet("font-weight: bold; font-size: 12pt; color: #7f8c8d;")
        control_layout.addWidget(self.lbl_step_state, 0, 1)

        control_layout.addWidget(QLabel("JOG:"), 1, 0)
        self.lbl_jog_state = QLabel("OFF")
        self.lbl_jog_state.setStyleSheet("font-weight: bold; font-size: 12pt; color: #7f8c8d;")
        control_layout.addWidget(self.lbl_jog_state, 1, 1)

        control_frame.setLayout(control_layout)
        device_layout.addWidget(control_frame, 1, 0, 1, 2)

        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        # 5. MODE CONTROL
        mode_group = QGroupBox("OPERATION MODE")
        mode_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: 2px solid #f39c12;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #2c3e50;
            }
        """)
        mode_layout = QHBoxLayout()

        self.lbl_mode_status = QLabel("Current Mode: AUTO")
        self.lbl_mode_status.setStyleSheet("""
            font-weight: bold;
            font-size: 13pt;
            color: #27ae60;
            padding: 12px;
            border-radius: 6px;
            background: #e8f6f3;
            border: 2px solid #a3e4d7;
        """)
        mode_layout.addWidget(self.lbl_mode_status)

        self.btn_mode_auto = QPushButton("SWITCH TO AUTO")
        self.btn_mode_auto.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 6px;
                border: 2px solid #219653;
                font-size: 11pt;
            }
            QPushButton:hover {
                background: #219653;
            }
            QPushButton:pressed {
                background: #1e874b;
            }
        """)
        self.btn_mode_auto.clicked.connect(lambda: self.set_mode(0))
        mode_layout.addWidget(self.btn_mode_auto)

        self.btn_mode_manual = QPushButton("SWITCH TO MANUAL")
        self.btn_mode_manual.setStyleSheet("""
            QPushButton {
                background: #e67e22;
                color: white;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 6px;
                border: 2px solid #d35400;
                font-size: 11pt;
            }
            QPushButton:hover {
                background: #d35400;
            }
            QPushButton:pressed {
                background: #ba4a00;
            }
        """)
        self.btn_mode_manual.clicked.connect(lambda: self.set_mode(1))
        mode_layout.addWidget(self.btn_mode_manual)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # 6. MANUAL CONTROL PANEL
        control_group = QGroupBox("MANUAL CONTROL (Active in MANUAL mode only)")
        control_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: 2px solid #e74c3c;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #2c3e50;
            }
        """)
        control_layout = QVBoxLayout()

        # Warning message
        warning_label = QLabel("⚠️ These controls only work when Layer A is in MANUAL mode (HR8=1)")
        warning_label.setAlignment(Qt.AlignCenter)
        warning_label.setStyleSheet("""
            QLabel {
                background: #fff3cd;
                color: #856404;
                padding: 10px;
                border-radius: 5px;
                border: 1px solid #ffeaa7;
                font-weight: bold;
                font-size: 10pt;
            }
        """)
        control_layout.addWidget(warning_label)

        # Position control
        pos_frame = QFrame()
        pos_frame.setFrameShape(QFrame.StyledPanel)
        pos_frame.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        pos_layout = QGridLayout()

        pos_layout.addWidget(QLabel("Target Position:"), 0, 0)
        self.le_pos = QLineEdit("20000")
        self.le_pos.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                font-size: 11pt;
                border: 2px solid #bdc3c7;
                border-radius: 4px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """)
        pos_layout.addWidget(self.le_pos, 0, 1)

        pos_layout.addWidget(QLabel("Speed (pps):"), 0, 2)
        self.le_speed = QLineEdit("8000")
        self.le_speed.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                font-size: 11pt;
                border: 2px solid #bdc3c7;
                border-radius: 4px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """)
        pos_layout.addWidget(self.le_speed, 0, 3)

        self.btn_override = QPushButton("MOVE TO POSITION")
        self.btn_override.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                border: 2px solid #2980b9;
                font-size: 11pt;
            }
            QPushButton:hover {
                background: #2980b9;
            }
            QPushButton:pressed {
                background: #2471a3;
            }
            QPushButton:disabled {
                background: #bdc3c7;
                border-color: #95a5a6;
            }
        """)
        self.btn_override.clicked.connect(self.override_motor)
        pos_layout.addWidget(self.btn_override, 1, 0, 1, 4)

        pos_frame.setLayout(pos_layout)
        control_layout.addWidget(pos_frame)

        # Jog control
        jog_frame = QFrame()
        jog_frame.setFrameShape(QFrame.StyledPanel)
        jog_frame.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        jog_layout = QGridLayout()

        jog_layout.addWidget(QLabel("Jog Speed:"), 0, 0)
        self.le_jog_speed = QLineEdit("12000")
        self.le_jog_speed.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                font-size: 11pt;
                border: 2px solid #bdc3c7;
                border-radius: 4px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """)
        jog_layout.addWidget(self.le_jog_speed, 0, 1)

        self.btn_jog_ccw = QPushButton("◀ JOG CCW")
        self.btn_jog_ccw.setStyleSheet("""
            QPushButton {
                background: #9b59b6;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                border: 2px solid #8e44ad;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #8e44ad;
            }
            QPushButton:pressed {
                background: #7d3c98;
            }
            QPushButton:disabled {
                background: #bdc3c7;
                border-color: #95a5a6;
            }
        """)
        self.btn_jog_ccw.clicked.connect(lambda: self.jog_move(-1))
        jog_layout.addWidget(self.btn_jog_ccw, 0, 2)

        self.btn_jog_cw = QPushButton("JOG CW ▶")
        self.btn_jog_cw.setStyleSheet("""
            QPushButton {
                background: #9b59b6;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                border: 2px solid #8e44ad;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #8e44ad;
            }
            QPushButton:pressed {
                background: #7d3c98;
            }
            QPushButton:disabled {
                background: #bdc3c7;
                border-color: #95a5a6;
            }
        """)
        self.btn_jog_cw.clicked.connect(lambda: self.jog_move(1))
        jog_layout.addWidget(self.btn_jog_cw, 0, 3)

        jog_frame.setLayout(jog_layout)
        control_layout.addWidget(jog_frame)

        # Control buttons row 1
        btn_row1_frame = QFrame()
        btn_row1_layout = QHBoxLayout()

        self.btn_step_on = QPushButton("STEP ON")
        self.btn_step_on.setStyleSheet("""
            QPushButton {
                background: #2ecc71;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                border: 2px solid #27ae60;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #27ae60;
            }
            QPushButton:pressed {
                background: #229954;
            }
            QPushButton:disabled {
                background: #bdc3c7;
                border-color: #95a5a6;
            }
        """)
        self.btn_step_on.clicked.connect(self.step_on)
        btn_row1_layout.addWidget(self.btn_step_on)

        self.btn_step_off = QPushButton("STEP OFF")
        self.btn_step_off.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                border: 2px solid #c0392b;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #c0392b;
            }
            QPushButton:pressed {
                background: #a93226;
            }
            QPushButton:disabled {
                background: #bdc3c7;
                border-color: #95a5a6;
            }
        """)
        self.btn_step_off.clicked.connect(self.step_off)
        btn_row1_layout.addWidget(self.btn_step_off)

        self.btn_reset_alarm = QPushButton("RESET ALARM")
        self.btn_reset_alarm.setStyleSheet("""
            QPushButton {
                background: #f39c12;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                border: 2px solid #d35400;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #d35400;
            }
            QPushButton:pressed {
                background: #ba4a00;
            }
            QPushButton:disabled {
                background: #bdc3c7;
                border-color: #95a5a6;
            }
        """)
        self.btn_reset_alarm.clicked.connect(self.reset_alarm)
        btn_row1_layout.addWidget(self.btn_reset_alarm)

        btn_row1_frame.setLayout(btn_row1_layout)
        control_layout.addWidget(btn_row1_frame)

        # Control buttons row 2
        btn_row2_frame = QFrame()
        btn_row2_layout = QHBoxLayout()

        self.btn_stop = QPushButton("STOP MOTOR")
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background: #e67e22;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                border: 2px solid #d35400;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #d35400;
            }
            QPushButton:pressed {
                background: #ba4a00;
            }
            QPushButton:disabled {
                background: #bdc3c7;
                border-color: #95a5a6;
            }
        """)
        self.btn_stop.clicked.connect(self.stop_motor)
        btn_row2_layout.addWidget(self.btn_stop)

        self.btn_release = QPushButton("RELEASE CONTROL")
        self.btn_release.setStyleSheet("""
            QPushButton {
                background: #95a5a6;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                border: 2px solid #7f8c8d;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #7f8c8d;
            }
            QPushButton:pressed {
                background: #6c7b7d;
            }
            QPushButton:disabled {
                background: #bdc3c7;
                border-color: #95a5a6;
            }
        """)
        self.btn_release.clicked.connect(self.release_control)
        btn_row2_layout.addWidget(self.btn_release)

        self.btn_emergency = QPushButton("⏹ EMERGENCY STOP")
        self.btn_emergency.setStyleSheet("""
            QPushButton {
                background: #c0392b;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                border: 2px solid #a93226;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #a93226;
            }
            QPushButton:pressed {
                background: #922b21;
            }
            QPushButton:disabled {
                background: #bdc3c7;
                border-color: #95a5a6;
            }
        """)
        self.btn_emergency.clicked.connect(self.emergency_stop)
        btn_row2_layout.addWidget(self.btn_emergency)

        btn_row2_frame.setLayout(btn_row2_layout)
        control_layout.addWidget(btn_row2_frame)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # 7. SENSOR CONTROL
        sensor_ctrl_frame = QFrame()
        sensor_ctrl_frame.setFrameShape(QFrame.StyledPanel)
        sensor_ctrl_frame.setStyleSheet("""
            QFrame {
                background: #e8f6f3;
                border: 2px solid #a3e4d7;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        sensor_ctrl_layout = QHBoxLayout()

        sensor_ctrl_layout.addWidget(QLabel("SHT20 Sensor:"))
        
        self.btn_toggle_sht20 = QPushButton("ENABLED")
        self.btn_toggle_sht20.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 6px;
                border: 2px solid #219653;
                font-size: 10pt;
                min-width: 120px;
            }
            QPushButton:hover {
                background: #219653;
            }
            QPushButton:pressed {
                background: #1e874b;
            }
        """)
        self.btn_toggle_sht20.clicked.connect(self.toggle_sht20)
        sensor_ctrl_layout.addWidget(self.btn_toggle_sht20)

        sensor_ctrl_layout.addStretch()
        sensor_ctrl_frame.setLayout(sensor_ctrl_layout)
        layout.addWidget(sensor_ctrl_frame)

        # 8. EVENT LOG
        log_group = QGroupBox("EVENT LOG")
        log_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: 2px solid #34495e;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #2c3e50;
            }
        """)
        log_layout = QVBoxLayout()

        log_toolbar = QFrame()
        log_toolbar_layout = QHBoxLayout()

        clear_btn = QPushButton("CLEAR LOG")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #95a5a6;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #7f8c8d;
                font-size: 9pt;
            }
            QPushButton:hover {
                background: #7f8c8d;
            }
        """)
        log_toolbar_layout.addWidget(clear_btn)

        export_btn = QPushButton("EXPORT TO FILE")
        export_btn.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #2980b9;
                font-size: 9pt;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        log_toolbar_layout.addWidget(export_btn)

        log_toolbar_layout.addStretch()
        
        self.lbl_log_count = QLabel("Lines: 0 / 500")
        self.lbl_log_count.setStyleSheet("color: #7f8c8d; font-size: 9pt;")
        log_toolbar_layout.addWidget(self.lbl_log_count)

        log_toolbar.setLayout(log_toolbar_layout)
        log_layout.addWidget(log_toolbar)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet("""
            QPlainTextEdit {
                background: #2c3e50;
                color: #ecf0f1;
                font-family: 'Consolas', 'Monaco', 'Courier New';
                font-size: 9pt;
                border-radius: 6px;
                border: 1px solid #34495e;
                padding: 5px;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        # Connect buttons after log_text is created
        clear_btn.clicked.connect(self.log_text.clear)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        self.log("SCADA Supervisor initialized")
        self.log(f"Layer A: {A_HOST}:{A_MODBUS_PORT}")
        self.log(f"Layer C server: port {SERVER_PORT}")

    def _setup_connections(self):
        """Connect signals from modbus client and TCP server"""
        self.modbus_client.signals.status_update.connect(self._handle_status_update)
        self.modbus_client.signals.connection_signal.connect(self.update_connection_status)
        self.modbus_client.signals.log_signal.connect(self.append_log)
        
        self.tcp_server.signals.forward_signal.connect(self.show_forward_animation)
        self.tcp_server.signals.log_signal.connect(self.append_log)
        self.tcp_server.signals.connection_signal.connect(self.update_connection_status)
        self.tcp_server.command_received.connect(self._handle_command_from_c)

    def _handle_status_update(self, data):
        """Update local state from modbus data"""
        self.current_position = data['position']
        self.current_speed = data['speed']
        # Chỉ cập nhật nhiệt độ, độ ẩm nếu SHT20 enabled
        if self.sht20_enabled:
            self.temperature = data['temperature']
            self.humidity = data['humidity']
        self.driver_alarm = data['driver_alarm']
        self.driver_inpos = data['driver_inpos']
        self.driver_running = data['driver_running']
        self.auto_state_code = data['auto_state_code']
        self.current_mode = data['mode']
        self.step_enabled = data['step_enabled']
        self.jog_state = data['jog_state']
        
        self.status_updates += 1
        self.signals.status_update.emit({})

    def _handle_command_from_c(self, command):
        """Handle commands received from Layer C"""
        self.commands_from_c += 1
        self.modbus_client.execute_command(command, from_c=True)
        self.signals.forward_signal.emit(command.get('type', 'unknown'))

    def connect_to_a(self):
        """Kết nối đến Layer A"""
        if self.modbus_client.connect():
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.log("Connecting to Layer A...")
        else:
            QMessageBox.warning(self, "Connection Error", "Failed to connect to Layer A\nCheck server address and port.")

    def disconnect_from_a(self):
        """Ngắt kết nối từ Layer A"""
        self.modbus_client.disconnect()
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.log("Disconnected from Layer A")

    def start_server_for_c(self):
        """Khởi động server cho Layer C"""
        # Server already started automatically in __init__
        self.log(f"TCP Server for Layer C started on port {SERVER_PORT}")

    def stop_server_for_c(self):
        """Dừng server cho Layer C"""
        self.tcp_server.stop()
        self.log("TCP Server for Layer C stopped")

    def set_mode(self, mode: int):
        """Đặt chế độ cho Layer A"""
        self.modbus_client.set_mode(mode)
        if mode == 0:
            self.lbl_mode_status.setText("Current Mode: AUTO")
            self.lbl_mode_status.setStyleSheet("""
                font-weight: bold;
                font-size: 13pt;
                color: #27ae60;
                padding: 12px;
                border-radius: 6px;
                background: #e8f6f3;
                border: 2px solid #a3e4d7;
            """)
            self.log("Layer A mode set to AUTO")
        else:
            self.lbl_mode_status.setText("Current Mode: MANUAL")
            self.lbl_mode_status.setStyleSheet("""
                font-weight: bold;
                font-size: 13pt;
                color: #e67e22;
                padding: 12px;
                border-radius: 6px;
                background: #fef9e7;
                border: 2px solid #f8c471;
            """)
            self.log("Layer A mode set to MANUAL")

    def _ensure_manual_mode(self) -> bool:
        """Kiểm tra nếu Layer A đang ở chế độ MANUAL"""
        if not self.modbus_client.modbus_connected:
            QMessageBox.warning(self, "Connection Error", "Not connected to Layer A")
            return False
            
        if self.current_mode != 1:
            QMessageBox.warning(
                self, "Mode Error",
                "Layer A is in AUTO mode.\nSwitch to MANUAL mode before manual control."
            )
            return False
        return True

    # Control Methods
    def override_motor(self):
        if not self._ensure_manual_mode():
            return
        try:
            pos = int(self.le_pos.text())
            speed = int(self.le_speed.text())

            if not validate_pos_speed(pos, speed):
                QMessageBox.warning(self, "Validation Error", 
                    "Position must be between -2,000,000,000 and 2,000,000,000\n"
                    "Speed must be between 1 and 200,000 pps")
                return

            command = {
                'type': 'motor_control',
                'priority': 2,
                'source': 'Layer_B',
                'timestamp': time.time(),
                'data': {
                    'position': pos,
                    'speed': speed
                }
            }
            self.modbus_client.execute_command(command, from_c=False)
            self.log(f"Move to position: {pos:,} @ {speed:,} pps")
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Invalid position or speed value!")

    def jog_move(self, direction):
        if not self._ensure_manual_mode():
            return
        try:
            speed = int(self.le_jog_speed.text())

            if speed < 1 or speed > 200_000:
                QMessageBox.warning(self, "Validation Error", "Speed must be between 1 and 200,000 pps")
                return

            command = {
                'type': 'jog_control',
                'priority': 2,
                'source': 'Layer_B',
                'timestamp': time.time(),
                'data': {
                    'speed': speed,
                    'direction': direction
                }
            }
            self.modbus_client.execute_command(command, from_c=False)
            dir_str = "CW" if direction > 0 else "CCW"
            self.log(f"Jog {dir_str} @ {speed:,} pps")
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Invalid speed value!")

    def step_on(self):
        if not self._ensure_manual_mode():
            return
        command = {
            'type': 'motor_control',
            'priority': 2,
            'source': 'Layer_B',
            'timestamp': time.time(),
            'data': {
                'step_command': 'on'
            }
        }
        self.modbus_client.execute_command(command, from_c=False)
        self.log("STEP ON command sent")

    def step_off(self):
        if not self._ensure_manual_mode():
            return
        command = {
            'type': 'motor_control',
            'priority': 2,
            'source': 'Layer_B',
            'timestamp': time.time(),
            'data': {
                'step_command': 'off'
            }
        }
        self.modbus_client.execute_command(command, from_c=False)
        self.log("STEP OFF command sent")

    def reset_alarm(self):
        if not self._ensure_manual_mode():
            return
        command = {
            'type': 'motor_control',
            'priority': 2,
            'source': 'Layer_B',
            'timestamp': time.time(),
            'data': {
                'alarm_reset': True
            }
        }
        self.modbus_client.execute_command(command, from_c=False)
        self.log("ALARM RESET command sent")

    def stop_motor(self):
        if not self._ensure_manual_mode():
            return
        command = {
            'type': 'stop_motor',
            'priority': 2,
            'source': 'Layer_B',
            'timestamp': time.time()
        }
        self.modbus_client.execute_command(command, from_c=False)
        self.log("STOP MOTOR command sent")

    def release_control(self):
        if not self._ensure_manual_mode():
            return
        command = {
            'type': 'release_control',
            'priority': 2,
            'source': 'Layer_B',
            'timestamp': time.time()
        }
        self.modbus_client.execute_command(command, from_c=False)
        self.log("RELEASE CONTROL command sent")

    def emergency_stop(self):
        if not self._ensure_manual_mode():
            return
        reply = QMessageBox.question(
            self, 'Emergency Stop Confirmation',
            'Are you sure you want to execute EMERGENCY STOP?\n'
            'This will immediately stop all motor operations.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            command = {
                'type': 'emergency_stop',
                'priority': 2,
                'source': 'Layer_B',
                'timestamp': time.time()
            }
            self.modbus_client.execute_command(command, from_c=False)
            self.log("EMERGENCY STOP executed")

    def toggle_sht20(self):
        self.sht20_enabled = not self.sht20_enabled
        if self.sht20_enabled:
            self.btn_toggle_sht20.setText("ENABLED")
            self.btn_toggle_sht20.setStyleSheet("""
                QPushButton {
                    background: #27ae60;
                    color: white;
                    font-weight: bold;
                    padding: 8px 20px;
                    border-radius: 6px;
                    border: 2px solid #219653;
                    font-size: 10pt;
                }
                QPushButton:hover {
                    background: #219653;
                }
                QPushButton:pressed {
                    background: #1e874b;
                }
            """)
            self.log("SHT20 sensor enabled")
        else:
            self.btn_toggle_sht20.setText("DISABLED")
            self.btn_toggle_sht20.setStyleSheet("""
                QPushButton {
                    background: #e74c3c;
                    color: white;
                    font-weight: bold;
                    padding: 8px 20px;
                    border-radius: 6px;
                    border: 2px solid #c0392b;
                    font-size: 10pt;
                }
                QPushButton:hover {
                    background: #c0392b;
                }
                QPushButton:pressed {
                    background: #a93226;
                }
            """)
            self.log("SHT20 sensor disabled")

    # UI Update Methods
    def update_displays(self, data):
        # Update temperature and humidity
        if self.sht20_enabled:
            self.lbl_temp.setText(f"{self.temperature:.1f}°C")
            self.lbl_humi.setText(f"{self.humidity:.1f}%")
        else:
            self.lbl_temp.setText("--.-°C")
            self.lbl_humi.setText("--.-%")

        # Update motor position and speed
        self.lbl_position.setText(f"{self.current_position:,} pulse")
        self.lbl_speed.setText(f"{self.current_speed:,} pps")

        # Update driver status
        if self.driver_alarm:
            self.lbl_alarm.setText("YES")
            self.lbl_alarm.setStyleSheet("font-weight: bold; font-size: 12pt; color: #e74c3c;")
        else:
            self.lbl_alarm.setText("NO")
            self.lbl_alarm.setStyleSheet("font-weight: bold; font-size: 12pt; color: #27ae60;")

        if self.driver_inpos:
            self.lbl_inpos.setText("YES")
            self.lbl_inpos.setStyleSheet("font-weight: bold; font-size: 12pt; color: #27ae60;")
        else:
            self.lbl_inpos.setText("NO")
            self.lbl_inpos.setStyleSheet("font-weight: bold; font-size: 12pt; color: #e74c3c;")

        if self.driver_running:
            self.lbl_running.setText("YES")
            self.lbl_running.setStyleSheet("font-weight: bold; font-size: 12pt; color: #f39c12;")
        else:
            self.lbl_running.setText("NO")
            self.lbl_running.setStyleSheet("font-weight: bold; font-size: 12pt; color: #95a5a6;")

        # Update STEP state
        if self.step_enabled:
            self.lbl_step_state.setText("ON")
            self.lbl_step_state.setStyleSheet("font-weight: bold; font-size: 12pt; color: #27ae60;")
        else:
            self.lbl_step_state.setText("OFF")
            self.lbl_step_state.setStyleSheet("font-weight: bold; font-size: 12pt; color: #7f8c8d;")

        # Update JOG state
        if self.jog_state == 1:
            self.lbl_jog_state.setText("CW")
            self.lbl_jog_state.setStyleSheet("font-weight: bold; font-size: 12pt; color: #3498db;")
        elif self.jog_state == 2:
            self.lbl_jog_state.setText("CCW")
            self.lbl_jog_state.setStyleSheet("font-weight: bold; font-size: 12pt; color: #9b59b6;")
        else:
            self.lbl_jog_state.setText("OFF")
            self.lbl_jog_state.setStyleSheet("font-weight: bold; font-size: 12pt; color: #7f8c8d;")

        # Update mode display
        if self.current_mode == 1:
            self.lbl_mode_status.setText("Current Mode: MANUAL")
            self.lbl_mode_status.setStyleSheet("""
                font-weight: bold;
                font-size: 13pt;
                color: #e67e22;
                padding: 12px;
                border-radius: 6px;
                background: #fef9e7;
                border: 2px solid #f8c471;
            """)
        else:
            self.lbl_mode_status.setText("Current Mode: AUTO")
            self.lbl_mode_status.setStyleSheet("""
                font-weight: bold;
                font-size: 13pt;
                color: #27ae60;
                padding: 12px;
                border-radius: 6px;
                background: #e8f6f3;
                border: 2px solid #a3e4d7;
            """)

    def update_connection_status(self, target, status):
        if target == "a":
            if "Connected" in status:
                self.lbl_conn_status.setText("CONNECTED")
                self.lbl_conn_status.setStyleSheet("""
                    font-weight: bold;
                    font-size: 11pt;
                    color: #27ae60;
                    padding: 4px 12px;
                    border-radius: 4px;
                    background: #d4edda;
                """)
                # Enable control buttons when connected
                self._update_control_buttons_state(True)
            elif "Disconnected" in status:
                self.lbl_conn_status.setText("DISCONNECTED")
                self.lbl_conn_status.setStyleSheet("""
                    font-weight: bold;
                    font-size: 11pt;
                    color: #e74c3c;
                    padding: 4px 12px;
                    border-radius: 4px;
                    background: #ffebee;
                """)
                # Disable control buttons when disconnected
                self._update_control_buttons_state(False)

    def _update_control_buttons_state(self, enabled):
        """Cập nhật trạng thái của các nút điều khiển"""
        self.btn_override.setEnabled(enabled)
        self.btn_jog_ccw.setEnabled(enabled)
        self.btn_jog_cw.setEnabled(enabled)
        self.btn_step_on.setEnabled(enabled)
        self.btn_step_off.setEnabled(enabled)
        self.btn_reset_alarm.setEnabled(enabled)
        self.btn_stop.setEnabled(enabled)
        self.btn_release.setEnabled(enabled)
        self.btn_emergency.setEnabled(enabled)
        self.btn_mode_auto.setEnabled(enabled)
        self.btn_mode_manual.setEnabled(enabled)

    def show_forward_animation(self, cmd_type):
        # Có thể thêm hiệu ứng animation ở đây
        pass

    def update_statistics(self):
        # Update uptime
        uptime = int(time.time() - self.start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60
        self.lbl_uptime.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # Update command count
        self.lbl_cmd_forwarded.setText(str(self.modbus_client.commands_forwarded))
        
        # Update log count
        line_count = self.log_text.document().blockCount()
        self.lbl_log_count.setText(f"Lines: {line_count} / 500")

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        if self.log_text.document().blockCount() > 500:
            self.log_text.clear()
        self.log_text.appendPlainText(f"[{timestamp}] {message}")

    def append_log(self, message):
        self.log(message)

    def closeEvent(self, event):
        self.modbus_client.disconnect()
        self.tcp_server.stop()
        self.stats_timer.stop()
        event.accept()