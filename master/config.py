# master/config.py
"""
Configuration for Master Layer (SCADA Client)
"""

# Slave (Server) Connection
SLAVE_HOST = "192.168.0.121"
SLAVE_MODBUS_PORT = 502
MODBUS_TIMEOUT = 3.0
POLL_INTERVAL_MS = 500  # Status polling interval

# Holding Register Map (same as Slave)
HR_TARGET_ADDR = 0        # Target counter
HR_MODE_ADDR = 8          # 0=AUTO, 1=MANUAL
HR_CMD_ADDR = 10          # Command packet
HR_CMD_REG_COUNT = 6      # CMD, POS_HI, POS_LO, SPEED, SOURCE, PRIORITY

# Input Register Map (Status from Slave)
IR_POS_HI = 0
IR_POS_LO = 1
IR_SPEED = 2
IR_TEMP = 3
IR_HUMI = 4
IR_STATUS_WORD = 5
IR_COUNTER_VALUE = 6
IR_COUNTER_TARGET = 7
IR_AUTO_STATE = 8
IR_MODE = 9
IR_STEP_STATE = 10
IR_JOG_STATE = 11

# Command Codes
CMD_STEP_ON = 1
CMD_STEP_OFF = 2
CMD_MOVE_ABS = 3
CMD_JOG_CW = 5
CMD_JOG_CCW = 6
CMD_STOP = 7
CMD_RESET_ALARM = 8
CMD_EMERGENCY = 9

# Source Codes
SOURCE_MASTER = 2
SOURCE_PRIORITY = 2

# Auto State Map
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

# Log Settings
LOG_MAX_LINES = 200