"""
Configuration for Layer B SCADA Supervisor.

Keep these values aligned with Layer A register map.
"""

# ========= Network =========
A_HOST = "192.168.0.121"
A_MODBUS_PORT = 502

SERVER_PORT = 5002
BUFFER_SIZE = 4096

# ========= Layer A Holding Register map =========
A_HR_TARGET_ADDR = 0
A_HR_MODE_ADDR = 8
A_HR_CMD_ADDR = 10
A_HR_CMD_REG_COUNT = 6

# ========= Input Register map (Layer A -> Layer B) =========
# Read IR 0..11 (12 regs):
# 0: pos_hi, 1: pos_lo, 2: speed, 3: temp*10, 4: humi*10, 5: status_word,
# 6: cnt_val, 7: cnt_target, 8: auto_code, 9: mode, 10: step_state, 11: jog_state
A_IR_BASE_ADDR = 0
A_IR_COUNT = 12

# ========= Process state text =========
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

# ========= Motor/Control limits =========
POS_MIN = -2_000_000_000
POS_MAX =  2_000_000_000
SPEED_MIN = 1
SPEED_MAX = 200_000

TARGET_MIN = 1
TARGET_MAX = 65535
