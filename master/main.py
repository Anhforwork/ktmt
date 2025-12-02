# master/main.py
"""
Master Layer - SCADA Client GUI
"""
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QGridLayout, QTextEdit, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from logger import MasterLogger, LogComponent
from modbus_client import ModbusMasterClient
from controller import MasterController
import config


class MasterLayerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MASTER LAYER - SCADA Client")
        self.setGeometry(100, 100, 1100, 900)
        
        # Initialize components
        self.logger = MasterLogger(max_lines=config.LOG_MAX_LINES)
        self.modbus = ModbusMasterClient(self.logger)
        self.controller = MasterController(self.modbus, self.logger)
        
        # Statistics
        self.uptime_start = 0
        
        self._build_ui()
        
        # Log refresh timer
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.refresh_log)
        self.log_timer.start(100)
        
        # Status polling timer
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_status)
        
        # Statistics timer
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_statistics)
        self.stats_timer.start(1000)
        
        self.logger.info(LogComponent.SYSTEM, "Master Layer initialized")
    
    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        
        # ===== TITLE =====
        title_frame = QFrame()
        title_frame.setFrameShape(QFrame.Box)
        title_frame.setStyleSheet("background: #34495e; border-radius: 5px;")
        title_layout = QVBoxLayout()
        
        title = QLabel("MASTER LAYER - SCADA CLIENT")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; font-size: 20pt; font-weight: bold; padding: 15px;")
        title_layout.addWidget(title)
        
        subtitle = QLabel("Control motor driver and monitor SHT20 sensor via Modbus TCP")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #ecf0f1; font-size: 11pt; padding: 5px;")
        title_layout.addWidget(subtitle)
        
        title_frame.setLayout(title_layout)
        main_layout.addWidget(title_frame)
        
        # ===== CONNECTION =====
        conn_group = QGroupBox("CONNECTION TO SLAVE")
        conn_group.setStyleSheet(self._group_style("#3498db"))
        conn_layout = QGridLayout()
        
        conn_layout.addWidget(QLabel("Slave Address:"), 0, 0)
        self.le_slave_host = QLineEdit(config.SLAVE_HOST)
        self.le_slave_host.setStyleSheet("padding: 5px; font-size: 10pt;")
        conn_layout.addWidget(self.le_slave_host, 0, 1)
        
        conn_layout.addWidget(QLabel("Modbus TCP Port:"), 0, 2)
        self.le_slave_port = QLineEdit(str(config.SLAVE_MODBUS_PORT))
        self.le_slave_port.setStyleSheet("padding: 5px; font-size: 10pt;")
        conn_layout.addWidget(self.le_slave_port, 0, 3)
        
        conn_layout.addWidget(QLabel("Status:"), 1, 0)
        self.lbl_conn_status = QLabel("DISCONNECTED")
        self.lbl_conn_status.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 11pt;")
        conn_layout.addWidget(self.lbl_conn_status, 1, 1)
        
        btn_layout = QHBoxLayout()
        
        self.btn_connect = QPushButton("CONNECT TO SLAVE")
        self.btn_connect.setStyleSheet(self._button_style("#27ae60"))
        self.btn_connect.clicked.connect(self.connect_to_slave)
        btn_layout.addWidget(self.btn_connect)
        
        self.btn_disconnect = QPushButton("DISCONNECT")
        self.btn_disconnect.setStyleSheet(self._button_style("#e74c3c"))
        self.btn_disconnect.clicked.connect(self.disconnect_from_slave)
        self.btn_disconnect.setEnabled(False)
        btn_layout.addWidget(self.btn_disconnect)
        
        conn_layout.addLayout(btn_layout, 2, 0, 1, 4)
        conn_group.setLayout(conn_layout)
        main_layout.addWidget(conn_group)
        
        # ===== STATISTICS =====
        stats_group = QGroupBox("SYSTEM STATISTICS")
        stats_group.setStyleSheet(self._group_style("#9b59b6"))
        stats_layout = QGridLayout()
        
        stats_layout.addWidget(QLabel("Uptime:"), 0, 0)
        self.lbl_uptime = QLabel("00:00:00")
        self.lbl_uptime.setStyleSheet("font-weight: bold; font-size: 11pt; color: #27ae60;")
        stats_layout.addWidget(self.lbl_uptime, 0, 1)
        
        stats_layout.addWidget(QLabel("Commands Sent:"), 0, 2)
        self.lbl_cmd_sent = QLabel("0")
        self.lbl_cmd_sent.setStyleSheet("font-weight: bold; font-size: 11pt; color: #3498db;")
        stats_layout.addWidget(self.lbl_cmd_sent, 0, 3)
        
        stats_layout.addWidget(QLabel("Status Reads:"), 1, 0)
        self.lbl_status_reads = QLabel("0")
        self.lbl_status_reads.setStyleSheet("font-weight: bold; font-size: 11pt; color: #e67e22;")
        stats_layout.addWidget(self.lbl_status_reads, 1, 1)
        
        stats_layout.addWidget(QLabel("Errors:"), 1, 2)
        self.lbl_errors = QLabel("0")
        self.lbl_errors.setStyleSheet("font-weight: bold; font-size: 11pt; color: #c0392b;")
        stats_layout.addWidget(self.lbl_errors, 1, 3)
        
        stats_group.setLayout(stats_layout)
        main_layout.addWidget(stats_group)
        
        # ===== DEVICE STATUS =====
        status_group = QGroupBox("DEVICE STATUS FROM SLAVE")
        status_group.setStyleSheet(self._group_style("#16a085"))
        status_layout = QGridLayout()
        
        # SHT20
        self.lbl_temp = QLabel("--.- °C")
        self.lbl_temp.setAlignment(Qt.AlignCenter)
        self.lbl_temp.setStyleSheet("""
            background: #ffffff;
            color: #333333;
            font-size: 16pt;
            font-weight: bold;
            padding: 10px;
            border-radius: 6px;
            border: 1px solid #cccccc;
        """)
        status_layout.addWidget(self.lbl_temp, 0, 0)
        
        self.lbl_humi = QLabel("--.- %")
        self.lbl_humi.setAlignment(Qt.AlignCenter)
        self.lbl_humi.setStyleSheet("""
            background: #ffffff;
            color: #333333;
            font-size: 16pt;
            font-weight: bold;
            padding: 10px;
            border-radius: 6px;
            border: 1px solid #cccccc;
        """)
        status_layout.addWidget(self.lbl_humi, 0, 1)
        
        # Driver
        self.lbl_position = QLabel("Position: -- pulse")
        self.lbl_position.setStyleSheet("font-size: 12pt; font-weight: bold;")
        status_layout.addWidget(self.lbl_position, 1, 0, 1, 2)
        
        self.lbl_speed = QLabel("Speed: -- pps")
        self.lbl_speed.setStyleSheet("font-size: 11pt; font-weight: bold;")
        status_layout.addWidget(self.lbl_speed, 2, 0)
        
        self.lbl_alarm = QLabel("Alarm: --")
        self.lbl_alarm.setStyleSheet("font-size: 11pt; font-weight: bold;")
        status_layout.addWidget(self.lbl_alarm, 2, 1)
        
        self.lbl_inpos = QLabel("InPos: --")
        self.lbl_inpos.setStyleSheet("font-size: 11pt; font-weight: bold;")
        status_layout.addWidget(self.lbl_inpos, 3, 0)
        
        self.lbl_running = QLabel("Running: --")
        self.lbl_running.setStyleSheet("font-size: 11pt; font-weight: bold;")
        status_layout.addWidget(self.lbl_running, 3, 1)
        
        # Counter
        self.lbl_counter = QLabel("Counter: -- / --")
        self.lbl_counter.setStyleSheet("font-size: 12pt; font-weight: bold; color: #2c3e50;")
        status_layout.addWidget(self.lbl_counter, 4, 0, 1, 2)
        
        self.lbl_auto_state = QLabel("AUTO STATE: --")
        self.lbl_auto_state.setStyleSheet("font-size: 11pt; font-weight: bold; color: #2c3e50;")
        status_layout.addWidget(self.lbl_auto_state, 5, 0, 1, 2)
        
        self.lbl_mode = QLabel("MODE: --")
        self.lbl_mode.setStyleSheet("font-size: 11pt; font-weight: bold; color: #27ae60;")
        status_layout.addWidget(self.lbl_mode, 6, 0, 1, 2)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # ===== MODE CONTROL =====
        mode_group = QGroupBox("MODE CONTROL")
        mode_group.setStyleSheet(self._group_style("#f39c12"))
        mode_layout = QHBoxLayout()
        
        self.btn_mode_auto = QPushButton("SET AUTO MODE")
        self.btn_mode_auto.setStyleSheet(self._button_style("#27ae60"))
        self.btn_mode_auto.clicked.connect(lambda: self.set_mode(0))
        self.btn_mode_auto.setEnabled(False)
        mode_layout.addWidget(self.btn_mode_auto)
        
        self.btn_mode_manual = QPushButton("SET MANUAL MODE")
        self.btn_mode_manual.setStyleSheet(self._button_style("#e67e22"))
        self.btn_mode_manual.clicked.connect(lambda: self.set_mode(1))
        self.btn_mode_manual.setEnabled(False)
        mode_layout.addWidget(self.btn_mode_manual)
        
        mode_group.setLayout(mode_layout)
        main_layout.addWidget(mode_group)
        
        # ===== TARGET CONTROL =====
        target_group = QGroupBox("TARGET COUNT CONTROL")
        target_group.setStyleSheet(self._group_style("#8e44ad"))
        target_layout = QHBoxLayout()
        
        target_layout.addWidget(QLabel("Target:"))
        self.le_target = QLineEdit("20")
        self.le_target.setStyleSheet("padding: 6px; font-size: 10pt;")
        target_layout.addWidget(self.le_target)
        
        self.btn_set_target = QPushButton("SEND TARGET TO SLAVE")
        self.btn_set_target.setStyleSheet(self._button_style("#9b59b6"))
        self.btn_set_target.clicked.connect(self.set_target)
        self.btn_set_target.setEnabled(False)
        target_layout.addWidget(self.btn_set_target)
        
        target_group.setLayout(target_layout)
        main_layout.addWidget(target_group)
        
        # ===== MANUAL CONTROL =====
        control_group = QGroupBox("MANUAL CONTROL (Requires MANUAL Mode)")
        control_group.setStyleSheet(self._group_style("#c0392b"))
        control_layout = QVBoxLayout()
        
        # Move Absolute
        move_layout = QHBoxLayout()
        move_layout.addWidget(QLabel("Position:"))
        self.le_position = QLineEdit("20000")
        self.le_position.setStyleSheet("padding: 5px; font-size: 10pt;")
        move_layout.addWidget(self.le_position)
        
        move_layout.addWidget(QLabel("Speed:"))
        self.le_speed = QLineEdit("8000")
        self.le_speed.setStyleSheet("padding: 5px; font-size: 10pt;")
        move_layout.addWidget(self.le_speed)
        
        self.btn_move_abs = QPushButton("MOVE ABSOLUTE")
        self.btn_move_abs.setStyleSheet(self._button_style("#3498db"))
        self.btn_move_abs.clicked.connect(self.move_absolute)
        self.btn_move_abs.setEnabled(False)
        move_layout.addWidget(self.btn_move_abs)
        
        control_layout.addLayout(move_layout)
        
        # Jog
        jog_layout = QHBoxLayout()
        jog_layout.addWidget(QLabel("Jog Speed:"))
        self.le_jog_speed = QLineEdit("12000")
        self.le_jog_speed.setStyleSheet("padding: 5px; font-size: 10pt;")
        jog_layout.addWidget(self.le_jog_speed)
        
        self.btn_jog_ccw = QPushButton("JOG CCW")
        self.btn_jog_ccw.setStyleSheet(self._button_style("#7f8c8d"))
        self.btn_jog_ccw.clicked.connect(lambda: self.jog(-1))
        self.btn_jog_ccw.setEnabled(False)
        jog_layout.addWidget(self.btn_jog_ccw)
        
        self.btn_jog_cw = QPushButton("JOG CW")
        self.btn_jog_cw.setStyleSheet(self._button_style("#7f8c8d"))
        self.btn_jog_cw.clicked.connect(lambda: self.jog(1))
        self.btn_jog_cw.setEnabled(False)
        jog_layout.addWidget(self.btn_jog_cw)
        
        control_layout.addLayout(jog_layout)
        
        # Step and others
        btn_row = QHBoxLayout()
        
        self.btn_step_on = QPushButton("STEP ON")
        self.btn_step_on.setStyleSheet(self._button_style("#95a5a6"))
        self.btn_step_on.clicked.connect(self.step_on)
        self.btn_step_on.setEnabled(False)
        btn_row.addWidget(self.btn_step_on)
        
        self.btn_step_off = QPushButton("STEP OFF")
        self.btn_step_off.setStyleSheet(self._button_style("#95a5a6"))
        self.btn_step_off.clicked.connect(self.step_off)
        self.btn_step_off.setEnabled(False)
        btn_row.addWidget(self.btn_step_off)
        
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setStyleSheet(self._button_style("#e67e22"))
        self.btn_stop.clicked.connect(self.stop_motor)
        self.btn_stop.setEnabled(False)
        btn_row.addWidget(self.btn_stop)
        
        self.btn_reset_alarm = QPushButton("RESET ALARM")
        self.btn_reset_alarm.setStyleSheet(self._button_style("#f39c12"))
        self.btn_reset_alarm.clicked.connect(self.reset_alarm)
        self.btn_reset_alarm.setEnabled(False)
        btn_row.addWidget(self.btn_reset_alarm)
        
        self.btn_emergency = QPushButton("EMERGENCY STOP")
        self.btn_emergency.setStyleSheet(self._button_style("#c0392b"))
        self.btn_emergency.clicked.connect(self.emergency_stop)
        self.btn_emergency.setEnabled(False)
        btn_row.addWidget(self.btn_emergency)
        
        control_layout.addLayout(btn_row)
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)
        
        # ===== LOG =====
        log_group = QGroupBox("SYSTEM LOG")
        log_group.setStyleSheet(self._group_style("#34495e"))
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            background: #2c3e50;
            color: #ecf0f1;
            border: 1px solid #34495e;
            border-radius: 3px;
        """)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)
        
        log_btn_layout = QHBoxLayout()
        
        self.btn_clear_log = QPushButton("CLEAR LOG")
        self.btn_clear_log.setStyleSheet(self._button_style("#e67e22"))
        self.btn_clear_log.clicked.connect(self.clear_log)
        log_btn_layout.addWidget(self.btn_clear_log)
        
        self.btn_export_log = QPushButton("EXPORT LOG")
        self.btn_export_log.setStyleSheet(self._button_style("#8e44ad"))
        self.btn_export_log.clicked.connect(self.export_log)
        log_btn_layout.addWidget(self.btn_export_log)
        
        self.lbl_log_count = QLabel("Lines: 0 / 200")
        self.lbl_log_count.setStyleSheet("font-size: 9pt; color: #7f8c8d;")
        log_btn_layout.addWidget(self.lbl_log_count)
        
        log_btn_layout.addStretch()
        log_layout.addLayout(log_btn_layout)
        
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
        self.setLayout(main_layout)
    
    def _group_style(self, color):
        return f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 12pt;
                border: 2px solid {color};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """
    
    def _button_style(self, color):
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                font-weight: bold;
                padding: 8px 15px;
                border-radius: 4px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background: {color};
                opacity: 0.8;
            }}
            QPushButton:disabled {{
                background: #95a5a6;
            }}
        """
    
    def connect_to_slave(self):
        """Connect to Slave"""
        # Update config from UI
        config.SLAVE_HOST = self.le_slave_host.text()
        config.SLAVE_MODBUS_PORT = int(self.le_slave_port.text())
        
        if self.modbus.connect():
            self.lbl_conn_status.setText("CONNECTED")
            self.lbl_conn_status.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 11pt;")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            
            # Enable controls
            self._enable_controls(True)
            
            # Start polling
            self.poll_timer.start(config.POLL_INTERVAL_MS)
            
            import time
            self.uptime_start = time.time()
        else:
            QMessageBox.critical(self, "Error", "Cannot connect to Slave")
    
    def disconnect_from_slave(self):
        """Disconnect from Slave"""
        self.poll_timer.stop()
        self.modbus.disconnect()
        
        self.lbl_conn_status.setText("DISCONNECTED")
        self.lbl_conn_status.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 11pt;")
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        
        self._enable_controls(False)
    
    def _enable_controls(self, enable):
        """Enable/disable control buttons"""
        self.btn_mode_auto.setEnabled(enable)
        self.btn_mode_manual.setEnabled(enable)
        self.btn_set_target.setEnabled(enable)
        self.btn_move_abs.setEnabled(enable)
        self.btn_jog_ccw.setEnabled(enable)
        self.btn_jog_cw.setEnabled(enable)
        self.btn_step_on.setEnabled(enable)
        self.btn_step_off.setEnabled(enable)
        self.btn_stop.setEnabled(enable)
        self.btn_reset_alarm.setEnabled(enable)
        self.btn_emergency.setEnabled(enable)
    
    def poll_status(self):
        """Poll status from Slave"""
        if self.controller.poll_status():
            self.update_status_display()
    
    def update_status_display(self):
        """Update status display"""
        status = self.controller.get_status_dict()
        
        # Temperature & Humidity
        self.lbl_temp.setText(f"{status['temperature']:.1f} °C")
        self.lbl_humi.setText(f"{status['humidity']:.1f} %")
        
        # Position & Speed
        self.lbl_position.setText(f"Position: {status['position']:,} pulse")
        self.lbl_speed.setText(f"Speed: {status['speed']:,} pps")
        
        # Alarm
        if status['driver_alarm']:
            self.lbl_alarm.setText("Alarm: YES")
            self.lbl_alarm.setStyleSheet("font-size: 11pt; font-weight: bold; color: #c0392b;")
        else:
            self.lbl_alarm.setText("Alarm: NO")
            self.lbl_alarm.setStyleSheet("font-size: 11pt; font-weight: bold; color: #27ae60;")
        
        # InPos
        if status['driver_inpos']:
            self.lbl_inpos.setText("InPos: YES")
            self.lbl_inpos.setStyleSheet("font-size: 11pt; font-weight: bold; color: #27ae60;")
        else:
            self.lbl_inpos.setText("InPos: NO")
            self.lbl_inpos.setStyleSheet("font-size: 11pt; font-weight: bold; color: #f39c12;")
        
        # Running
        if status['driver_running']:
            self.lbl_running.setText("Running: YES")
            self.lbl_running.setStyleSheet("font-size: 11pt; font-weight: bold; color: #3498db;")
        else:
            self.lbl_running.setText("Running: NO")
            self.lbl_running.setStyleSheet("font-size: 11pt; font-weight: bold; color: #95a5a6;")
        
        # Counter
        self.lbl_counter.setText(f"Counter: {status['counter_value']} / {status['counter_target']}")
        
        # Auto State
        self.lbl_auto_state.setText(f"AUTO STATE: {status['auto_state_text']}")
        
        # Mode
        mode_text = "AUTO" if status['mode'] == 0 else "MANUAL"
        self.lbl_mode.setText(f"MODE: {mode_text}")
        if status['mode'] == 1:
            self.lbl_mode.setStyleSheet("font-size: 11pt; font-weight: bold; color: #e67e22;")
        else:
            self.lbl_mode.setStyleSheet("font-size: 11pt; font-weight: bold; color: #27ae60;")
    
    def set_mode(self, mode):
        """Set mode"""
        self.controller.set_mode(mode)
    
    def set_target(self):
        """Set target"""
        try:
            target = int(self.le_target.text())
            self.controller.set_target(target)
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid target value")
    
    def move_absolute(self):
        """Move absolute"""
        try:
            pos = int(self.le_position.text())
            speed = int(self.le_speed.text())
            self.controller.move_absolute(pos, speed)
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid position or speed")
    
    def jog(self, direction):
        """Jog motor"""
        try:
            speed = int(self.le_jog_speed.text())
            if direction > 0:
                self.controller.jog_cw(speed)
            else:
                self.controller.jog_ccw(speed)
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid jog speed")
    
    def step_on(self):
        self.controller.step_on()
    
    def step_off(self):
        self.controller.step_off()
    
    def stop_motor(self):
        self.controller.stop()
    
    def reset_alarm(self):
        self.controller.reset_alarm()
    
    def emergency_stop(self):
        reply = QMessageBox.question(
            self,
            "Emergency Stop",
            "Confirm EMERGENCY STOP?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.controller.emergency_stop()
    
    def update_statistics(self):
        """Update statistics display"""
        stats = self.modbus.get_statistics()
        
        self.lbl_cmd_sent.setText(str(stats['commands_sent']))
        self.lbl_status_reads.setText(str(stats['status_reads']))
        self.lbl_errors.setText(str(stats['errors']))
        
        if self.uptime_start > 0:
            import time
            uptime = int(time.time() - self.uptime_start)
            hours = uptime // 3600
            minutes = (uptime % 3600) // 60
            seconds = uptime % 60
            self.lbl_uptime.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def refresh_log(self):
        """Refresh log display"""
        logs = self.logger.get_all_logs()
        current_text = self.log_text.toPlainText()
        new_text = "\n".join(logs)
        
        if current_text != new_text:
            self.log_text.setPlainText(new_text)
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
        
        self.lbl_log_count.setText(f"Lines: {len(logs)} / {config.LOG_MAX_LINES}")
    
    def clear_log(self):
        """Clear log"""
        self.logger.clear()
        self.log_text.clear()
        self.logger.info(LogComponent.SYSTEM, "Log cleared")
    
    def export_log(self):
        """Export log"""
        from datetime import datetime
        filename = f"master_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        if self.logger.export_to_file(filename):
            QMessageBox.information(self, "Success", f"Log exported to:\n{filename}")
            self.logger.info(LogComponent.SYSTEM, f"Log exported to {filename}")
        else:
            QMessageBox.critical(self, "Error", "Failed to export log")
    
    def closeEvent(self, event):
        """Clean up on close"""
        self.poll_timer.stop()
        self.log_timer.stop()
        self.stats_timer.stop()
        if self.modbus.connected:
            self.modbus.disconnect()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = MasterLayerGUI()
    gui.show()
    sys.exit(app.exec())