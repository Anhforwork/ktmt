# device_manager.py
"""
Device Manager - Quản lý giao tiếp với các thiết bị qua Modbus RTU
"""

import time
import serial
import threading

from modbus_utils import (
    build_fc03, build_fc04, build_fc06, build_fc16,
    verify_crc, unpack_s32_from_bytes, pack_s32, pack_u32
)
from config import (
    SLAVE_ID_DRIVER, SLAVE_ID_SHT20, SLAVE_ID_COUNTER,
    SERIAL_TIMEOUT
)


class DeviceManager:
    """Quản lý giao tiếp với Driver, SHT20, Counter Arduino"""
    
    def __init__(self):
        self.ser = None
        self.ser_lock = threading.Lock()
        
        # Driver state
        self.current_position = 0
        self.current_speed = 0
        self.driver_alarm = False
        self.driver_inpos = False
        self.driver_running = False
        
        # SHT20
        self.temperature = 0.0
        self.humidity = 0.0
        self.sht20_ok = False
        
        # Counter Arduino
        self.counter_value = 0
        self.counter_target = 0
        self.counter_done = False
    
    def connect(self, port: str, baudrate: int) -> tuple:
        """
        Kết nối serial port
        Returns: (success: bool, message: str)
        """
        if self.ser and self.ser.is_open:
            return False, "Already connected"
        
        try:
            self.ser = serial.Serial(port, baudrate=baudrate, timeout=SERIAL_TIMEOUT)
            time.sleep(0.1)
            return True, f"Connected to {port} @ {baudrate}"
        except Exception as e:
            return False, f"Cannot connect: {e}"
    
    def disconnect(self):
        """Ngắt kết nối serial"""
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
            self.ser = None
    
    def is_connected(self) -> bool:
        """Kiểm tra trạng thái kết nối"""
        return self.ser is not None and self.ser.is_open
    
    def send_frame(self, frame: bytes) -> bytes:
        """Gửi frame và nhận response"""
        if not self.is_connected():
            return b""
        
        with self.ser_lock:
            try:
                self.ser.reset_input_buffer()
                self.ser.write(frame)
                self.ser.flush()
                time.sleep(0.02)
                
                resp = b""
                start = time.time()
                while time.time() - start < SERIAL_TIMEOUT:
                    chunk = self.ser.read(256)
                    if chunk:
                        resp += chunk
                        time.sleep(0.03)
                    else:
                        if resp:
                            break
                        time.sleep(0.01)
                return resp
            except Exception as e:
                print(f"Serial error: {e}")
                return b""
    
    def read_driver_position(self) -> bool:
        """Đọc vị trí hiện tại của driver"""
        frame = build_fc03(SLAVE_ID_DRIVER, 0x1000, 2)
        resp = self.send_frame(frame)
        if len(resp) >= 9 and resp[1] == 0x03 and verify_crc(resp):
            try:
                self.current_position = unpack_s32_from_bytes(resp, 3)
                return True
            except:
                pass
        return False
    
    def read_driver_status(self) -> bool:
        """Đọc trạng thái driver"""
        frame = build_fc03(SLAVE_ID_DRIVER, 0x1010, 1)
        resp = self.send_frame(frame)
        if len(resp) >= 7 and resp[1] == 0x03 and verify_crc(resp):
            sw = (resp[3] << 8) | resp[4]
            self.driver_alarm = bool((sw >> 8) & 0x01)
            self.driver_inpos = bool((sw >> 4) & 0x01)
            self.driver_running = bool((sw >> 2) & 0x01)
            return True
        return False
    
    def read_sht20(self) -> bool:
        """Đọc cảm biến nhiệt độ và độ ẩm SHT20"""
        frame = build_fc04(SLAVE_ID_SHT20, 0x0001, 2)
        resp = self.send_frame(frame)
        if len(resp) >= 9 and resp[1] == 0x04 and verify_crc(resp):
            try:
                self.temperature = ((resp[3] << 8) | resp[4]) / 10.0
                self.humidity = ((resp[5] << 8) | resp[6]) / 10.0
                self.sht20_ok = True
                return True
            except:
                self.sht20_ok = False
        else:
            self.sht20_ok = False
        return False
    
    def read_counter(self) -> bool:
        """Đọc counter Arduino"""
        frame = build_fc03(SLAVE_ID_COUNTER, 0x0000, 4)
        resp = self.send_frame(frame)
        if len(resp) >= 13 and resp[1] == 0x03 and verify_crc(resp):
            hr0 = (resp[3] << 8) | resp[4]
            hr1 = (resp[5] << 8) | resp[6]
            hr2 = (resp[7] << 8) | resp[8]
            self.counter_value = hr0
            self.counter_target = hr1
            self.counter_done = bool(hr2 & 0x0001)
            return True
        return False
    
    def read_all_devices(self):
        """Đọc tất cả thiết bị"""
        self.read_driver_position()
        time.sleep(0.01)
        self.read_driver_status()
        time.sleep(0.01)
        self.read_sht20()
        time.sleep(0.01)
        self.read_counter()
    
    def set_counter_target(self, target: int) -> bool:
        """Gửi target xuống Arduino"""
        frame = build_fc06(SLAVE_ID_COUNTER, 0x0001, target)
        resp = self.send_frame(frame)
        return resp and len(resp) >= 8
    
    def reset_counter(self) -> bool:
        """Reset counter Arduino (HR3 = 1)"""
        frame = build_fc06(SLAVE_ID_COUNTER, 0x0003, 1)
        resp = self.send_frame(frame)
        return resp and len(resp) >= 8
    
    def motor_step_on(self) -> bool:
        """Bật motor step"""
        frame = build_fc06(SLAVE_ID_DRIVER, 0x0000, 1)
        resp = self.send_frame(frame)
        return bool(resp)
    
    def motor_step_off(self) -> bool:
        """Tắt motor step"""
        frame = build_fc06(SLAVE_ID_DRIVER, 0x0000, 0)
        resp = self.send_frame(frame)
        return bool(resp)
    
    def motor_move_absolute(self, position: int, speed: int) -> bool:
        """Di chuyển motor tới vị trí tuyệt đối"""
        if speed < 0:
            speed = 0
        if speed > 0xFFFFFFFF:
            speed = 0xFFFFFFFF
        
        frame = build_fc16(
            SLAVE_ID_DRIVER,
            0x20,
            pack_s32(position) + pack_u32(speed)
        )
        resp = self.send_frame(frame)
        return bool(resp)
    
    def motor_jog_cw(self, speed: int) -> bool:
        """Chạy motor tốc độ CW (clockwise)"""
        if speed < 0:
            speed = 0
        if speed > 0xFFFFFFFF:
            speed = 0xFFFFFFFF
        
        frame = build_fc16(
            SLAVE_ID_DRIVER,
            0x0030,
            pack_u32(speed) + [0, 1]  # dir=1 (CW)
        )
        resp = self.send_frame(frame)
        return bool(resp)
    
    def motor_jog_ccw(self, speed: int) -> bool:
        """Chạy motor tốc độ CCW (counter-clockwise)"""
        if speed < 0:
            speed = 0
        if speed > 0xFFFFFFFF:
            speed = 0xFFFFFFFF
        
        frame = build_fc16(
            SLAVE_ID_DRIVER,
            0x0030,
            pack_u32(speed) + [0, 0]  # dir=0 (CCW)
        )
        resp = self.send_frame(frame)
        return bool(resp)
    
    def motor_stop(self) -> bool:
        """Dừng motor"""
        frame = build_fc06(SLAVE_ID_DRIVER, 0x0002, 1)
        resp = self.send_frame(frame)
        return bool(resp)
    
    def motor_reset_alarm(self) -> bool:
        """Reset alarm của driver"""
        frame = build_fc06(SLAVE_ID_DRIVER, 0x0001, 1)
        resp = self.send_frame(frame)
        return bool(resp)