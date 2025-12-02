# slave/main.py
"""
Slave Layer - Device Connection Tester GUI
"""
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QGridLayout, QTextEdit, QFrame, QMessageBox,
    QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from logger import EventLogger, LogComponent
from serial_handler import SerialHandler
from device_tester import DeviceTester
import config


class SlaveLayerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SLAVE LAYER - Device Connection Tester")
        self.setGeometry(100, 100, 1000, 800)
        
        # Initialize components
        self.logger = EventLogger(max_lines=config.LOG_MAX_LINES)
        self.serial = SerialHandler(self.logger)
        self.tester = DeviceTester(self.serial, self.logger)
        
        # Auto test flag
        self.auto_test_enabled = False
        
        self._build_ui()
        
        # Log refresh timer
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.refresh_log)
        self.log_timer.start(100)
        
        # Auto test timer
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.auto_test)
        
        self.logger.info(LogComponent.SYSTEM, "Slave Layer initialized")
    
    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        
        # ===== TITLE =====
        title_frame = QFrame()
        title_frame.setFrameShape(QFrame.Box)
        title_frame.setStyleSheet("background: #2c3e50; border-radius: 5px;")
        title_layout = QVBoxLayout()
        
        title = QLabel("SLAVE LAYER - DEVICE CONNECTION TESTER")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-size: 20pt; font-weight: bold; padding: 15px;")
        title_layout.addWidget(title)
        
        subtitle = QLabel("Test and monitor SHT20 sensor and motor driver via Modbus RTU")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #ecf0f1; font-size: 11pt; padding: 5px;")
        title_layout.addWidget(subtitle)
        
        title_frame.setLayout(title_layout)
        main_layout.addWidget(title_frame)
        
        # ===== CONNECTION SECTION =====
        conn_group = QGroupBox("RS485 CONNECTION")
        conn_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        conn_layout = QGridLayout()
        
        # Port selection
        conn_layout.addWidget(QLabel("Port:"), 0, 0)
        self.combo_port = QComboBox()
        self.combo_port.addItems(config.AVAILABLE_PORTS)
        self.combo_port.setStyleSheet("padding: 5px; font-size: 10pt;")
        conn_layout.addWidget(self.combo_port, 0, 1)
        
        # Baudrate
        conn_layout.addWidget(QLabel("Baudrate:"), 0, 2)
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(config.AVAILABLE_BAUDS)
        self.combo_baud.setCurrentText("9600")
        self.combo_baud.setStyleSheet("padding: 5px; font-size: 10pt;")
        conn_layout.addWidget(self.combo_baud, 0, 3)
        
        # Parity
        conn_layout.addWidget(QLabel("Parity:"), 1, 0)
        self.combo_parity = QComboBox()
        self.combo_parity.addItems(["Even (E)", "Odd (O)", "None (N)"])
        self.combo_parity.setCurrentText("Even (E)")
        self.combo_parity.setStyleSheet("padding: 5px; font-size: 10pt;")
        conn_layout.addWidget(self.combo_parity, 1, 1)
        
        # Connection status
        conn_layout.addWidget(QLabel("Status:"), 1, 2)
        self.lbl_conn_status = QLabel("DISCONNECTED")
        self.lbl_conn_status.setStyleSheet("""
            color: #e74c3c;
            font-weight: bold;
            font-size: 11pt;
            padding: 5px;
        """)
        conn_layout.addWidget(self.lbl_conn_status, 1, 3)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_connect = QPushButton("CONNECT")
        self.btn_connect.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background: #229954;
            }
        """)
        self.btn_connect.clicked.connect(self.connect_serial)
        btn_layout.addWidget(self.btn_connect)
        
        self.btn_disconnect = QPushButton("DISCONNECT")
        self.btn_disconnect.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background: #c0392b;
            }
            QPushButton:disabled {
                background: #95a5a6;
            }
        """)
        self.btn_disconnect.clicked.connect(self.disconnect_serial)
        self.btn_disconnect.setEnabled(False)
        btn_layout.addWidget(self.btn_disconnect)
        
        conn_layout.addLayout(btn_layout, 2, 0, 1, 4)
        conn_group.setLayout(conn_layout)
        main_layout.addWidget(conn_group)
        
        # ===== DEVICE STATUS =====
        status_group = QGroupBox("DEVICE STATUS")
        status_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: 2px solid #9b59b6;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        status_layout = QGridLayout()
        
        # SHT20
        status_layout.addWidget(QLabel("SHT20 Sensor:"), 0, 0)
        self.lbl_sht20_status = QLabel("OFFLINE")
        self.lbl_sht20_status.setStyleSheet("color: #95a5a6; font-weight: bold; font-size: 11pt;")
        status_layout.addWidget(self.lbl_sht20_status, 0, 1)
        
        self.lbl_temp = QLabel("Temp: --.- °C")
        self.lbl_temp.setStyleSheet("font-size: 10pt;")
        status_layout.addWidget(self.lbl_temp, 0, 2)
        
        self.lbl_humi = QLabel("Humi: --.- %")
        self.lbl_humi.setStyleSheet("font-size: 10pt;")
        status_layout.addWidget(self.lbl_humi, 0, 3)
        
        # Driver
        status_layout.addWidget(QLabel("Motor Driver:"), 1, 0)
        self.lbl_driver_status = QLabel("OFFLINE")
        self.lbl_driver_status.setStyleSheet("color: #95a5a6; font-weight: bold; font-size: 11pt;")
        status_layout.addWidget(self.lbl_driver_status, 1, 1)
        
        self.lbl_position = QLabel("Position: 0 pulse")
        self.lbl_position.setStyleSheet("font-size: 10pt;")
        status_layout.addWidget(self.lbl_position, 1, 2, 1, 2)
        
        self.lbl_driver_flags = QLabel("Alarm:- InPos:- Run:-")
        self.lbl_driver_flags.setStyleSheet("font-size: 10pt;")
        status_layout.addWidget(self.lbl_driver_flags, 2, 0, 1, 4)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # ===== TEST CONTROL =====
        test_group = QGroupBox("TEST CONTROL")
        test_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: 2px solid #f39c12;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        test_layout = QHBoxLayout()
        
        self.btn_test_once = QPushButton("TEST ALL DEVICES (ONCE)")
        self.btn_test_once.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background: #2980b9;
            }
            QPushButton:disabled {
                background: #95a5a6;
            }
        """)
        self.btn_test_once.clicked.connect(self.test_once)
        self.btn_test_once.setEnabled(False)
        test_layout.addWidget(self.btn_test_once)
        
        self.chk_auto_test = QCheckBox("AUTO TEST (1 sec interval)")
        self.chk_auto_test.setStyleSheet("font-size: 10pt; font-weight: bold;")
        self.chk_auto_test.stateChanged.connect(self.toggle_auto_test)
        self.chk_auto_test.setEnabled(False)
        test_layout.addWidget(self.chk_auto_test)
        
        test_group.setLayout(test_layout)
        main_layout.addWidget(test_group)
        
        # ===== EVENT LOG =====
        log_group = QGroupBox("EVENT LOG")
        log_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: 2px solid #16a085;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        log_layout = QVBoxLayout()
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            background: #2c3e50;
            color: #ecf0f1;
            border: 1px solid #34495e;
            border-radius: 3px;
        """)
        log_layout.addWidget(self.log_text)
        
        # Log control buttons
        log_btn_layout = QHBoxLayout()
        
        self.btn_clear_log = QPushButton("CLEAR LOG")
        self.btn_clear_log.setStyleSheet("""
            background: #e67e22;
            color: white;
            font-weight: bold;
            padding: 6px 15px;
            border-radius: 3px;
        """)
        self.btn_clear_log.clicked.connect(self.clear_log)
        log_btn_layout.addWidget(self.btn_clear_log)
        
        self.btn_export_log = QPushButton("EXPORT TO FILE")
        self.btn_export_log.setStyleSheet("""
            background: #8e44ad;
            color: white;
            font-weight: bold;
            padding: 6px 15px;
            border-radius: 3px;
        """)
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
    
    def connect_serial(self):
        """Connect to serial port"""
        port = self.combo_port.currentText()
        baud = int(self.combo_baud.currentText())
        parity_map = {"Even (E)": "E", "Odd (O)": "O", "None (N)": "N"}
        parity = parity_map[self.combo_parity.currentText()]
        
        if self.serial.connect(port, baud, parity=parity):
            self.lbl_conn_status.setText("CONNECTED")
            self.lbl_conn_status.setStyleSheet("""
                color: #27ae60;
                font-weight: bold;
                font-size: 11pt;
                padding: 5px;
            """)
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.btn_test_once.setEnabled(True)
            self.chk_auto_test.setEnabled(True)
        else:
            QMessageBox.critical(self, "Error", "Cannot connect to serial port")
    
    def disconnect_serial(self):
        """Disconnect from serial port"""
        self.chk_auto_test.setChecked(False)
        self.serial.disconnect()
        self.lbl_conn_status.setText("DISCONNECTED")
        self.lbl_conn_status.setStyleSheet("""
            color: #e74c3c;
            font-weight: bold;
            font-size: 11pt;
            padding: 5px;
        """)
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.btn_test_once.setEnabled(False)
        self.chk_auto_test.setEnabled(False)
    
    def test_once(self):
        """Run test once"""
        self.tester.test_all_devices()
        self.update_device_display()
    
    def toggle_auto_test(self, state):
        """Toggle auto test mode"""
        if state == Qt.CheckState.Checked:
            self.auto_test_enabled = True
            self.test_timer.start(config.READ_INTERVAL_MS)
            self.logger.info(LogComponent.SYSTEM, "Auto test ENABLED")
        else:
            self.auto_test_enabled = False
            self.test_timer.stop()
            self.logger.info(LogComponent.SYSTEM, "Auto test DISABLED")
    
    def auto_test(self):
        """Auto test routine"""
        if self.auto_test_enabled and self.serial.is_connected:
            self.tester.test_all_devices()
            self.update_device_display()
    
    def update_device_display(self):
        """Update device status display"""
        status = self.tester.get_device_status()
        
        # SHT20
        if status['sht20']['online']:
            self.lbl_sht20_status.setText("ONLINE")
            self.lbl_sht20_status.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 11pt;")
            self.lbl_temp.setText(f"Temp: {status['sht20']['temperature']:.1f} °C")
            self.lbl_humi.setText(f"Humi: {status['sht20']['humidity']:.1f} %")
        else:
            self.lbl_sht20_status.setText("OFFLINE")
            self.lbl_sht20_status.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 11pt;")
            self.lbl_temp.setText("Temp: --.- °C")
            self.lbl_humi.setText("Humi: --.- %")
        
        # Driver
        if status['driver']['online']:
            self.lbl_driver_status.setText("ONLINE")
            self.lbl_driver_status.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 11pt;")
            self.lbl_position.setText(f"Position: {status['driver']['position']:,} pulse")
            
            alarm_str = "YES" if status['driver']['alarm'] else "NO"
            inpos_str = "YES" if status['driver']['inpos'] else "NO"
            run_str = "YES" if status['driver']['running'] else "NO"
            self.lbl_driver_flags.setText(f"Alarm:{alarm_str} InPos:{inpos_str} Run:{run_str}")
        else:
            self.lbl_driver_status.setText("OFFLINE")
            self.lbl_driver_status.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 11pt;")
            self.lbl_position.setText("Position: -- pulse")
            self.lbl_driver_flags.setText("Alarm:- InPos:- Run:-")
    
    def refresh_log(self):
        """Refresh log display"""
        logs = self.logger.get_all_logs()
        current_text = self.log_text.toPlainText()
        new_text = "\n".join(logs)
        
        if current_text != new_text:
            self.log_text.setPlainText(new_text)
            scrollbar = self.log_text.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
        
        self.lbl_log_count.setText(f"Lines: {len(logs)} / {config.LOG_MAX_LINES}")
    
    def clear_log(self):
        """Clear log"""
        reply = QMessageBox.question(
            self,
            "Clear Log",
            "Are you sure you want to clear all logs?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.logger.clear()
            self.log_text.clear()
            self.logger.info(LogComponent.SYSTEM, "Log cleared")
    
    def export_log(self):
        """Export log to file"""
        from datetime import datetime
        filename = f"slave_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        if self.logger.export_to_file(filename):
            QMessageBox.information(
                self,
                "Export Success",
                f"Log exported to:\n{filename}"
            )
            self.logger.info(LogComponent.SYSTEM, f"Log exported to {filename}")
        else:
            QMessageBox.critical(
                self,
                "Export Failed",
                "Failed to export log file"
            )
    
    def closeEvent(self, event):
        """Clean up on close"""
        self.test_timer.stop()
        self.log_timer.stop()
        if self.serial.is_connected:
            self.serial.disconnect()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = SlaveLayerGUI()
    gui.show()
    sys.exit(app.exec())