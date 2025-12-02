# slave/config.py
"""
Configuration constants for the slave layer
"""

# Serial Communication
SERIAL_TIMEOUT = 1.0
READ_INTERVAL_MS = 1000  # Ping interval

# Modbus Slave IDs
SLAVE_ID_SHT20 = 1
SLAVE_ID_DRIVER = 2

# SHT20 Sensor
SHT20_REG_START = 0x0001
SHT20_REG_COUNT = 2

# Driver Registers
DRIVER_REG_POSITION = 0x1000
DRIVER_REG_POSITION_COUNT = 2
DRIVER_REG_STATUS = 0x1010
DRIVER_REG_STATUS_COUNT = 1

# Log Settings
LOG_MAX_LINES = 200
LOG_EXPORT_PATH = "slave_log.txt"

# Available COM Ports
AVAILABLE_PORTS = ["COM11", "COM3", "COM14", "COM5", "COM6", "COM7"]
AVAILABLE_BAUDS = ["9600", "19200", "38400", "57600", "115200"]