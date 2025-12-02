# config.py
"""
Cấu hình hệ thống PLC
"""

# ==========================
# CẤU HÌNH HỆ THỐNG
# ==========================

# Modbus TCP
MODBUS_TCP_PORT = 502

# Serial / RS485
SERIAL_TIMEOUT = 1.0
READ_INTERVAL_MS = 300

# Slave IDs
SLAVE_ID_DRIVER = 2
SLAVE_ID_SHT20 = 1
SLAVE_ID_COUNTER = 3

# Tham số auto chạy motor
AUTO_MOVE_PULSES = 5000
AUTO_MOVE_SPEED = 8000

# Holding Register Map
HR_TARGET_ADDR = 0        # B/C ghi target counter (A → Arduino)
HR_MODE_ADDR = 8          # 0=AUTO, 1=MANUAL
HR_CMD_ADDR = 10          # packet lệnh MANUAL từ B/C
HR_CMD_REG_COUNT = 6      # CMD, POS_HI, POS_LO, SPEED, SOURCE, PRIORITY

# Auto state mapping
AUTO_STATE_MAP = {
    "Idle": 0,
    "Waiting count": 1,
    "Motor running": 2,
    "Waiting reset": 3,
    "Alarm": 4,
    "Timeout motor": 5,
    "Disabled": 6,
    "Waiting target": 7,
    "Manual": 8,
}

# UI Colors
COLOR_CONNECTED = "#27ae60"
COLOR_DISCONNECTED = "#777777"
COLOR_ERROR = "#c0392b"
COLOR_WARNING = "#e67e22"
COLOR_INFO = "#3498db"
COLOR_NEUTRAL = "#95a5a6"