# main.py
"""
LAYER A - FIELD CONTROLLER (PLC MODE)
GUI chính của hệ thống PLC
"""

import sys
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QGridLayout, QTextEdit, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject

from config import (
    READ_INTERVAL_MS, HR_TARGET_ADDR, HR_MODE_ADDR,
    COLOR_CONNECTED, COLOR_DISCONNECTED, COLOR_ERROR,
    COLOR_WARNING, COLOR_INFO, COLOR_NEUTRAL
)
from device_manager import DeviceManager
from plc_controller import PLCController


class SignalEmitter(QObject):
    """Signal emitter để giao tiếp giữa thread và UI"""
    log_signal = pyqtSignal(str)
    tcp_status_signal = pyqtSignal(str)


class LayerA_PLC(QWidget):
    """GUI chính của PLC"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAYER A - FIELD CONTROLLER (PLC MODE)")
        self.setGeometry(50, 50, 900, 700)
        
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
        
        # Build UI
        self._build_ui()
        
        # Start Modbus TCP Server
        self.plc_controller.start_modbus_server(
            status_callback=lambda msg: self.signals.tcp_status_signal.emit(msg)
        )
        
        # Start timers
        self.timer_read = QTimer()
        self.timer_read.timeout.connect(self.read_all_devices)
        self.timer_read.start(READ_INTERVAL_MS)
        
        self.timer_auto = QTimer()
        self.timer_auto.timeout.connect(self.auto_cycle)
        self.timer_auto.start(200)
    
    def _build_ui(self):
        """Xây dựng giao diện"""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # Status bar
        layout.addWidget(self._create_status_bar())
        
        # Connection status
        layout.addWidget(self._create_connection_group())
        
        # Monitoring
        layout.addWidget(self._create_monitoring_group())
        
        # Log
        layout.addWidget(self._create_log_group())
        
        self.setLayout(layout)
        
        # Initial logs
        self.log("Layer A (PLC mode) initialized.")
        self.log("AUTO cycle enabled.")
        self.log(f"Listening for TARGET from B via Modbus TCP HR{HR_TARGET_ADDR}.")
        self.log(f"MODE control via HR{HR_MODE_ADDR} (0=AUTO, 1=MANUAL).")
    
    def _create_status_bar(self) -> QFrame:
        """Tạo thanh trạng thái"""
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Box)
        status_frame.setLineWidth(2)
        status_frame.setStyleSheet("border: 2px solid #d0d0d0; background: #f5f5f5;")
        
        s_layout = QVBoxLayout()
        
        self.lbl_main_status = QLabel("PLC AUTO MODE (AUTO/MANUAL từ Layer B)")
        self.lbl_main_status.setAlignment(Qt.AlignCenter)
        self.lbl_main_status.setStyleSheet("""
            background: #e0e0e0;
            color: #333333;
            font-size: 18pt;
            font-weight: bold;
            padding: 16px;
            border-radius: 6px;
        """)
        s_layout.addWidget(self.lbl_main_status)
        
        self.lbl_sub_status = QLabel(
            "Layer A acts as PLC: AUTO cycle theo counter hoặc MANUAL nhận lệnh từ B/C.\n"
            f"Target count từ Layer B via Modbus TCP HR{HR_TARGET_ADDR}."
        )
        self.lbl_sub_status.setAlignment(Qt.AlignCenter)
        self.lbl_sub_status.setStyleSheet("color:#555555; font-size:10pt; padding:4px;")
        s_layout.addWidget(self.lbl_sub_status)
        
        status_frame.setLayout(s_layout)
        return status_frame
    
    def _create_connection_group(self) -> QGroupBox:
        """Tạo nhóm connection status"""
        conn_group = QGroupBox("CONNECTION STATUS")
        conn_group.setStyleSheet(self._get_groupbox_style())
        
        conn_layout = QGridLayout()
        
        # RS485 status
        conn_layout.addWidget(QLabel("RS485 Interface:"), 0, 0)
        self.lbl_serial_status = QLabel("Disconnected")
        self.lbl_serial_status.setStyleSheet(
            f"font-weight:bold; font-size:11pt; color:{COLOR_DISCONNECTED};"
        )
        conn_layout.addWidget(self.lbl_serial_status, 0, 1)
        
        # Serial controls
        row_serial = QHBoxLayout()
        
        self.combo_port = QComboBox()
        self.combo_port.addItems(["COM11", "COM3", "COM14", "COM5", "COM6", "COM7"])
        row_serial.addWidget(QLabel("Port:"))
        row_serial.addWidget(self.combo_port)
        
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.combo_baud.setCurrentText("9600")
        row_serial.addWidget(QLabel("Baud:"))
        row_serial.addWidget(self.combo_baud)
        
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setStyleSheet(self._get_button_style())
        self.btn_connect.clicked.connect(self.connect_serial)
        row_serial.addWidget(self.btn_connect)
        
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setStyleSheet(self._get_button_style(secondary=True))
        self.btn_disconnect.clicked.connect(self.disconnect_serial)
        self.btn_disconnect.setEnabled(False)
        row_serial.addWidget(self.btn_disconnect)
        
        conn_layout.addLayout(row_serial, 1, 0, 1, 2)
        
        # TCP status
        conn_layout.addWidget(QLabel("Modbus TCP Server:"), 2, 0)
        self.lbl_tcp_status = QLabel("Starting...")
        self.lbl_tcp_status.setStyleSheet("font-weight:bold; font-size:11pt; color:#999999;")
        conn_layout.addWidget(self.lbl_tcp_status, 2, 1)
        
        conn_group.setLayout(conn_layout)
        return conn_group
    
    def _create_monitoring_group(self) -> QGroupBox:
        """Tạo nhóm monitoring"""
        mon_group = QGroupBox("DEVICE & PROCESS MONITORING")
        mon_group.setStyleSheet(self._get_groupbox_style())
        
        mon_layout = QGridLayout()
        
        # SHT20 sensors
        self.lbl_temp = QLabel("--.- °C")
        self.lbl_temp.setAlignment(Qt.AlignCenter)
        self.lbl_temp.setStyleSheet(self._get_sensor_display_style())
        mon_layout.addWidget(self.lbl_temp, 0, 0)
        
        self.lbl_humi = QLabel("--.- %")
        self.lbl_humi.setAlignment(Qt.AlignCenter)
        self.lbl_humi.setStyleSheet(self._get_sensor_display_style())
        mon_layout.addWidget(self.lbl_humi, 0, 1)
        
        self.lbl_sht_status = QLabel("SHT20: OFFLINE")
        self.lbl_sht_status.setStyleSheet(f"font-weight:bold; color:{COLOR_ERROR};")
        mon_layout.addWidget(self.lbl_sht_status, 1, 0, 1, 2)
        
        # Driver status
        self.lbl_pos = QLabel("Position: 0 pulse")
        self.lbl_pos.setStyleSheet("font-size:12pt; font-weight:bold;")
        mon_layout.addWidget(self.lbl_pos, 2, 0, 1, 2)
        
        self.lbl_drv_alarm = QLabel("Alarm: NO")
        self.lbl_drv_alarm.setStyleSheet(f"color:{COLOR_CONNECTED}; font-weight:bold;")
        mon_layout.addWidget(self.lbl_drv_alarm, 3, 0)
        
        self.lbl_drv_inpos = QLabel("InPos: NO")
        self.lbl_drv_inpos.setStyleSheet(f"color:{COLOR_WARNING}; font-weight:bold;")
        mon_layout.addWidget(self.lbl_drv_inpos, 3, 1)
        
        self.lbl_drv_run = QLabel("Running: NO")
        self.lbl_drv_run.setStyleSheet(f"color:{COLOR_NEUTRAL}; font-weight:bold;")
        mon_layout.addWidget(self.lbl_drv_run, 4, 0)
        
        # Counter status
        self.lbl_counter = QLabel("Counter: 0 / 0")
        self.lbl_counter.setStyleSheet("font-size:12pt; font-weight:bold;")
        mon_layout.addWidget(self.lbl_counter, 5, 0, 1, 2)
        
        self.lbl_counter_done = QLabel("Counter DONE: NO")
        self.lbl_counter_done.setStyleSheet(f"color:{COLOR_NEUTRAL}; font-weight:bold;")
        mon_layout.addWidget(self.lbl_counter_done, 6, 0, 1, 2)
        
        # AUTO state
        self.lbl_auto_state = QLabel("AUTO STATE: Idle")
        self.lbl_auto_state.setStyleSheet("font-size:12pt; font-weight:bold; color:#2c3e50;")
        mon_layout.addWidget(self.lbl_auto_state, 7, 0, 1, 2)
        
        # Mode info
        self.lbl_mode_info = QLabel("MODE: AUTO")
        self.lbl_mode_info.setStyleSheet(f"font-size:11pt; font-weight:bold; color:{COLOR_CONNECTED};")
        mon_layout.addWidget(self.lbl_mode_info, 8, 0, 1, 2)
        
        # TCP target
        self.lbl_tcp_target = QLabel("TCP Target: 0")
        self.lbl_tcp_target.setStyleSheet("font-size:11pt; font-weight:bold; color:#555555;")
        mon_layout.addWidget(self.lbl_tcp_target, 9, 0, 1, 2)
        
        mon_group.setLayout(mon_layout)
        return mon_group
    
    def _create_log_group(self) -> QGroupBox:
        """Tạo nhóm log"""
        log_group = QGroupBox("SYSTEM LOG")
        log_group.setStyleSheet(self._get_groupbox_style())
        
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("""
            background:#f5f5f5;
            color:#333333;
            font-family:'Consolas';
            font-size:9pt;
            border-radius:4px;
            border:1px solid #d0d0d0;
        """)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        return log_group
    
    @staticmethod
    def _get_groupbox_style() -> str:
        """Style cho QGroupBox"""
        return """
            QGroupBox {
                font-weight:bold;
                font-size:11pt;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
            }
        """
    
    @staticmethod
    def _get_button_style(secondary=False) -> str:
        """Style cho button"""
        if secondary:
            return """
                background:#f0f0f0;
                color:#555555;
                padding:4px 10px;
                border:1px solid #cccccc;
                border-radius:3px;
            """
        return """
            background:#e0e0e0;
            color:#333333;
            font-weight:bold;
            padding:4px 10px;
            border:1px solid #c0c0c0;
            border-radius:3px;
        """
    
    @staticmethod
    def _get_sensor_display_style() -> str:
        """Style cho hiển thị sensor"""
        return """
            background:#ffffff;
            color:#333333;
            font-size:16pt;
            padding:10px;
            border-radius:6px;
            border:1px solid #cccccc;
        """
    
    def connect_serial(self):
        """Kết nối serial"""
        if self.device_manager.is_connected():
            self.log("Already connected.")
            return
        
        port = self.combo_port.currentText()
        baud = int(self.combo_baud.currentText())
        
        success, message = self.device_manager.connect(port, baud)
        
        if success:
            self.lbl_serial_status.setText("Connected")
            self.lbl_serial_status.setStyleSheet(
                f"font-weight:bold; font-size:11pt; color:{COLOR_CONNECTED};"
            )
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.log(message)
        else:
            QMessageBox.critical(self, "Error", message)
            self.log(f"RS485 error: {message}")
    
    def disconnect_serial(self):
        """Ngắt kết nối serial"""
        self.device_manager.disconnect()
        self.lbl_serial_status.setText("Disconnected")
        self.lbl_serial_status.setStyleSheet(
            f"font-weight:bold; font-size:11pt; color:{COLOR_DISCONNECTED};"
        )
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.log("RS485 disconnected")
    
    def read_all_devices(self):
        """Đọc tất cả thiết bị"""
        self.device_manager.read_all_devices()
        self.update_ui()
        self.plc_controller.update_input_registers()
    
    def auto_cycle(self):
        """Chu kỳ AUTO"""
        self.plc_controller.auto_cycle()
        self.update_ui()
        self.plc_controller.update_input_registers()
    
    def update_ui(self):
        """Cập nhật giao diện"""
        dm = self.device_manager
        
        # SHT20
        self.lbl_temp.setText(f"{dm.temperature:.1f} °C")
        self.lbl_humi.setText(f"{dm.humidity:.1f} %")
        
        if dm.sht20_ok:
            self.lbl_sht_status.setText("SHT20: ONLINE")
            self.lbl_sht_status.setStyleSheet(f"font-weight:bold; color:{COLOR_CONNECTED};")
        else:
            self.lbl_sht_status.setText("SHT20: OFFLINE")
            self.lbl_sht_status.setStyleSheet(f"font-weight:bold; color:{COLOR_ERROR};")
        
        # Driver
        self.lbl_pos.setText(f"Position: {dm.current_position:,} pulse")
        
        if dm.driver_alarm:
            self.lbl_drv_alarm.setText("Alarm: YES")
            self.lbl_drv_alarm.setStyleSheet(f"color:{COLOR_ERROR}; font-weight:bold;")
        else:
            self.lbl_drv_alarm.setText("Alarm: NO")
            self.lbl_drv_alarm.setStyleSheet(f"color:{COLOR_CONNECTED}; font-weight:bold;")
        
        if dm.driver_inpos:
            self.lbl_drv_inpos.setText("InPos: YES")
            self.lbl_drv_inpos.setStyleSheet(f"color:{COLOR_CONNECTED}; font-weight:bold;")
        else:
            self.lbl_drv_inpos.setText("InPos: NO")
            self.lbl_drv_inpos.setStyleSheet(f"color:{COLOR_WARNING}; font-weight:bold;")
        
        if dm.driver_running:
            self.lbl_drv_run.setText("Running: YES")
            self.lbl_drv_run.setStyleSheet(f"color:{COLOR_INFO}; font-weight:bold;")
        else:
            self.lbl_drv_run.setText("Running: NO")
            self.lbl_drv_run.setStyleSheet(f"color:{COLOR_NEUTRAL}; font-weight:bold;")
        
        # Counter
        self.lbl_counter.setText(f"Counter: {dm.counter_value} / {dm.counter_target}")
        
        if dm.counter_done:
            self.lbl_counter_done.setText("Counter DONE: YES")
            self.lbl_counter_done.setStyleSheet(f"color:{COLOR_CONNECTED}; font-weight:bold;")
        else:
            self.lbl_counter_done.setText("Counter DONE: NO")
            self.lbl_counter_done.setStyleSheet(f"color:{COLOR_NEUTRAL}; font-weight:bold;")
        
        # AUTO state
        self.lbl_auto_state.setText(f"AUTO STATE: {self.plc_controller.motor_state}")
        self.lbl_tcp_target.setText(f"TCP Target: {self.plc_controller.last_tcp_target}")
        
        # Mode
        mode = self.plc_controller.get_mode()
        if mode == 1:
            self.lbl_mode_info.setText("MODE: MANUAL")
            self.lbl_mode_info.setStyleSheet(f"font-size:11pt; font-weight:bold; color:{COLOR_WARNING};")
        else:
            self.lbl_mode_info.setText("MODE: AUTO")
            self.lbl_mode_info.setStyleSheet(f"font-size:11pt; font-weight:bold; color:{COLOR_CONNECTED};")
    
    def log(self, msg: str):
        """Ghi log"""
        ts = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {msg}")
    
    def append_log(self, msg: str):
        """Append log từ signal"""
        self.log(msg)
    
    def update_tcp_status(self, text: str):
        """Cập nhật trạng thái TCP"""
        self.lbl_tcp_status.setText(text)
        if "Listening" in text or "listening" in text:
            self.lbl_tcp_status.setStyleSheet(f"font-weight:bold; font-size:11pt; color:{COLOR_CONNECTED};")
        elif "error" in text.lower():
            self.lbl_tcp_status.setStyleSheet(f"font-weight:bold; font-size:11pt; color:{COLOR_ERROR};")
        else:
            self.lbl_tcp_status.setStyleSheet(f"font-weight:bold; font-size:11pt; color:{COLOR_WARNING};")
    
    def closeEvent(self, event):
        """Xử lý đóng cửa sổ"""
        self.timer_read.stop()
        self.timer_auto.stop()
        self.device_manager.disconnect()
        self.plc_controller.stop_modbus_server()
        event.accept()


def main():
    """Hàm main"""
    app = QApplication(sys.argv)
    gui = LayerA_PLC()
    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()