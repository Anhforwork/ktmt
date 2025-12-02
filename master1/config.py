# =========================================
# CẤU HÌNH
# =========================================

# Layer A Modbus Configuration
A_HOST = "192.168.1.220"  # Địa chỉ từ ảnh SLAVE LAYER
A_MODBUS_PORT = 502  # Port từ ảnh SLAVE LAYER

# Layer C TCP Server Configuration
SERVER_PORT = 5002
BUFFER_SIZE = 4096

# Modbus Register Addresses
A_HR_MODE_ADDR = 8
A_HR_CMD_ADDR = 10
A_HR_CMD_REG_COUNT = 6

# Auto State Mapping
AUTO_STATE_MAP = {
    0: "Idle",
    1: "Waiting count",
    2: "Motor running",
    3: "Waiting reset",
    4: "Alarm",
    5: "Timeout motor",
    6: "Disabled",
    7: "Waiting target",
    8: "Manual",
}