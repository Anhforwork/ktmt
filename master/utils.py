from PyQt5.QtCore import QObject, pyqtSignal
from config import AUTO_STATE_MAP


class SignalEmitter(QObject):
    log_signal = pyqtSignal(str)
    status_update = pyqtSignal(dict)
    connection_signal = pyqtSignal(str, str)
    forward_signal = pyqtSignal(str)


def regs_to_s32(hi, lo):
    """Convert two 16-bit registers to signed 32-bit integer"""
    val = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
    if val & 0x80000000:
        val = val - (1 << 32)
    return val


def s32_to_regs(val):
    """Convert signed 32-bit integer to two 16-bit registers"""
    if val < 0:
        val = (1 << 32) + val
    hi = (val >> 16) & 0xFFFF
    lo = val & 0xFFFF
    return hi, lo


def validate_pos_speed(pos: int, speed: int) -> bool:
    """Validate position and speed values"""
    if abs(pos) > 2_000_000_000:
        return False
    if speed < 1 or speed > 200_000:
        return False
    return True