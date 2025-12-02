"""
Layer B SCADA Supervisor UI (PyQt5).

This file focuses on GUI and orchestration only:
- Receives status updates from ModbusService
- Receives commands from JsonTcpServer
- Executes allowed commands by writing to Layer A via ModbusService
- Forwards status to Layer C
"""
from __future__ import annotations

import time
from collections import deque
from typing import Dict, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QTabWidget, QPlainTextEdit, QMessageBox, QSpinBox, QFrame, QProgressBar
)

from config import AUTO_STATE_MAP, POS_MIN, POS_MAX, SPEED_MIN, SPEED_MAX, TARGET_MIN, TARGET_MAX
from modbus_service import ModbusService
from c_server import JsonTcpServer


def _chip(text: str, bg: str, fg: str = "white") -> str:
    return f"""
        QLabel {{
            padding: 6px 10px;
            border-radius: 999px;
            background: {bg};
            color: {fg};
            font-weight: 700;
        }}
    """


class LayerBMainWindow(QMainWindow):
    def __init__(self, modbus: ModbusService, server_c: JsonTcpServer) -> None:
        super().__init__()
        self.modbus = modbus
        self.server_c = server_c

        self.setWindowTitle("LAYER B - SCADA SUPERVISOR (Priority 2)")
        self.resize(1220, 820)

        # ---------- state ----------
        self.current_position = 0
        self.current_speed = 0
        self.temperature = 0.0
        self.humidity = 0.0
        self.driver_alarm = False
        self.driver_inpos = False
        self.driver_running = False

        self.counter_value = 0
        self.counter_target = 0
        self.auto_state_code = 0
        self.current_mode = 0  # 0=AUTO, 1=MANUAL

        self.step_enabled = False
        self.jog_state = 0

        self.sht20_enabled = True

        # statistics
        self.commands_forwarded = 0
        self.commands_from_c = 0
        self.status_updates = 0
        self.start_time = time.time()
        self.command_history = deque(maxlen=12)

        # ---------- UI ----------
        self._build_ui()
        self._wire_signals()

        # timer
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self._update_statistics)
        self.stats_timer.start(1000)

        self.log("Layer B SCADA Supervisor initialized")
        self.log("pyModbusTCP client ready (expecting pyModbusTCP==0.3.0)")

    # =========================================================
    # UI setup
    # =========================================================
    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # Top bar
        top = QFrame()
        top.setObjectName("TopBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(14, 12, 14, 12)

        title = QLabel("SCADA SUPERVISOR — Layer B")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        sub = QLabel("Monitor & Control: Layer A (Modbus TCP) ⇄ Layer B ⇄ Layer C (JSON/TCP)")
        sub.setStyleSheet("color: #6b7280;")

        title_col = QVBoxLayout()
        title_col.addWidget(title)
        title_col.addWidget(sub)

        top_layout.addLayout(title_col)
        top_layout.addStretch(1)

        self.chip_a = QLabel("A: Connecting...")
        self.chip_a.setStyleSheet(_chip(""," #f59e0b"))
        self.chip_c = QLabel("C: Waiting...")
        self.chip_c.setStyleSheet(_chip(""," #6b7280"))

        top_layout.addWidget(self.chip_a)
        top_layout.addWidget(self.chip_c)
        root_layout.addWidget(top)

        # Tabs
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        root_layout.addWidget(tabs, 1)

        self.tab_dashboard = QWidget()
        self.tab_control = QWidget()
        self.tab_logs = QWidget()
        tabs.addTab(self.tab_dashboard, "Dashboard")
        tabs.addTab(self.tab_control, "Control")
        tabs.addTab(self.tab_logs, "Logs")

        self._build_dashboard(self.tab_dashboard)
        self._build_control(self.tab_control)
        self._build_logs(self.tab_logs)

        # global style
        self.setStyleSheet("""
            QWidget { font-family: Segoe UI, Arial; font-size: 10.5pt; }
            QMainWindow { background: #f6f7fb; }
            #TopBar { background: white; border-radius: 14px; }
            QGroupBox {
                font-weight: 700;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
                margin-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                margin-left: 10px;
                color: #111827;
            }
            QPushButton {
                border-radius: 10px;
                padding: 8px 10px;
                font-weight: 700;
                background: #eef2ff;
                border: 1px solid #e5e7eb;
            }
            QPushButton:hover { background: #e0e7ff; }
            QPushButton:pressed { background: #c7d2fe; }
            QPushButton#Danger { background: #ef4444; color: white; border: 1px solid #dc2626; }
            QPushButton#Danger:hover { background: #dc2626; }
            QPlainTextEdit {
                background: #0b1020;
                color: #dbeafe;
                border-radius: 12px;
                border: 1px solid #111827;
                padding: 10px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 9.5pt;
            }
        """)

    def _build_dashboard(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Row 1: Live cards
        row1 = QHBoxLayout()
        layout.addLayout(row1)

        # Sensors
        g_sensors = QGroupBox("Sensors (SHT20)")
        g1 = QVBoxLayout(g_sensors)

        self.lbl_temp = QLabel("-- °C")
        self.lbl_temp.setAlignment(Qt.AlignCenter)
        self.lbl_temp.setStyleSheet("font-size: 22pt; font-weight: 800; padding: 18px;")
        self.lbl_humi = QLabel("-- %RH")
        self.lbl_humi.setAlignment(Qt.AlignCenter)
        self.lbl_humi.setStyleSheet("font-size: 22pt; font-weight: 800; padding: 18px;")

        btm = QHBoxLayout()
        self.btn_toggle_sht20 = QPushButton("SHT20: ON")
        self.btn_toggle_sht20.clicked.connect(self.toggle_sht20)
        btm.addWidget(self.btn_toggle_sht20)
        btm.addStretch(1)

        g1.addWidget(self.lbl_temp)
        g1.addWidget(self.lbl_humi)
        g1.addLayout(btm)
        row1.addWidget(g_sensors, 1)

        # Motor
        g_motor = QGroupBox("Motor / Driver")
        gm = QGridLayout(g_motor)
        gm.setHorizontalSpacing(14)
        gm.setVerticalSpacing(10)

        self.lbl_position = QLabel("Position: -- pulse")
        self.lbl_position.setStyleSheet("font-size: 13pt; font-weight: 800;")
        self.lbl_speed = QLabel("Speed: -- pps")
        self.lbl_speed.setStyleSheet("font-size: 13pt; font-weight: 800;")

        self.lbl_alarm = QLabel("Alarm: --")
        self.lbl_inpos = QLabel("InPos: --")
        self.lbl_running = QLabel("Running: --")
        self.lbl_step_state = QLabel("STEP: --")
        self.lbl_jog_state = QLabel("JOG: --")

        for lab in [self.lbl_alarm, self.lbl_inpos, self.lbl_running, self.lbl_step_state, self.lbl_jog_state]:
            lab.setStyleSheet("font-weight: 700; color: #374151;")

        gm.addWidget(self.lbl_position, 0, 0, 1, 2)
        gm.addWidget(self.lbl_speed, 0, 2, 1, 2)
        gm.addWidget(self.lbl_alarm, 1, 0)
        gm.addWidget(self.lbl_inpos, 1, 1)
        gm.addWidget(self.lbl_running, 1, 2)
        gm.addWidget(self.lbl_step_state, 2, 0)
        gm.addWidget(self.lbl_jog_state, 2, 1)

        row1.addWidget(g_motor, 2)

        # Row 2: Process + stats
        row2 = QHBoxLayout()
        layout.addLayout(row2)

        g_proc = QGroupBox("Process / Counter (from Layer A)")
        gp = QVBoxLayout(g_proc)

        top_line = QHBoxLayout()
        self.lbl_counter = QLabel("Counter: -- / --")
        self.lbl_counter.setStyleSheet("font-size: 14pt; font-weight: 800;")
        self.lbl_counter_done = QLabel("DONE: --")
        self.lbl_counter_done.setStyleSheet("font-weight: 800;")
        top_line.addWidget(self.lbl_counter)
        top_line.addStretch(1)
        top_line.addWidget(self.lbl_counter_done)
        gp.addLayout(top_line)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        gp.addWidget(self.progress)

        meta = QHBoxLayout()
        self.lbl_auto_state = QLabel("AUTO STATE: Unknown")
        self.lbl_mode_status = QLabel("Mode: AUTO")
        self.lbl_auto_state.setStyleSheet("font-weight: 800;")
        self.lbl_mode_status.setStyleSheet("font-weight: 800;")
        meta.addWidget(self.lbl_auto_state)
        meta.addStretch(1)
        meta.addWidget(self.lbl_mode_status)
        gp.addLayout(meta)

        # Forward indicator (used when receiving commands from C)
        self.lbl_forward_status = QLabel("Idle")
        self.lbl_forward_status.setAlignment(Qt.AlignCenter)
        self.lbl_forward_status.setStyleSheet("""
            background: #6b7280;
            color: white;
            font-size: 12pt;
            font-weight: 900;
            padding: 12px;
            border-radius: 12px;
        """)
        gp.addWidget(self.lbl_forward_status)

        row2.addWidget(g_proc, 2)

        g_stats = QGroupBox("System Health & Statistics")
        gs = QGridLayout(g_stats)
        gs.setVerticalSpacing(10)

        self.lbl_uptime = QLabel("00:00:00")
        self.lbl_cmd_forwarded = QLabel("0")
        self.lbl_cmd_from_c = QLabel("0")
        self.lbl_status_updates = QLabel("0")

        for w in [self.lbl_uptime, self.lbl_cmd_forwarded, self.lbl_cmd_from_c, self.lbl_status_updates]:
            w.setStyleSheet("font-weight: 900; font-size: 12pt;")

        gs.addWidget(QLabel("Uptime"), 0, 0)
        gs.addWidget(self.lbl_uptime, 0, 1)

        gs.addWidget(QLabel("Commands forwarded to A"), 1, 0)
        gs.addWidget(self.lbl_cmd_forwarded, 1, 1)

        gs.addWidget(QLabel("Commands from C"), 2, 0)
        gs.addWidget(self.lbl_cmd_from_c, 2, 1)

        gs.addWidget(QLabel("Status updates from A"), 3, 0)
        gs.addWidget(self.lbl_status_updates, 3, 1)

        row2.addWidget(g_stats, 1)

        layout.addStretch(1)

    def _build_control(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Mode control
        g_mode = QGroupBox("Mode Control (Layer A AUTO / MANUAL)")
        m = QHBoxLayout(g_mode)

        self.btn_mode_auto = QPushButton("A → AUTO")
        self.btn_mode_auto.clicked.connect(lambda: self.set_mode(0))
        self.btn_mode_manual = QPushButton("A → MANUAL")
        self.btn_mode_manual.clicked.connect(lambda: self.set_mode(1))

        self.lbl_mode_hint = QLabel("Manual commands require A in MANUAL (HR8=1).")
        self.lbl_mode_hint.setStyleSheet("color: #6b7280; font-weight: 700;")

        m.addWidget(self.btn_mode_auto)
        m.addWidget(self.btn_mode_manual)
        m.addStretch(1)
        m.addWidget(self.lbl_mode_hint)

        # Target count
        g_target = QGroupBox("Set Target Count (B → A → Counter)")
        t = QGridLayout(g_target)

        self.sp_target = QSpinBox()
        self.sp_target.setRange(TARGET_MIN, TARGET_MAX)
        self.sp_target.setValue(20)
        self.sp_target.setSingleStep(1)

        self.btn_set_target = QPushButton("SEND TARGET → A")
        self.btn_set_target.clicked.connect(self.set_counter_target)

        self.lbl_target_info = QLabel("Current target from A: --")
        self.lbl_target_info.setStyleSheet("color: #374151; font-weight: 700;")

        t.addWidget(QLabel("Target count:"), 0, 0)
        t.addWidget(self.sp_target, 0, 1)
        t.addWidget(self.btn_set_target, 0, 2)
        t.addWidget(self.lbl_target_info, 1, 0, 1, 3)

        # Manual override
        g_manual = QGroupBox("Layer B Manual Override (via Modbus → Layer A)")
        man = QVBoxLayout(g_manual)

        # Move abs
        move_box = QGroupBox("Move ABS")
        mv = QGridLayout(move_box)

        self.sp_pos = QSpinBox()
        self.sp_pos.setRange(POS_MIN, POS_MAX)
        self.sp_pos.setValue(20000)
        self.sp_pos.setSingleStep(1000)

        self.sp_speed = QSpinBox()
        self.sp_speed.setRange(SPEED_MIN, SPEED_MAX)
        self.sp_speed.setValue(8000)
        self.sp_speed.setSingleStep(500)

        self.btn_override = QPushButton("OVERRIDE MOVE ABS")
        self.btn_override.clicked.connect(self.override_motor)

        mv.addWidget(QLabel("Position (pulse)"), 0, 0)
        mv.addWidget(self.sp_pos, 0, 1)
        mv.addWidget(QLabel("Speed (pps)"), 0, 2)
        mv.addWidget(self.sp_speed, 0, 3)
        mv.addWidget(self.btn_override, 1, 0, 1, 4)

        # Jog
        jog_box = QGroupBox("Jog")
        jg = QHBoxLayout(jog_box)

        self.sp_jog_speed = QSpinBox()
        self.sp_jog_speed.setRange(SPEED_MIN, SPEED_MAX)
        self.sp_jog_speed.setValue(12000)
        self.sp_jog_speed.setSingleStep(500)

        self.btn_jog_ccw = QPushButton("JOG CCW")
        self.btn_jog_ccw.clicked.connect(lambda: self.jog_move(-1))
        self.btn_jog_cw = QPushButton("JOG CW")
        self.btn_jog_cw.clicked.connect(lambda: self.jog_move(1))

        jg.addWidget(QLabel("Speed (pps)"))
        jg.addWidget(self.sp_jog_speed)
        jg.addStretch(1)
        jg.addWidget(self.btn_jog_ccw)
        jg.addWidget(self.btn_jog_cw)

        # Quick control buttons
        quick = QGroupBox("Quick Actions")
        q = QHBoxLayout(quick)
        self.btn_step_on = QPushButton("STEP ON")
        self.btn_step_on.clicked.connect(self.step_on)
        self.btn_step_off = QPushButton("STEP OFF")
        self.btn_step_off.clicked.connect(self.step_off)
        self.btn_reset_alarm = QPushButton("RESET ALARM")
        self.btn_reset_alarm.clicked.connect(self.reset_alarm)

        self.btn_stop = QPushButton("STOP")
        self.btn_stop.clicked.connect(self.stop_motor)
        self.btn_release = QPushButton("RELEASE → LOCAL")
        self.btn_release.clicked.connect(self.release_control)
        self.btn_emergency = QPushButton("EMERGENCY")
        self.btn_emergency.setObjectName("Danger")
        self.btn_emergency.clicked.connect(self.emergency_stop)

        for b in [self.btn_step_on, self.btn_step_off, self.btn_reset_alarm, self.btn_stop, self.btn_release, self.btn_emergency]:
            q.addWidget(b)
        q.addStretch(1)

        man.addWidget(move_box)
        man.addWidget(jog_box)
        man.addWidget(quick)

        layout.addWidget(g_mode)
        layout.addWidget(g_target)
        layout.addWidget(g_manual)
        layout.addStretch(1)

    def _build_logs(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        g_log = QGroupBox("System Log")
        gl = QVBoxLayout(g_log)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        gl.addWidget(self.log_text)

        g_hist = QGroupBox("Command History (last 12)")
        gh = QVBoxLayout(g_hist)
        self.history_text = QPlainTextEdit()
        self.history_text.setReadOnly(True)
        gh.addWidget(self.history_text)

        layout.addWidget(g_log, 2)
        layout.addWidget(g_hist, 1)

    def _wire_signals(self) -> None:
        self.modbus.log.connect(self.log)
        self.modbus.connection_changed.connect(self._on_conn_a)
        self.modbus.status_updated.connect(self._on_status)

        self.server_c.log.connect(self.log)
        self.server_c.connection_changed.connect(self._on_conn_c)
        self.server_c.command_received.connect(self._on_command_from_c)

    # =========================================================
    # Connection handlers
    # =========================================================
    def _on_conn_a(self, status: str) -> None:
        if "Connected" in status:
            self.chip_a.setText("A: Connected")
            self.chip_a.setStyleSheet(_chip("", "#22c55e"))
        elif "Disconnected" in status:
            self.chip_a.setText("A: Disconnected")
            self.chip_a.setStyleSheet(_chip("", "#ef4444"))
        else:
            self.chip_a.setText(f"A: {status}")
            self.chip_a.setStyleSheet(_chip("", "#f59e0b"))

    def _on_conn_c(self, status: str) -> None:
        if "Connected" in status:
            self.chip_c.setText("C: Connected")
            self.chip_c.setStyleSheet(_chip("", "#22c55e"))
        else:
            self.chip_c.setText("C: Waiting")
            self.chip_c.setStyleSheet(_chip("", "#6b7280"))

    # =========================================================
    # Status update
    # =========================================================
    def _on_status(self, st: Dict) -> None:
        # Update counters
        self.status_updates += 1

        # Apply SHT20 toggle behaviour like original:
        if self.sht20_enabled:
            self.temperature = float(st.get("temperature", self.temperature))
            self.humidity = float(st.get("humidity", self.humidity))

        self.current_position = int(st.get("position", self.current_position))
        self.current_speed = int(st.get("speed", self.current_speed))
        self.driver_alarm = bool(st.get("driver_alarm", self.driver_alarm))
        self.driver_inpos = bool(st.get("driver_inpos", self.driver_inpos))
        self.driver_running = bool(st.get("driver_running", self.driver_running))

        self.counter_value = int(st.get("counter_value", self.counter_value))
        self.counter_target = int(st.get("counter_target", self.counter_target))
        self.auto_state_code = int(st.get("auto_state_code", self.auto_state_code))
        self.current_mode = int(st.get("mode", self.current_mode))

        self.step_enabled = bool(st.get("step_enabled", self.step_enabled))
        self.jog_state = int(st.get("jog_state", self.jog_state))

        self._refresh_dashboard()

        # Forward status to layer C (same shape as original)
        status_msg = {
            "type": "status",
            "timestamp": float(st.get("timestamp", time.time())),
            "data": {
                "position": self.current_position,
                "speed": self.current_speed,
                "temperature": float(self.temperature),
                "humidity": float(self.humidity),
                "driver_alarm": self.driver_alarm,
                "driver_inpos": self.driver_inpos,
                "driver_running": self.driver_running,
                "counter_value": self.counter_value,
                "counter_target": self.counter_target,
                "auto_state_code": self.auto_state_code,
                "auto_state_text": AUTO_STATE_MAP.get(self.auto_state_code, "Unknown"),
                "mode": self.current_mode,
                "step_enabled": self.step_enabled,
                "jog_state": self.jog_state,
            }
        }
        self.server_c.send(status_msg)

    def _refresh_dashboard(self) -> None:
        # temp/humi
        self.lbl_temp.setText(f"{self.temperature:.1f} °C")
        self.lbl_humi.setText(f"{self.humidity:.1f} %RH")

        # motor
        self.lbl_position.setText(f"Position: {self.current_position:,} pulse")
        self.lbl_speed.setText(f"Speed: {self.current_speed:,} pps")

        self.lbl_alarm.setText("Alarm: YES" if self.driver_alarm else "Alarm: NO")
        self.lbl_alarm.setStyleSheet("font-weight: 900; color: " + ("#ef4444" if self.driver_alarm else "#22c55e") + ";")

        self.lbl_inpos.setText("InPos: YES" if self.driver_inpos else "InPos: NO")
        self.lbl_inpos.setStyleSheet("font-weight: 900; color: " + ("#22c55e" if self.driver_inpos else "#f59e0b") + ";")

        self.lbl_running.setText("Running: YES" if self.driver_running else "Running: NO")
        self.lbl_running.setStyleSheet("font-weight: 900; color: " + ("#3b82f6" if self.driver_running else "#6b7280") + ";")

        self.lbl_step_state.setText("STEP: ON" if self.step_enabled else "STEP: OFF")
        self.lbl_step_state.setStyleSheet("font-weight: 900; color: " + ("#22c55e" if self.step_enabled else "#6b7280") + ";")

        if self.jog_state == 1:
            self.lbl_jog_state.setText("JOG: CW")
            self.lbl_jog_state.setStyleSheet("font-weight: 900; color: #3b82f6;")
        elif self.jog_state == 2:
            self.lbl_jog_state.setText("JOG: CCW")
            self.lbl_jog_state.setStyleSheet("font-weight: 900; color: #3b82f6;")
        else:
            self.lbl_jog_state.setText("JOG: OFF")
            self.lbl_jog_state.setStyleSheet("font-weight: 900; color: #6b7280;")

        # process / counter
        self.lbl_counter.setText(f"Counter: {self.counter_value} / {self.counter_target if self.counter_target else '--'}")
        auto_text = AUTO_STATE_MAP.get(self.auto_state_code, "Unknown")
        self.lbl_auto_state.setText(f"AUTO STATE: {auto_text}")

        done = False
        resetting = False
        if self.counter_target > 0 and self.counter_value >= self.counter_target:
            done = True
        if self.auto_state_code == 3:
            resetting = True
            done = True

        if resetting:
            self.lbl_counter_done.setText("DONE: YES (Resetting...)")
            self.lbl_counter_done.setStyleSheet("font-weight: 900; color: #f59e0b;")
        elif done:
            self.lbl_counter_done.setText("DONE: YES")
            self.lbl_counter_done.setStyleSheet("font-weight: 900; color: #22c55e;")
        else:
            self.lbl_counter_done.setText("DONE: NO")
            self.lbl_counter_done.setStyleSheet("font-weight: 900; color: #6b7280;")

        if self.counter_target > 0:
            self.lbl_target_info.setText(f"Current target from A: {self.counter_target}")
            p = int(min(100, max(0, (self.counter_value / self.counter_target) * 100)))
            self.progress.setValue(p)
        else:
            self.lbl_target_info.setText("Current target from A: --")
            self.progress.setValue(0)

        # mode
        if self.current_mode == 1:
            self.lbl_mode_status.setText("Mode: MANUAL")
            self.lbl_mode_status.setStyleSheet("font-weight: 900; color: #f59e0b;")
        else:
            self.lbl_mode_status.setText("Mode: AUTO")
            self.lbl_mode_status.setStyleSheet("font-weight: 900; color: #22c55e;")

    # =========================================================
    # command handling (C -> B -> A)
    # =========================================================
    def _on_command_from_c(self, command: Dict) -> None:
        cmd_type = command.get("type")
        if cmd_type == "heartbeat":
            return

        self.commands_from_c += 1
        self._show_forward_animation(str(cmd_type))
        self.log(f"Received from C: {cmd_type}")

        source = command.get("source", "Layer_C")
        timestamp = time.strftime("%H:%M:%S")
        self.command_history.appendleft(f"[{timestamp}] {source} → {cmd_type}")
        self._refresh_history()

        allowed = {"motor_control", "jog_control", "stop_motor", "release_control", "emergency_stop", "set_target", "set_mode"}
        if cmd_type not in allowed:
            self.log(f"Rejected: unsupported command '{cmd_type}'")
            return

        self._execute_command(command, from_c=True)

    def _execute_command(self, command: Dict, from_c: bool) -> None:
        cmd_type = command.get("type")
        source = command.get("source", "Layer_C" if from_c else "Layer_B")
        priority = int(command.get("priority", 3 if from_c else 2))
        data = command.get("data", {}) or {}

        if cmd_type == "set_target":
            target = int(data.get("target", 0))
            if target < TARGET_MIN or target > TARGET_MAX:
                self.log(f"Invalid target {target}")
                return
            if self.modbus.write_target(target):
                self.commands_forwarded += 1
                self.log(f"SET TARGET {target} (from {source})")

        elif cmd_type == "set_mode":
            mode = int(data.get("mode", 0))
            if mode not in (0, 1):
                return
            if self.modbus.write_mode(mode):
                self.commands_forwarded += 1
                self.log(f"SET MODE {mode} (from {source})")

        elif cmd_type == "motor_control":
            step_cmd = data.get("step_command")
            alarm_reset = bool(data.get("alarm_reset", False))

            if step_cmd == "on":
                if self.modbus.write_cmd_packet(1, origin_source=source, priority=priority):
                    self.commands_forwarded += 1
                    self.log(f"STEP ON (via Modbus) from {source}")

            elif step_cmd == "off":
                if self.modbus.write_cmd_packet(2, origin_source=source, priority=priority):
                    self.commands_forwarded += 1
                    self.log(f"STEP OFF (via Modbus) from {source}")

            elif alarm_reset:
                if self.modbus.write_cmd_packet(8, origin_source=source, priority=priority):
                    self.commands_forwarded += 1
                    self.log(f"RESET ALARM (via Modbus) from {source}")

            else:
                pos = int(data.get("position", self.current_position))
                speed = int(data.get("speed", self.current_speed if self.current_speed > 0 else 1000))
                if self.modbus.write_cmd_packet(3, pos=pos, speed=speed, origin_source=source, priority=priority):
                    self.commands_forwarded += 1
                    self.log(f"MOVE ABS (Modbus) from {source}: pos={pos:,} @ {speed:,}pps")

        elif cmd_type == "jog_control":
            speed = int(data.get("speed", 0))
            direction = int(data.get("direction", 1))
            cmd = 5 if direction > 0 else 6
            if self.modbus.write_cmd_packet(cmd, speed=speed, origin_source=source, priority=priority):
                self.commands_forwarded += 1
                self.log(f"JOG {'CW' if direction > 0 else 'CCW'} (Modbus) from {source}: {speed:,}pps")

        elif cmd_type == "stop_motor":
            if self.modbus.write_cmd_packet(7, origin_source=source, priority=priority):
                self.commands_forwarded += 1
                self.log(f"STOP (Modbus) from {source}")

        elif cmd_type == "release_control":
            if self.modbus.write_cmd_packet(7, origin_source="Local", priority=1):
                self.commands_forwarded += 1
                self.log("RELEASE CONTROL → Local (via Modbus)")

        elif cmd_type == "emergency_stop":
            if self.modbus.write_cmd_packet(9, origin_source=source, priority=priority):
                self.commands_forwarded += 1
                self.log(f"EMERGENCY STOP (Modbus) from {source}")

    # =========================================================
    # Buttons (UI -> execute)
    # =========================================================
    def _ensure_manual_mode(self) -> bool:
        if self.current_mode != 1:
            QMessageBox.warning(
                self, "Mode error",
                "Layer A đang ở AUTO.\nHãy chuyển sang MANUAL trước khi điều khiển từ B."
            )
            return False
        return True

    def set_mode(self, mode: int) -> None:
        if mode not in (0, 1):
            return
        cmd = {"type": "set_mode", "priority": 2, "source": "Layer_B", "data": {"mode": int(mode)}, "timestamp": time.time()}
        self._execute_command(cmd, from_c=False)

    def set_counter_target(self) -> None:
        target = int(self.sp_target.value())
        cmd = {"type": "set_target", "priority": 2, "source": "Layer_B", "data": {"target": target}, "timestamp": time.time()}
        self._execute_command(cmd, from_c=False)

    def override_motor(self) -> None:
        if not self._ensure_manual_mode():
            return
        pos = int(self.sp_pos.value())
        speed = int(self.sp_speed.value())
        cmd = {"type": "motor_control", "priority": 2, "source": "Layer_B", "data": {"position": pos, "speed": speed}, "timestamp": time.time()}
        self._execute_command(cmd, from_c=False)

    def jog_move(self, direction: int) -> None:
        if not self._ensure_manual_mode():
            return
        spd = int(self.sp_jog_speed.value())
        cmd = {"type": "jog_control", "priority": 2, "source": "Layer_B", "data": {"speed": spd, "direction": int(direction)}, "timestamp": time.time()}
        self._execute_command(cmd, from_c=False)

    def step_on(self) -> None:
        if not self._ensure_manual_mode():
            return
        cmd = {"type": "motor_control", "priority": 2, "source": "Layer_B", "data": {"step_command": "on"}, "timestamp": time.time()}
        self._execute_command(cmd, from_c=False)

    def step_off(self) -> None:
        if not self._ensure_manual_mode():
            return
        cmd = {"type": "motor_control", "priority": 2, "source": "Layer_B", "data": {"step_command": "off"}, "timestamp": time.time()}
        self._execute_command(cmd, from_c=False)

    def reset_alarm(self) -> None:
        if not self._ensure_manual_mode():
            return
        cmd = {"type": "motor_control", "priority": 2, "source": "Layer_B", "data": {"alarm_reset": True}, "timestamp": time.time()}
        self._execute_command(cmd, from_c=False)

    def stop_motor(self) -> None:
        if not self._ensure_manual_mode():
            return
        cmd = {"type": "stop_motor", "priority": 2, "source": "Layer_B", "timestamp": time.time()}
        self._execute_command(cmd, from_c=False)

    def release_control(self) -> None:
        if not self._ensure_manual_mode():
            return
        cmd = {"type": "release_control", "priority": 2, "source": "Layer_B", "timestamp": time.time()}
        self._execute_command(cmd, from_c=False)

    def emergency_stop(self) -> None:
        if not self._ensure_manual_mode():
            return
        reply = QMessageBox.question(
            self, "Emergency Stop",
            "EMERGENCY STOP system?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            cmd = {"type": "emergency_stop", "priority": 2, "source": "Layer_B", "timestamp": time.time()}
            self._execute_command(cmd, from_c=False)

    # =========================================================
    # UX helpers
    # =========================================================
    def toggle_sht20(self) -> None:
        self.sht20_enabled = not self.sht20_enabled

        if self.sht20_enabled:
            self.btn_toggle_sht20.setText("SHT20: ON")
            self.btn_toggle_sht20.setStyleSheet("""
                QPushButton {
                    background: #22c55e;
                    color: white;
                    border: 1px solid #16a34a;
                    font-weight: 800;
                }
                QPushButton:hover { background: #16a34a; }
            """)
            self.log("SHT20 sensor reading ENABLED")
        else:
            self.btn_toggle_sht20.setText("SHT20: OFF")
            self.btn_toggle_sht20.setStyleSheet("""
                QPushButton {
                    background: #ef4444;
                    color: white;
                    border: 1px solid #dc2626;
                    font-weight: 800;
                }
                QPushButton:hover { background: #dc2626; }
            """)
            self.log("SHT20 sensor reading DISABLED")

    def _show_forward_animation(self, cmd_type: str) -> None:
        self.lbl_forward_status.setText(f"FORWARDING: {cmd_type}")
        self.lbl_forward_status.setStyleSheet("""
            background: #3b82f6;
            color: white;
            font-size: 12pt;
            font-weight: 900;
            padding: 12px;
            border-radius: 12px;
        """)
        QTimer.singleShot(900, self._reset_forward_status)

    def _reset_forward_status(self) -> None:
        self.lbl_forward_status.setText("Idle")
        self.lbl_forward_status.setStyleSheet("""
            background: #6b7280;
            color: white;
            font-size: 12pt;
            font-weight: 900;
            padding: 12px;
            border-radius: 12px;
        """)

    def _refresh_history(self) -> None:
        self.history_text.setPlainText("\n".join(list(self.command_history)))

    def _update_statistics(self) -> None:
        uptime = int(time.time() - self.start_time)
        h = uptime // 3600
        m = (uptime % 3600) // 60
        s = uptime % 60
        self.lbl_uptime.setText(f"{h:02d}:{m:02d}:{s:02d}")

        self.lbl_cmd_forwarded.setText(str(self.commands_forwarded))
        self.lbl_cmd_from_c.setText(str(self.commands_from_c))
        self.lbl_status_updates.setText(str(self.status_updates))

    def log(self, message: str) -> None:
        ts = time.strftime("%H:%M:%S")
        # keep last ~600 lines
        if self.log_text.document().blockCount() > 600:
            self.log_text.clear()
        self.log_text.appendPlainText(f"[{ts}] {message}")

    # =========================================================
    # Close
    # =========================================================
    def closeEvent(self, event) -> None:
        try:
            self.stats_timer.stop()
        except Exception:
            pass
        try:
            self.modbus.stop()
        except Exception:
            pass
        try:
            self.server_c.stop()
        except Exception:
            pass
        event.accept()
