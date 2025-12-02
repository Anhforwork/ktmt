import time
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QLabel, QHBoxLayout,
    QLineEdit, QMessageBox, QGroupBox, QGridLayout, QFrame,
    QScrollArea, QPlainTextEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from modbus_client import ModbusClientA
from tcp_server import TCPServerForC
from utils import SignalEmitter, AUTO_STATE_MAP, validate_pos_speed


class LayerB_SCADASupervisor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAYER B - SCADA SUPERVISOR (Priority 2)")
        self.setGeometry(100, 100, 1200, 800)

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
        self.commands_forwarded = 0
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

        # Start polling
        self.modbus_client.start_polling()
        
        # Stats update timer
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_statistics)
        self.stats_timer.start(1000)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # 1. MAIN STATUS BAR
        self.status_bar_frame = QFrame()
        self.status_bar_frame.setFrameShape(QFrame.Box)
        self.status_bar_frame.setLineWidth(2)
        self.status_bar_frame.setStyleSheet("border: 2px solid #d0d0d0;")
        status_bar_layout = QVBoxLayout()

        self.lbl_main_status = QLabel("SCADA SUPERVISOR - MONITOR & CONTROL")
        self.lbl_main_status.setAlignment(Qt.AlignCenter)
        self.lbl_main_status.setStyleSheet("""
            background: #e0e0e0;
            color: #333333;
            padding: 20px;
            font-size: 18pt;
            font-weight: bold;
            border-radius: 10px;
        """)
        status_bar_layout.addWidget(self.lbl_main_status)

        self.status_bar_frame.setLayout(status_bar_layout)
        layout.addWidget(self.status_bar_frame)

        # 2. NETWORK TOPOLOGY
        topology_group = QGroupBox("NETWORK TOPOLOGY & STATUS")
        topology_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
            }
        """)
        topology_layout = QVBoxLayout()

        conn_frame = QFrame()
        conn_frame.setFrameShape(QFrame.StyledPanel)
        conn_frame.setStyleSheet("background: #f5f5f5; border-radius: 5px;")
        conn_layout = QGridLayout()

        conn_layout.addWidget(QLabel("Connection to Layer A (Modbus TCP):"), 0, 0)
        self.lbl_conn_a = QLabel("Connecting...")
        self.lbl_conn_a.setStyleSheet("font-weight: bold; font-size: 11pt; color: #e67e22;")
        conn_layout.addWidget(self.lbl_conn_a, 0, 1)

        topology_layout.addWidget(conn_frame)
        topology_group.setLayout(topology_layout)
        layout.addWidget(topology_group)

        # 3. SYSTEM HEALTH
        health_group = QGroupBox("SYSTEM HEALTH & STATISTICS")
        health_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
            }
        """)
        health_layout = QGridLayout()

        health_layout.addWidget(QLabel("Uptime:"), 0, 0)
        self.lbl_uptime = QLabel("00:00:00")
        self.lbl_uptime.setStyleSheet("font-weight: bold; font-size: 11pt; color: #27ae60;")
        health_layout.addWidget(self.lbl_uptime, 0, 1)

        health_layout.addWidget(QLabel("Commands forwarded to A:"), 1, 0)
        self.lbl_cmd_forwarded = QLabel("0")
        self.lbl_cmd_forwarded.setStyleSheet("font-weight: bold; font-size: 11pt; color: #9b59b6;")
        health_layout.addWidget(self.lbl_cmd_forwarded, 1, 1)

        health_layout.addWidget(QLabel("Status updates from A:"), 1, 2)
        self.lbl_status_updates = QLabel("0")
        self.lbl_status_updates.setStyleSheet("font-weight: bold; font-size: 11pt; color: #e67e22;")
        health_layout.addWidget(self.lbl_status_updates, 1, 3)

        health_group.setLayout(health_layout)
        layout.addWidget(health_group)

        # 4. MODE CONTROL
        mode_group = QGroupBox("MODE CONTROL (Layer A AUTO / MANUAL)")
        mode_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
            }
        """)
        mode_layout = QHBoxLayout()

        self.lbl_mode_status = QLabel("Mode: AUTO")
        self.lbl_mode_status.setStyleSheet("font-weight: bold; font-size: 11pt; color: #27ae60;")
        mode_layout.addWidget(self.lbl_mode_status)

        self.btn_mode_auto = QPushButton("A → AUTO")
        self.btn_mode_auto.setStyleSheet("""
            background: #e0e0e0;
            color: #333333;
            font-weight: bold;
            padding: 6px;
            border: 1px solid #c0c0c0;
            border-radius: 4px;
        """)
        self.btn_mode_auto.clicked.connect(lambda: self.set_mode(0))
        mode_layout.addWidget(self.btn_mode_auto)

        self.btn_mode_manual = QPushButton("A → MANUAL")
        self.btn_mode_manual.setStyleSheet("""
            background: #f0f0f0;
            color: #333333;
            font-weight: bold;
            padding: 6px;
            border: 1px solid #c0c0c0;
            border-radius: 4px;
        """)
        self.btn_mode_manual.clicked.connect(lambda: self.set_mode(1))
        mode_layout.addWidget(self.btn_mode_manual)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # 5. REAL-TIME DATA FROM A
        data_group = QGroupBox("REAL-TIME DEVICE DATA FROM LAYER A")
        data_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
            }
        """)
        data_layout = QVBoxLayout()

        sensor_frame = QFrame()
        sensor_frame.setFrameShape(QFrame.StyledPanel)
        sensor_frame.setStyleSheet("background: #f5f5f5; border-radius: 5px;")
        sensor_layout = QHBoxLayout()

        self.lbl_temp = QLabel("--°C")
        self.lbl_temp.setAlignment(Qt.AlignCenter)
        self.lbl_temp.setStyleSheet("""
            background: #ffffff;
            color: #333333;
            font-size: 16pt;
            font-weight: bold;
            padding: 12px;
            border-radius: 8px;
            min-width: 140px;
            border: 1px solid #cccccc;
        """)
        sensor_layout.addWidget(self.lbl_temp)

        self.lbl_humi = QLabel("--%")
        self.lbl_humi.setAlignment(Qt.AlignCenter)
        self.lbl_humi.setStyleSheet("""
            background: #ffffff;
            color: #333333;
            font-size: 16pt;
            font-weight: bold;
            padding: 12px;
            border-radius: 8px;
            min-width: 140px;
            border: 1px solid #cccccc;
        """)
        sensor_layout.addWidget(self.lbl_humi)

        sensor_frame.setLayout(sensor_layout)
        data_layout.addWidget(sensor_frame)

        driver_frame = QFrame()
        driver_frame.setFrameShape(QFrame.StyledPanel)
        driver_frame.setStyleSheet("background: #f5f5f5; border-radius: 5px; padding: 8px;")
        driver_layout = QGridLayout()

        self.lbl_position = QLabel("Position: -- pulse")
        self.lbl_position.setStyleSheet("font-size: 13pt; font-weight: bold; color: #2c3e50;")
        driver_layout.addWidget(self.lbl_position, 0, 0)

        self.lbl_speed = QLabel("Speed: -- pps")
        self.lbl_speed.setStyleSheet("font-size: 13pt; font-weight: bold; color: #2c3e50;")
        driver_layout.addWidget(self.lbl_speed, 0, 1)

        self.lbl_alarm = QLabel("Alarm: --")
        self.lbl_alarm.setStyleSheet("font-size: 11pt; font-weight: bold;")
        driver_layout.addWidget(self.lbl_alarm, 1, 0)

        self.lbl_inpos = QLabel("InPos: --")
        self.lbl_inpos.setStyleSheet("font-size: 11pt; font-weight: bold;")
        driver_layout.addWidget(self.lbl_inpos, 1, 1)

        self.lbl_running = QLabel("Running: --")
        self.lbl_running.setStyleSheet("font-size: 11pt; font-weight: bold;")
        driver_layout.addWidget(self.lbl_running, 1, 2)

        self.lbl_step_state = QLabel("STEP: --")
        self.lbl_step_state.setStyleSheet("font-size: 11pt; font-weight: bold; color: #95a5a6;")
        driver_layout.addWidget(self.lbl_step_state, 2, 0)

        self.lbl_jog_state = QLabel("JOG: --")
        self.lbl_jog_state.setStyleSheet("font-size: 11pt; font-weight: bold; color: #95a5a6;")
        driver_layout.addWidget(self.lbl_jog_state, 2, 1)

        driver_frame.setLayout(driver_layout)
        data_layout.addWidget(driver_frame)

        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

        # 6. SHT20 TOGGLE
        toggle_frame = QFrame()
        toggle_frame.setFrameShape(QFrame.StyledPanel)
        toggle_layout = QHBoxLayout()

        self.btn_toggle_sht20 = QPushButton("SHT20: ON")
        self.btn_toggle_sht20.setStyleSheet("""
            background: #27ae60;
            color: white;
            font-weight: bold;
            padding: 6px;
            border-radius: 4px;
        """)
        self.btn_toggle_sht20.clicked.connect(self.toggle_sht20)

        toggle_layout.addWidget(self.btn_toggle_sht20)
        toggle_frame.setLayout(toggle_layout)
        layout.addWidget(toggle_frame)

        # 7. MANUAL OVERRIDE CONTROL
        control_group = QGroupBox("LAYER B MANUAL OVERRIDE (via Modbus → Layer A)")
        control_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
            }
        """)
        control_layout = QVBoxLayout()

        info_label = QLabel("Các lệnh này chỉ hoạt động khi Layer A đang ở MANUAL (HR8=1).")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("""
            background: #f5f5f5;
            color: #555555;
            padding: 8px;
            border-radius: 5px;
            font-weight: bold;
        """)
        control_layout.addWidget(info_label)

        pos_frame = QFrame()
        pos_frame.setFrameShape(QFrame.StyledPanel)
        pos_layout = QGridLayout()

        pos_layout.addWidget(QLabel("Position:"), 0, 0)
        self.le_pos = QLineEdit("20000")
        self.le_pos.setStyleSheet("padding: 5px; font-size: 10pt;")
        pos_layout.addWidget(self.le_pos, 0, 1)

        pos_layout.addWidget(QLabel("Speed:"), 0, 2)
        self.le_speed = QLineEdit("8000")
        self.le_speed.setStyleSheet("padding: 5px; font-size: 10pt;")
        pos_layout.addWidget(self.le_speed, 0, 3)

        self.btn_override = QPushButton("OVERRIDE MOVE ABS")
        self.btn_override.setStyleSheet("""
            background: #e0e0e0;
            color: #333333;
            font-weight: bold;
            padding: 10px;
            font-size: 11pt;
            border-radius: 5px;
            border: 1px solid #c0c0c0;
        """)
        self.btn_override.clicked.connect(self.override_motor)
        pos_layout.addWidget(self.btn_override, 1, 0, 1, 4)

        pos_frame.setLayout(pos_layout)
        control_layout.addWidget(pos_frame)

        jog_frame = QFrame()
        jog_frame.setFrameShape(QFrame.StyledPanel)
        jog_layout = QHBoxLayout()

        jog_layout.addWidget(QLabel("JOG Speed:"))
        self.le_jog_speed = QLineEdit("12000")
        self.le_jog_speed.setStyleSheet("padding: 5px; font-size: 10pt;")
        jog_layout.addWidget(self.le_jog_speed)

        self.btn_jog_ccw = QPushButton("JOG CCW")
        self.btn_jog_ccw.setStyleSheet("""
            background: #e0e0e0;
            color: #333333;
            font-weight: bold;
            padding: 8px;
            border: 1px solid #c0c0c0;
            border-radius: 4px;
        """)
        self.btn_jog_ccw.clicked.connect(lambda: self.jog_move(-1))
        jog_layout.addWidget(self.btn_jog_ccw)

        self.btn_jog_cw = QPushButton("JOG CW")
        self.btn_jog_cw.setStyleSheet("""
            background: #e0e0e0;
            color: #333333;
            font-weight: bold;
            padding: 8px;
            border: 1px solid #c0c0c0;
            border-radius: 4px;
        """)
        self.btn_jog_cw.clicked.connect(lambda: self.jog_move(1))
        jog_layout.addWidget(self.btn_jog_cw)

        jog_frame.setLayout(jog_layout)
        control_layout.addWidget(jog_frame)

        step_frame = QFrame()
        step_frame.setFrameShape(QFrame.StyledPanel)
        step_layout = QHBoxLayout()

        self.btn_step_on = QPushButton("STEP ON")
        self.btn_step_on.setStyleSheet("""
            background: #e0e0e0;
            color: #333333;
            font-weight: bold;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #c0c0c0;
        """)
        self.btn_step_on.clicked.connect(self.step_on)
        step_layout.addWidget(self.btn_step_on)

        self.btn_step_off = QPushButton("STEP OFF")
        self.btn_step_off.setStyleSheet("""
            background: #f0f0f0;
            color: #333333;
            font-weight: bold;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #c0c0c0;
        """)
        self.btn_step_off.clicked.connect(self.step_off)
        step_layout.addWidget(self.btn_step_off)

        self.btn_reset_alarm = QPushButton("RESET ALARM")
        self.btn_reset_alarm.setStyleSheet("""
            background: #f0f0f0;
            color: #333333;
            font-weight: bold;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #c0c0c0;
        """)
        self.btn_reset_alarm.clicked.connect(self.reset_alarm)
        step_layout.addWidget(self.btn_reset_alarm)

        step_frame.setLayout(step_layout)
        control_layout.addWidget(step_frame)

        btn_frame = QFrame()
        btn_frame.setFrameShape(QFrame.StyledPanel)
        btn_layout = QHBoxLayout()

        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setStyleSheet("""
            background: #e0e0e0;
            color: #333333;
            font-weight: bold;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #c0c0c0;
        """)
        self.btn_stop.clicked.connect(self.stop_motor)
        btn_layout.addWidget(self.btn_stop)

        self.btn_release = QPushButton("RELEASE CONTROL → LOCAL")
        self.btn_release.setStyleSheet("""
            background: #e0e0e0;
            color: #333333;
            font-weight: bold;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #c0c0c0;
        """)
        self.btn_release.clicked.connect(self.release_control)
        btn_layout.addWidget(self.btn_release)

        self.btn_emergency = QPushButton("EMERGENCY")
        self.btn_emergency.setStyleSheet("""
            background: #d9534f;
            color: white;
            font-weight: bold;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #c9302c;
        """)
        self.btn_emergency.clicked.connect(self.emergency_stop)
        btn_layout.addWidget(self.btn_emergency)

        btn_frame.setLayout(btn_layout)
        control_layout.addWidget(btn_frame)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # 8. LOG
        log_group = QGroupBox("System Log")
        log_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
            }
        """)
        log_layout = QVBoxLayout()

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(160)
        self.log_text.setStyleSheet("""
            background: #f5f5f5;
            color: #333333;
            font-family: 'Courier New';
            font-size: 9pt;
            border-radius: 5px;
            border: 1px solid #d0d0d0;
        """)
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        self.log("Layer B SCADA Supervisor initialized")

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

    def set_mode(self, mode: int):
        """Set Layer A mode: 0=AUTO, 1=MANUAL"""
        self.modbus_client.set_mode(mode)
        if mode == 0:
            self.lbl_mode_status.setText("Mode: AUTO")
            self.lbl_mode_status.setStyleSheet("font-weight: bold; font-size: 11pt; color: #27ae60;")
        else:
            self.lbl_mode_status.setText("Mode: MANUAL")
            self.lbl_mode_status.setStyleSheet("font-weight: bold; font-size: 11pt; color: #e67e22;")

    def _ensure_manual_mode(self) -> bool:
        """Check if Layer A is in MANUAL mode"""
        if self.current_mode != 1:
            QMessageBox.warning(
                self, "Mode error",
                "Layer A đang ở AUTO.\nHãy chuyển sang MANUAL trước khi điều khiển từ B."
            )
            return False
        return True

    # UI Control Methods
    def override_motor(self):
        if not self._ensure_manual_mode():
            return
        try:
            pos = int(self.le_pos.text())
            speed = int(self.le_speed.text())

            if not validate_pos_speed(pos, speed):
                QMessageBox.warning(self, "Error", "Invalid position or speed!")
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
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid input!")

    def jog_move(self, direction):
        if not self._ensure_manual_mode():
            return
        try:
            speed = int(self.le_jog_speed.text())

            if speed < 1 or speed > 200_000:
                QMessageBox.warning(self, "Error", "Speed out of range!")
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
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid speed!")

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

    def emergency_stop(self):
        if not self._ensure_manual_mode():
            return
        reply = QMessageBox.question(
            self, 'Emergency Stop',
            'EMERGENCY STOP system?',
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

    def toggle_sht20(self):
        self.sht20_enabled = not self.sht20_enabled
        if self.sht20_enabled:
            self.btn_toggle_sht20.setText("SHT20: ON")
            self.btn_toggle_sht20.setStyleSheet("""
                background: #27ae60;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 4px;
            """)
            self.log("SHT20 sensor reading ENABLED")
        else:
            self.btn_toggle_sht20.setText("SHT20: OFF")
            self.btn_toggle_sht20.setStyleSheet("""
                background: #c0392b;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 4px;
            """)
            self.log("SHT20 sensor reading DISABLED")

    # UI Update Methods
    def update_displays(self, data):
        self.lbl_temp.setText(f"{self.temperature:.1f}°C")
        self.lbl_humi.setText(f"{self.humidity:.1f}%")

        self.lbl_position.setText(f"Position: {self.current_position:,} pulse")
        self.lbl_speed.setText(f"Speed: {self.current_speed:,} pps")

        # Alarm display
        if self.driver_alarm:
            self.lbl_alarm.setText("Alarm: YES")
            self.lbl_alarm.setStyleSheet("font-size: 11pt; font-weight: bold; color: #c0392b;")
        else:
            self.lbl_alarm.setText("Alarm: NO")
            self.lbl_alarm.setStyleSheet("font-size: 11pt; font-weight: bold; color: #27ae60;")

        # InPos display
        if self.driver_inpos:
            self.lbl_inpos.setText("InPos: YES")
            self.lbl_inpos.setStyleSheet("font-size: 11pt; font-weight: bold; color: #27ae60;")
        else:
            self.lbl_inpos.setText("InPos: NO")
            self.lbl_inpos.setStyleSheet("font-size: 11pt; font-weight: bold; color: #f39c12;")

        # Running display
        if self.driver_running:
            self.lbl_running.setText("Running: YES")
            self.lbl_running.setStyleSheet("font-size: 11pt; font-weight: bold; color: #3498db;")
        else:
            self.lbl_running.setText("Running: NO")
            self.lbl_running.setStyleSheet("font-size: 11pt; font-weight: bold; color: #95a5a6;")

        # STEP state
        if self.step_enabled:
            self.lbl_step_state.setText("STEP: ON")
            self.lbl_step_state.setStyleSheet("font-size: 11pt; font-weight: bold; color: #27ae60;")
        else:
            self.lbl_step_state.setText("STEP: OFF")
            self.lbl_step_state.setStyleSheet("font-size: 11pt; font-weight: bold; color: #95a5a6;")

        # JOG state
        if self.jog_state == 1:
            self.lbl_jog_state.setText("JOG: CW")
            self.lbl_jog_state.setStyleSheet("font-size: 11pt; font-weight: bold; color: #3498db;")
        elif self.jog_state == 2:
            self.lbl_jog_state.setText("JOG: CCW")
            self.lbl_jog_state.setStyleSheet("font-size: 11pt; font-weight: bold; color: #3498db;")
        else:
            self.lbl_jog_state.setText("JOG: OFF")
            self.lbl_jog_state.setStyleSheet("font-size: 11pt; font-weight: bold; color: #95a5a6;")

        # Mode display
        if self.current_mode == 1:
            self.lbl_mode_status.setText("Mode: MANUAL")
            self.lbl_mode_status.setStyleSheet("font-weight: bold; font-size: 11pt; color: #e67e22;")
        else:
            self.lbl_mode_status.setText("Mode: AUTO")
            self.lbl_mode_status.setStyleSheet("font-weight: bold; font-size: 11pt; color: #27ae60;")

    def update_connection_status(self, target, status):
        if target == "a":
            self.lbl_conn_a.setText(status)
            if "Connected" in status:
                color = "#27ae60"
            elif "Disconnected" in status:
                color = "#c0392b"
            else:
                color = "#e67e22"
            self.lbl_conn_a.setStyleSheet(f"font-weight: bold; font-size: 11pt; color: {color};")

    def show_forward_animation(self, cmd_type):
        # This method can be enhanced with animation if needed
        pass

    def update_statistics(self):
        uptime = int(time.time() - self.start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60
        self.lbl_uptime.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        self.lbl_cmd_forwarded.setText(str(self.modbus_client.commands_forwarded))
        self.lbl_status_updates.setText(str(self.status_updates))

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        if self.log_text.document().blockCount() > 500:
            self.log_text.clear()
        self.log_text.appendPlainText(f"[{timestamp}] {message}")

    def append_log(self, message):
        self.log(message)

    def closeEvent(self, event):
        self.modbus_client.stop()
        self.tcp_server.stop()
        self.stats_timer.stop()
        event.accept()