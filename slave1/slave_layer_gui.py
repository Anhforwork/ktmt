# slave_layer_gui.py
"""
SLAVE LAYER - Device Connection Tester + Modbus Server
GUI giống hình ảnh mô tả
"""

import sys
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QGridLayout, QTextEdit, QFrame, QSpinBox, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QPalette, QColor

from config import (
    COLOR_CONNECTED, COLOR_DISCONNECTED, COLOR_ERROR,
    COLOR_WARNING, COLOR_INFO, COLOR_NEUTRAL
)
from device_manager import DeviceManager
from plc_controller import PLCController


class SignalEmitter(QObject):
    """Signal emitter để giao tiếp giữa thread và UI"""
    log_signal = pyqtSignal(str)
    tcp_status_signal = pyqtSignal(str)
    serial_status_signal = pyqtSignal(str)


class SlaveLayerGUI(QWidget):
    """GUI chính của Slave Layer"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SLAVE LAYER - Device Connection Tester + Modbus Server")
        self.setGeometry(100, 100, 800, 800)
        
        # Initialize managers
        self.device_manager = DeviceManager()
        self.plc_controller = PLCController(
            self.device_manager,
            log_callback=self.log
        )
        
        # Signals
        self.signals = SignalEmitter()
        self.signals.log_signal.connect(self.append_log)
        self.signals.tcp_status_signal.connect(self.update_tcp_status)
        self.signals.serial_status_signal.connect(self.update_serial_status)
        
        # Auto test flag
        self.auto_test_running = False
        self.auto_test_timer = None
        
        # Build UI
        self._build_ui()
        
        # Initial logs
        self.log("SLAVE LAYER - MODBUS TCP SERVER initialized.")
        self.log("Device tester + Modbus TCP Server for Master connection")
        
        # Start update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_device_status)
        self.timer.start(1000)  # Update every second
    
    def _build_ui(self):
        """Xây dựng giao diện"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        layout.addWidget(self._create_header())
        
        # Modbus TCP Server section
        layout.addWidget(self._create_tcp_server_section())
        
        # RS485 Connection section
        layout.addWidget(self._create_rs485_section())
        
        # Device Status section
        layout.addWidget(self._create_device_status_section())
        
        # Test Control section
        layout.addWidget(self._create_test_control_section())
        
        # Event Log section
        layout.addWidget(self._create_log_section())
        
        self.setLayout(layout)
    
    def _create_header(self):
        """Tạo header"""
        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.Box)
        header_frame.setLineWidth(2)
        header_frame.setStyleSheet("""
            border: 3px solid #2c3e50;
            background: #34495e;
            border-radius: 8px;
            padding: 10px;
        """)
        
        header_layout = QVBoxLayout()
        
        title = QLabel("SLAVE LAYER - Device Connection Tester + Modbus Server")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            color: white;
            font-size: 20pt;
            font-weight: bold;
            padding: 10px;
        """)
        header_layout.addWidget(title)
        
        subtitle = QLabel("Device tester + Modbus TCP Server for Master connection")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            color: #bdc3c7;
            font-size: 12pt;
            font-style: italic;
            padding: 5px;
        """)
        header_layout.addWidget(subtitle)
        
        header_frame.setLayout(header_layout)
        return header_frame
    
    def _create_tcp_server_section(self):
        """Tạo phần Modbus TCP Server"""
        group = QGroupBox("MODBUS TCP SERVER")
        group.setStyleSheet(self._get_groupbox_style("#2c3e50"))
        
        layout = QGridLayout()
        layout.setSpacing(15)
        
        # Server info
        layout.addWidget(QLabel("Server Address:"), 0, 0)
        self.lbl_server_addr = QLabel("192.168.1.220")
        self.lbl_server_addr.setStyleSheet("font-weight: bold; color: #3498db;")
        layout.addWidget(self.lbl_server_addr, 0, 1)
        
        layout.addWidget(QLabel("Port:"), 1, 0)
        self.lbl_server_port = QLabel("502")
        self.lbl_server_port.setStyleSheet("font-weight: bold; color: #3498db;")
        layout.addWidget(self.lbl_server_port, 1, 1)
        
        layout.addWidget(QLabel("Status:"), 2, 0)
        self.lbl_tcp_status = QLabel("STOPPED")
        self.lbl_tcp_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
        layout.addWidget(self.lbl_tcp_status, 2, 1)
        
        layout.addWidget(QLabel("Master Connected:"), 3, 0)
        self.lbl_master_connected = QLabel("NO")
        self.lbl_master_connected.setStyleSheet("font-weight: bold; color: #e74c3c;")
        layout.addWidget(self.lbl_master_connected, 3, 1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_start_server = QPushButton("START MODBUS SERVER")
        self.btn_start_server.setStyleSheet(self._get_button_style("#27ae60", True))
        self.btn_start_server.clicked.connect(self.start_modbus_server)
        btn_layout.addWidget(self.btn_start_server)
        
        self.btn_stop_server = QPushButton("STOP SERVER")
        self.btn_stop_server.setStyleSheet(self._get_button_style("#e74c3c", True))
        self.btn_stop_server.clicked.connect(self.stop_modbus_server)
        self.btn_stop_server.setEnabled(False)
        btn_layout.addWidget(self.btn_stop_server)
        
        layout.addLayout(btn_layout, 4, 0, 1, 2)
        
        group.setLayout(layout)
        return group
    
    def _create_rs485_section(self):
        """Tạo phần RS485 Connection"""
        group = QGroupBox("RS485 CONNECTION")
        group.setStyleSheet(self._get_groupbox_style("#16a085"))
        
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Port selection
        layout.addWidget(QLabel("Port:"), 0, 0)
        self.combo_port = QComboBox()
        self.combo_port.addItems(["COM11", "COM3", "COM14", "COM5", "COM6", "COM7", "COM8", "COM9"])
        self.combo_port.setCurrentText("COM11")
        layout.addWidget(self.combo_port, 0, 1)
        
        # Baudrate
        layout.addWidget(QLabel("Baudrate:"), 1, 0)
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.combo_baud.setCurrentText("9600")
        layout.addWidget(self.combo_baud, 1, 1)
        
        # Parity
        layout.addWidget(QLabel("Parity:"), 2, 0)
        self.combo_parity = QComboBox()
        self.combo_parity.addItems(["Even (E)", "Odd (O)", "None (N)"])
        self.combo_parity.setCurrentText("Even (E)")
        layout.addWidget(self.combo_parity, 2, 1)
        
        # Status
        layout.addWidget(QLabel("Status:"), 3, 0)
        self.lbl_serial_status = QLabel("DISCONNECTED")
        self.lbl_serial_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
        layout.addWidget(self.lbl_serial_status, 3, 1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_connect = QPushButton("CONNECT")
        self.btn_connect.setStyleSheet(self._get_button_style("#27ae60", True))
        self.btn_connect.clicked.connect(self.connect_serial)
        btn_layout.addWidget(self.btn_connect)
        
        self.btn_disconnect = QPushButton("DISCONNECT")
        self.btn_disconnect.setStyleSheet(self._get_button_style("#e74c3c", True))
        self.btn_disconnect.clicked.connect(self.disconnect_serial)
        self.btn_disconnect.setEnabled(False)
        btn_layout.addWidget(self.btn_disconnect)
        
        layout.addLayout(btn_layout, 4, 0, 1, 2)
        
        group.setLayout(layout)
        return group
    
    def _create_device_status_section(self):
        """Tạo phần Device Status"""
        group = QGroupBox("DEVICE STATUS")
        group.setStyleSheet(self._get_groupbox_style("#8e44ad"))
        
        layout = QGridLayout()
        layout.setSpacing(12)
        
        # SHT20 Sensor
        layout.addWidget(QLabel("SHT20 Sensor:"), 0, 0)
        self.lbl_sht20_status = QLabel("OFFLINE")
        self.lbl_sht20_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
        layout.addWidget(self.lbl_sht20_status, 0, 1)
        
        layout.addWidget(QLabel("Temp:"), 0, 2)
        self.lbl_temp = QLabel("--.-°C")
        self.lbl_temp.setStyleSheet("font-weight: bold; color: #3498db;")
        layout.addWidget(self.lbl_temp, 0, 3)
        
        layout.addWidget(QLabel("Humi:"), 0, 4)
        self.lbl_humi = QLabel("--.-%")
        self.lbl_humi.setStyleSheet("font-weight: bold; color: #3498db;")
        layout.addWidget(self.lbl_humi, 0, 5)
        
        # Motor Driver
        layout.addWidget(QLabel("Motor Driver:"), 1, 0)
        self.lbl_motor_status = QLabel("OFFLINE")
        self.lbl_motor_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
        layout.addWidget(self.lbl_motor_status, 1, 1)
        
        layout.addWidget(QLabel("Position:"), 1, 2)
        self.lbl_position = QLabel("0 pulse")
        self.lbl_position.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.lbl_position, 1, 3)
        
        layout.addWidget(QLabel("Alarm:"), 2, 0)
        self.lbl_alarm = QLabel("-")
        self.lbl_alarm.setStyleSheet("font-weight: bold; color: #e74c3c;")
        layout.addWidget(self.lbl_alarm, 2, 1)
        
        layout.addWidget(QLabel("InPos:"), 2, 2)
        self.lbl_inpos = QLabel("-")
        self.lbl_inpos.setStyleSheet("font-weight: bold; color: #e67e22;")
        layout.addWidget(self.lbl_inpos, 2, 3)
        
        layout.addWidget(QLabel("Run:"), 2, 4)
        self.lbl_run = QLabel("-")
        self.lbl_run.setStyleSheet("font-weight: bold; color: #95a5a6;")
        layout.addWidget(self.lbl_run, 2, 5)
        
        group.setLayout(layout)
        return group
    
    def _create_test_control_section(self):
        """Tạo phần Test Control"""
        group = QGroupBox("TEST CONTROL")
        group.setStyleSheet(self._get_groupbox_style("#d35400"))
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Test all devices button
        self.btn_test_all = QPushButton("TEST ALL DEVICES (ONCE)")
        self.btn_test_all.setStyleSheet(self._get_button_style("#3498db", True))
        self.btn_test_all.clicked.connect(self.test_all_devices)
        layout.addWidget(self.btn_test_all)
        
        # Auto test section
        auto_layout = QHBoxLayout()
        
        self.btn_auto_test = QPushButton("AUTO TEST (1 sec interval)")
        self.btn_auto_test.setStyleSheet(self._get_button_style("#f39c12", True))
        self.btn_auto_test.clicked.connect(self.toggle_auto_test)
        auto_layout.addWidget(self.btn_auto_test)
        
        self.lbl_auto_test_status = QLabel("OFF")
        self.lbl_auto_test_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
        auto_layout.addWidget(self.lbl_auto_test_status)
        
        layout.addLayout(auto_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_log_section(self):
        """Tạo phần Event Log"""
        group = QGroupBox("EVENT LOG")
        group.setStyleSheet(self._get_groupbox_style("#7f8c8d"))
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Log display
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet("""
            background: #2c3e50;
            color: #ecf0f1;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 9pt;
            border-radius: 4px;
            border: 1px solid #34495e;
            padding: 5px;
        """)
        layout.addWidget(self.log_text)
        
        # Log controls
        control_layout = QHBoxLayout()
        
        self.btn_clear_log = QPushButton("CLEAR LOG")
        self.btn_clear_log.setStyleSheet(self._get_button_style("#95a5a6"))
        self.btn_clear_log.clicked.connect(self.clear_log)
        control_layout.addWidget(self.btn_clear_log)
        
        self.btn_export_log = QPushButton("EXPORT TO FILE")
        self.btn_export_log.setStyleSheet(self._get_button_style("#3498db"))
        self.btn_export_log.clicked.connect(self.export_log)
        control_layout.addWidget(self.btn_export_log)
        
        # Line counter
        control_layout.addStretch()
        self.lbl_line_count = QLabel("Lines: 0 / 200")
        self.lbl_line_count.setStyleSheet("color: #7f8c8d; font-weight: bold;")
        control_layout.addWidget(self.lbl_line_count)
        
        layout.addLayout(control_layout)
        
        group.setLayout(layout)
        return group
    
    @staticmethod
    def _get_groupbox_style(border_color):
        """Style cho QGroupBox"""
        return f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 12pt;
                color: {border_color};
                border: 2px solid {border_color};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                background-color: white;
            }}
        """
    
    @staticmethod
    def _get_button_style(bg_color, large=False):
        """Style cho button"""
        size = "padding: 12px 20px;" if large else "padding: 8px 15px;"
        font = "font-size: 11pt;" if large else "font-size: 10pt;"
        
        return f"""
            QPushButton {{
                background: {bg_color};
                color: white;
                font-weight: bold;
                {font}
                {size}
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {QColor(bg_color).darker(120).name()};
            }}
            QPushButton:disabled {{
                background: #95a5a6;
                color: #bdc3c7;
            }}
        """
    
    def log(self, msg: str):
        """Ghi log"""
        ts = time.strftime("[%H:%M:%S]")
        full_msg = f"{ts} {msg}"
        self.log_text.append(full_msg)
        
        # Update line count
        lines = self.log_text.toPlainText().count('\n') + 1
        self.lbl_line_count.setText(f"Lines: {lines} / 200")
        
        # Limit log size
        if lines > 200:
            text = self.log_text.toPlainText()
            lines_list = text.split('\n')
            self.log_text.setPlainText('\n'.join(lines_list[-200:]))
    
    def append_log(self, msg: str):
        """Append log từ signal"""
        self.log(msg)
    
    def clear_log(self):
        """Xóa log"""
        self.log_text.clear()
        self.lbl_line_count.setText("Lines: 0 / 200")
    
    def export_log(self):
        """Export log to file"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"slave_layer_log_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_text.toPlainText())
            
            self.log(f"Log exported to {filename}")
        except Exception as e:
            self.log(f"Error exporting log: {e}")
    
    def update_device_status(self):
        """Cập nhật trạng thái thiết bị"""
        if not self.device_manager.is_connected():
            return
        
        # Đọc tất cả thiết bị
        self.device_manager.read_all_devices()
        
        # Cập nhật UI
        dm = self.device_manager
        
        # SHT20
        if dm.sht20_ok:
            self.lbl_sht20_status.setText("ONLINE")
            self.lbl_sht20_status.setStyleSheet("font-weight: bold; color: #27ae60;")
            self.lbl_temp.setText(f"{dm.temperature:.1f}°C")
            self.lbl_humi.setText(f"{dm.humidity:.1f}%")
        else:
            self.lbl_sht20_status.setText("OFFLINE")
            self.lbl_sht20_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
            self.lbl_temp.setText("--.-°C")
            self.lbl_humi.setText("--.-%")
        
        # Motor Driver
        if any([dm.driver_alarm, dm.driver_inpos, dm.driver_running]):
            self.lbl_motor_status.setText("ONLINE")
            self.lbl_motor_status.setStyleSheet("font-weight: bold; color: #27ae60;")
        else:
            self.lbl_motor_status.setText("OFFLINE")
            self.lbl_motor_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
        
        self.lbl_position.setText(f"{dm.current_position:,} pulse")
        self.lbl_alarm.setText("YES" if dm.driver_alarm else "NO")
        self.lbl_inpos.setText("YES" if dm.driver_inpos else "NO")
        self.lbl_run.setText("YES" if dm.driver_running else "NO")
        
        # Update colors based on status
        self.lbl_alarm.setStyleSheet(
            f"font-weight: bold; color: {COLOR_ERROR if dm.driver_alarm else COLOR_CONNECTED};"
        )
        self.lbl_inpos.setStyleSheet(
            f"font-weight: bold; color: {COLOR_CONNECTED if dm.driver_inpos else COLOR_WARNING};"
        )
        self.lbl_run.setStyleSheet(
            f"font-weight: bold; color: {COLOR_INFO if dm.driver_running else COLOR_NEUTRAL};"
        )
    
    def connect_serial(self):
        """Kết nối serial"""
        if self.device_manager.is_connected():
            self.log("Already connected.")
            return
        
        port = self.combo_port.currentText()
        baud = int(self.combo_baud.currentText())
        
        success, message = self.device_manager.connect(port, baud)
        
        if success:
            self.lbl_serial_status.setText("CONNECTED")
            self.lbl_serial_status.setStyleSheet("font-weight: bold; color: #27ae60;")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.log(f"RS485 connected to {port} @ {baud} baud")
        else:
            self.log(f"RS485 connection error: {message}")
    
    def disconnect_serial(self):
        """Ngắt kết nối serial"""
        self.device_manager.disconnect()
        self.lbl_serial_status.setText("DISCONNECTED")
        self.lbl_serial_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.log("RS485 disconnected")
    
    def start_modbus_server(self):
        """Khởi động Modbus TCP Server"""
        try:
            self.plc_controller.start_modbus_server(
                status_callback=lambda msg: self.signals.tcp_status_signal.emit(msg)
            )
            self.lbl_tcp_status.setText("RUNNING")
            self.lbl_tcp_status.setStyleSheet("font-weight: bold; color: #27ae60;")
            self.btn_start_server.setEnabled(False)
            self.btn_stop_server.setEnabled(True)
            self.log("Modbus TCP Server started")
        except Exception as e:
            self.log(f"Error starting Modbus server: {e}")
    
    def stop_modbus_server(self):
        """Dừng Modbus TCP Server"""
        self.plc_controller.stop_modbus_server()
        self.lbl_tcp_status.setText("STOPPED")
        self.lbl_tcp_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
        self.btn_start_server.setEnabled(True)
        self.btn_stop_server.setEnabled(False)
        self.log("Modbus TCP Server stopped")
    
    def test_all_devices(self):
        """Test tất cả thiết bị một lần"""
        if not self.device_manager.is_connected():
            self.log("Cannot test devices: RS485 not connected")
            return
        
        self.log("Testing all devices...")
        
        # Test từng thiết bị
        results = []
        
        # Test SHT20
        if self.device_manager.read_sht20():
            results.append("SHT20: OK")
        else:
            results.append("SHT20: FAILED")
        
        # Test Driver Position
        if self.device_manager.read_driver_position():
            results.append("Driver Position: OK")
        else:
            results.append("Driver Position: FAILED")
        
        # Test Driver Status
        if self.device_manager.read_driver_status():
            results.append("Driver Status: OK")
        else:
            results.append("Driver Status: FAILED")
        
        # Test Counter
        if self.device_manager.read_counter():
            results.append("Counter: OK")
        else:
            results.append("Counter: FAILED")
        
        # Hiển thị kết quả
        for result in results:
            self.log(result)
        
        self.log("Device test completed")
    
    def toggle_auto_test(self):
        """Bật/tắt auto test"""
        if self.auto_test_running:
            # Stop auto test
            if self.auto_test_timer:
                self.auto_test_timer.stop()
                self.auto_test_timer = None
            
            self.auto_test_running = False
            self.btn_auto_test.setText("AUTO TEST (1 sec interval)")
            self.lbl_auto_test_status.setText("OFF")
            self.lbl_auto_test_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
            self.log("Auto test stopped")
        else:
            # Start auto test
            self.auto_test_running = True
            self.btn_auto_test.setText("STOP AUTO TEST")
            self.lbl_auto_test_status.setText("ON")
            self.lbl_auto_test_status.setStyleSheet("font-weight: bold; color: #27ae60;")
            
            self.auto_test_timer = QTimer()
            self.auto_test_timer.timeout.connect(self.test_all_devices)
            self.auto_test_timer.start(1000)  # 1 second interval
            
            self.log("Auto test started (1 sec interval)")
    
    def update_tcp_status(self, text: str):
        """Cập nhật trạng thái TCP"""
        if "Listening" in text or "started" in text:
            self.log(f"Modbus TCP Server: {text}")
    
    def update_serial_status(self, text: str):
        """Cập nhật trạng thái serial"""
        self.log(f"RS485: {text}")
    
    def closeEvent(self, event):
        """Xử lý đóng cửa sổ"""
        if self.auto_test_timer:
            self.auto_test_timer.stop()
        
        self.timer.stop()
        self.device_manager.disconnect()
        self.plc_controller.stop_modbus_server()
        event.accept()


def main():
    """Hàm main"""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show GUI
    gui = SlaveLayerGUI()
    gui.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()