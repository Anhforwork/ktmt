# slave/device_tester.py
"""
Device connection tester for SHT20 and Driver
"""
from serial_handler import SerialHandler
from logger import EventLogger, LogComponent
from modbus_rtu import (
    build_fc03, build_fc04, verify_crc, 
    unpack_s32_from_bytes, bytes_to_hex
)
import config


class DeviceTester:
    def __init__(self, serial_handler: SerialHandler, logger: EventLogger):
        self.serial = serial_handler
        self.logger = logger
        
        # SHT20 State
        self.sht20_online = False
        self.temperature = 0.0
        self.humidity = 0.0
        
        # Driver State
        self.driver_online = False
        self.position = 0
        self.driver_alarm = False
        self.driver_inpos = False
        self.driver_running = False
        
    def test_sht20(self) -> bool:
        """Test SHT20 sensor connection"""
        frame = build_fc04(
            config.SLAVE_ID_SHT20,
            config.SHT20_REG_START,
            config.SHT20_REG_COUNT
        )
        
        resp = self.serial.send_frame(frame, LogComponent.SENSOR)
        
        if len(resp) >= 9 and resp[1] == 0x04:
            if verify_crc(resp):
                try:
                    self.temperature = ((resp[3] << 8) | resp[4]) / 10.0
                    self.humidity = ((resp[5] << 8) | resp[6]) / 10.0
                    self.sht20_online = True
                    
                    self.logger.info(
                        LogComponent.SENSOR,
                        f"SHT20 OK - Temp: {self.temperature:.1f}°C, Humi: {self.humidity:.1f}%"
                    )
                    return True
                    
                except Exception as e:
                    self.logger.error(LogComponent.SENSOR, f"Parse error: {e}")
                    self.sht20_online = False
                    return False
            else:
                self.logger.error(LogComponent.SENSOR, "CRC mismatch")
                self.sht20_online = False
                return False
        else:
            self.logger.warn(LogComponent.SENSOR, f"Invalid response (len={len(resp)})")
            self.sht20_online = False
            return False
    
    def test_driver_position(self) -> bool:
        """Test driver position reading"""
        frame = build_fc03(
            config.SLAVE_ID_DRIVER,
            config.DRIVER_REG_POSITION,
            config.DRIVER_REG_POSITION_COUNT
        )
        
        resp = self.serial.send_frame(frame, LogComponent.DRIVER)
        
        if len(resp) >= 9 and resp[1] == 0x03:
            if verify_crc(resp):
                try:
                    self.position = unpack_s32_from_bytes(resp, 3)
                    self.logger.info(
                        LogComponent.DRIVER,
                        f"Position read OK - {self.position:,} pulse"
                    )
                    return True
                    
                except Exception as e:
                    self.logger.error(LogComponent.DRIVER, f"Parse position error: {e}")
                    return False
            else:
                self.logger.error(LogComponent.DRIVER, "Position CRC mismatch")
                return False
        else:
            self.logger.warn(LogComponent.DRIVER, f"Position invalid response (len={len(resp)})")
            return False
    
    def test_driver_status(self) -> bool:
        """Test driver status reading"""
        frame = build_fc03(
            config.SLAVE_ID_DRIVER,
            config.DRIVER_REG_STATUS,
            config.DRIVER_REG_STATUS_COUNT
        )
        
        resp = self.serial.send_frame(frame, LogComponent.DRIVER)
        
        if len(resp) >= 7 and resp[1] == 0x03:
            if verify_crc(resp):
                try:
                    sw = (resp[3] << 8) | resp[4]
                    self.driver_alarm = bool((sw >> 8) & 0x01)
                    self.driver_inpos = bool((sw >> 4) & 0x01)
                    self.driver_running = bool((sw >> 2) & 0x01)
                    
                    self.driver_online = True
                    
                    status_str = f"Alarm:{self.driver_alarm} InPos:{self.driver_inpos} Run:{self.driver_running}"
                    self.logger.info(LogComponent.DRIVER, f"Status OK - {status_str}")
                    return True
                    
                except Exception as e:
                    self.logger.error(LogComponent.DRIVER, f"Parse status error: {e}")
                    self.driver_online = False
                    return False
            else:
                self.logger.error(LogComponent.DRIVER, "Status CRC mismatch")
                self.driver_online = False
                return False
        else:
            self.logger.warn(LogComponent.DRIVER, f"Status invalid response (len={len(resp)})")
            self.driver_online = False
            return False
    
    def test_all_devices(self):
        """Test all devices"""
        if not self.serial.is_connected:
            self.logger.error(LogComponent.SYSTEM, "Serial not connected")
            return
        
        self.logger.info(LogComponent.SYSTEM, "=== Starting device test ===")
        
        # Test SHT20
        self.test_sht20()
        
        # Test Driver
        pos_ok = self.test_driver_position()
        status_ok = self.test_driver_status()
        
        # Summary
        if self.sht20_online:
            self.logger.info(LogComponent.SYSTEM, "✓ SHT20 sensor ONLINE")
        else:
            self.logger.warn(LogComponent.SYSTEM, "✗ SHT20 sensor OFFLINE")
        
        if pos_ok and status_ok:
            self.logger.info(LogComponent.SYSTEM, "✓ Driver ONLINE")
        else:
            self.logger.warn(LogComponent.SYSTEM, "✗ Driver OFFLINE or partial")
        
        self.logger.info(LogComponent.SYSTEM, "=== Test completed ===")
    
    def get_device_status(self) -> dict:
        """Get current device status"""
        return {
            'sht20': {
                'online': self.sht20_online,
                'temperature': self.temperature,
                'humidity': self.humidity
            },
            'driver': {
                'online': self.driver_online,
                'position': self.position,
                'alarm': self.driver_alarm,
                'inpos': self.driver_inpos,
                'running': self.driver_running
            }
        }