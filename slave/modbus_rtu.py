# slave/modbus_rtu.py
"""
Modbus RTU protocol functions
"""

def crc16_modbus(data: bytes) -> int:
    """Calculate Modbus CRC16"""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def verify_crc(resp: bytes) -> bool:
    """Verify CRC of response frame"""
    if len(resp) < 5:
        return False
    data = resp[:-2]
    recv_crc = resp[-2] | (resp[-1] << 8)
    calc_crc = crc16_modbus(data)
    return recv_crc == calc_crc


def build_fc03(slave_id: int, start_reg: int, count: int) -> bytes:
    """Build Function Code 03 (Read Holding Registers)"""
    data = bytes([
        slave_id, 0x03,
        (start_reg >> 8) & 0xFF, start_reg & 0xFF,
        (count >> 8) & 0xFF, count & 0xFF
    ])
    crc = crc16_modbus(data)
    return data + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def build_fc04(slave_id: int, start_reg: int, count: int) -> bytes:
    """Build Function Code 04 (Read Input Registers)"""
    data = bytes([
        slave_id, 0x04,
        (start_reg >> 8) & 0xFF, start_reg & 0xFF,
        (count >> 8) & 0xFF, count & 0xFF
    ])
    crc = crc16_modbus(data)
    return data + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def build_fc06(slave_id: int, reg_addr: int, reg_val: int) -> bytes:
    """Build Function Code 06 (Write Single Register)"""
    data = bytes([
        slave_id, 0x06,
        (reg_addr >> 8) & 0xFF, reg_addr & 0xFF,
        (reg_val >> 8) & 0xFF, reg_val & 0xFF
    ])
    crc = crc16_modbus(data)
    return data + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def bytes_to_hex(data: bytes) -> str:
    """Convert bytes to hex string for logging"""
    return ' '.join([f'{b:02X}' for b in data])


def unpack_s32_from_bytes(b: bytes, offset: int) -> int:
    """Unpack signed 32-bit from bytes"""
    val = (b[offset] << 24) | (b[offset+1] << 16) | (b[offset+2] << 8) | b[offset+3]
    if val & 0x80000000:
        val = val - (1 << 32)
    return val