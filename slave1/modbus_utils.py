# modbus_utils.py
"""
Modbus RTU Helper Functions
"""


def crc16_modbus(data: bytes) -> int:
    """Tính CRC16 cho Modbus RTU"""
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
    """Kiểm tra CRC của response"""
    if len(resp) < 5:
        return False
    data = resp[:-2]
    recv_crc = resp[-2] | (resp[-1] << 8)
    calc_crc = crc16_modbus(data)
    return recv_crc == calc_crc


def build_fc03(slave_id: int, start_reg: int, count: int) -> bytes:
    """Build Function Code 03 - Read Holding Registers"""
    data = bytes([
        slave_id, 0x03,
        (start_reg >> 8) & 0xFF, start_reg & 0xFF,
        (count >> 8) & 0xFF, count & 0xFF
    ])
    crc = crc16_modbus(data)
    return data + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def build_fc04(slave_id: int, start_reg: int, count: int) -> bytes:
    """Build Function Code 04 - Read Input Registers"""
    data = bytes([
        slave_id, 0x04,
        (start_reg >> 8) & 0xFF, start_reg & 0xFF,
        (count >> 8) & 0xFF, count & 0xFF
    ])
    crc = crc16_modbus(data)
    return data + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def build_fc06(slave_id: int, reg_addr: int, reg_val: int) -> bytes:
    """Build Function Code 06 - Write Single Register"""
    data = bytes([
        slave_id, 0x06,
        (reg_addr >> 8) & 0xFF, reg_addr & 0xFF,
        (reg_val >> 8) & 0xFF, reg_val & 0xFF
    ])
    crc = crc16_modbus(data)
    return data + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def build_fc16(slave_id: int, start_reg: int, registers: list) -> bytes:
    """Build Function Code 16 - Write Multiple Registers"""
    reg_count = len(registers)
    byte_count = reg_count * 2
    data = bytearray([
        slave_id, 0x10,
        (start_reg >> 8) & 0xFF, start_reg & 0xFF,
        (reg_count >> 8) & 0xFF, reg_count & 0xFF,
        byte_count
    ])
    for reg in registers:
        data.append((reg >> 8) & 0xFF)
        data.append(reg & 0xFF)
    crc = crc16_modbus(bytes(data))
    return bytes(data) + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def pack_u32(val: int) -> list:
    """Pack unsigned 32-bit value to 2 registers"""
    return [(val >> 16) & 0xFFFF, val & 0xFFFF]


def pack_s32(val: int) -> list:
    """Pack signed 32-bit value to 2 registers"""
    if val < 0:
        val = (1 << 32) + val
    return [(val >> 16) & 0xFFFF, val & 0xFFFF]


def unpack_s32_from_bytes(b: bytes, offset: int) -> int:
    """Unpack signed 32-bit value from bytes"""
    val = (b[offset] << 24) | (b[offset+1] << 16) | (b[offset+2] << 8) | b[offset+3]
    if val & 0x80000000:
        val = val - (1 << 32)
    return val