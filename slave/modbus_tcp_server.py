"""
Modbus TCP Server - Mô phỏng PLC/Slave với SHT20 Sensor và EZi-STEP Drive
Sử dụng pymodbus.server
"""
import threading
import time
import random
from datetime import datetime
from pymodbus.server import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.exceptions import ModbusException

from .logger_handler import logger
from .config import DEVICE_SENSOR, DEVICE_DRIVE


class ModbusTCPServer:
    """Modbus TCP Server sử dụng pymodbus"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 502):
        self.host = host
        self.port = port
        self.server_thread = None
        self.context = None
        self.running = False
        
        # Statistics
        self.request_count = 0
        self.response_count = 0
        self.error_count = 0
        self.start_time = None
        
        # Initialize data stores
        self._init_datastore()
    
    def _init_datastore(self):
        """Khởi tạo datastore cho các slave devices"""
        
        # ===== SLAVE 1: SHT20 Sensor =====
        # Input Registers (FC04): 0x0001-0x0002
        # Temperature @ 0x0001, Humidity @ 0x0002
        sensor_ir = ModbusSequentialDataBlock(0x0000, [0] * 100)  # 100 input registers
        sensor_hr = ModbusSequentialDataBlock(0x0000, [0] * 100)  # 100 holding registers
        sensor_di = ModbusSequentialDataBlock(0x0000, [0] * 100)  # 100 discrete inputs
        sensor_co = ModbusSequentialDataBlock(0x0000, [0] * 100)  # 100 coils
        
        slave1_context = ModbusSlaveContext(
            di=sensor_di,
            co=sensor_co,
            hr=sensor_hr,
            ir=sensor_ir
        )
        
        # ===== SLAVE 2: EZi-STEP Drive =====
        # Holding Registers (FC03):
        # 0x0000: Step ON/OFF
        # 0x0001: Alarm Reset
        # 0x0002: Stop
        # 0x0010-0x0013: Absolute Move (Position + Speed)
        # 0x0020-0x0023: Incremental Move (Offset + Speed)
        # 0x0030-0x0033: JOG (Speed + Direction)
        # 0x1000-0x1001: Current Position
        # 0x1010: Status Word
        drive_hr = ModbusSequentialDataBlock(0x0000, [0] * 0x2000)  # Large register space
        drive_ir = ModbusSequentialDataBlock(0x0000, [0] * 100)
        drive_di = ModbusSequentialDataBlock(0x0000, [0] * 100)
        drive_co = ModbusSequentialDataBlock(0x0000, [0] * 100)
        
        slave2_context = ModbusSlaveContext(
            di=drive_di,
            co=drive_co,
            hr=drive_hr,
            ir=drive_ir
        )
        
        # Create server context với 2 slaves
        self.context = ModbusServerContext(
            slaves={
                DEVICE_SENSOR["slave_id"]: slave1_context,
                DEVICE_DRIVE["slave_id"]: slave2_context
            },
            single=False
        )
        
        logger.info("Datastore initialized for 2 slaves", "SERVER")
        
        # Set initial values
        self._set_initial_values()
    
    def _set_initial_values(self):
        """Đặt giá trị ban đầu cho registers"""
        # Sensor: Initial temp=25.0°C, humi=50.0%
        slave1 = self.context[DEVICE_SENSOR["slave_id"]]
        slave1.setValues(4, 0x0001, [250, 500])  # FC04: Input Registers
        
        # Drive: Initial position=0, status=0x0010 (InPos)
        slave2 = self.context[DEVICE_DRIVE["slave_id"]]
        slave2.setValues(3, 0x1000, [0, 0])  # Position = 0
        slave2.setValues(3, 0x1010, [0x0010])  # Status = InPos
        
        logger.info("Initial values set", "SERVER")
    
    def start(self) -> bool:
        """Khởi động server"""
        try:
            # Device identification
            identity = ModbusDeviceIdentification()
            identity.VendorName = 'VN IoT Lab'
            identity.ProductCode = 'MODBUS-SIM'
            identity.VendorUrl = 'https://github.com/vniotlab'
            identity.ProductName = 'Modbus TCP Server Simulator'
            identity.ModelName = 'SHT20 + EZi-STEP'
            identity.MajorMinorRevision = '1.0.0'
            
            # Start server in separate thread
            self.server_thread = threading.Thread(
                target=self._run_server,
                args=(identity,),
                daemon=True
            )
            self.server_thread.start()
            
            self.running = True
            self.start_time = datetime.now()
            
            time.sleep(0.5)  # Wait for server to start
            
            logger.info(f"Modbus TCP Server started on {self.host}:{self.port}", "SERVER")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}", "SERVER")
            return False
    
    def _run_server(self, identity):
        """Chạy server (blocking)"""
        try:
            StartTcpServer(
                context=self.context,
                identity=identity,
                address=(self.host, self.port),
                allow_reuse_address=True
            )
        except Exception as e:
            logger.error(f"Server error: {e}", "SERVER")
            self.running = False
    
    def stop(self):
        """Dừng server"""
        self.running = False
        logger.info("Server stopped", "SERVER")
    
    def get_context(self):
        """Lấy server context để truy cập registers"""
        return self.context
    
    def get_stats(self) -> dict:
        """Lấy thống kê server"""
        uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        return {
            "running": self.running,
            "host": self.host,
            "port": self.port,
            "uptime_seconds": uptime,
            "request_count": self.request_count,
            "response_count": self.response_count,
            "error_count": self.error_count
        }
    
    def read_sensor_data(self) -> dict:
        """Đọc dữ liệu sensor từ datastore"""
        try:
            slave = self.context[DEVICE_SENSOR["slave_id"]]
            values = slave.getValues(4, 0x0001, 2)  # FC04: Input Registers
            
            temp_raw = values[0]
            humi_raw = values[1]
            
            # Convert to signed if needed
            if temp_raw & 0x8000:
                temp_raw = temp_raw - (1 << 16)
            if humi_raw & 0x8000:
                humi_raw = humi_raw - (1 << 16)
            
            return {
                "temperature_c": temp_raw / 10.0,
                "humidity_percent": humi_raw / 10.0,
                "raw_temp": temp_raw,
                "raw_humi": humi_raw
            }
        except Exception as e:
            logger.error(f"Failed to read sensor data: {e}", "SERVER")
            return {}
    
    def write_sensor_data(self, temp_c: float, humi_percent: float):
        """Ghi dữ liệu sensor vào datastore"""
        try:
            slave = self.context[DEVICE_SENSOR["slave_id"]]
            
            temp_raw = int(temp_c * 10)
            humi_raw = int(humi_percent * 10)
            
            # Convert to unsigned 16-bit
            if temp_raw < 0:
                temp_raw = (1 << 16) + temp_raw
            if humi_raw < 0:
                humi_raw = (1 << 16) + humi_raw
            
            slave.setValues(4, 0x0001, [temp_raw, humi_raw])
            
            logger.debug(f"Sensor updated: {temp_c:.1f}°C, {humi_percent:.1f}%", "SERVER")
            
        except Exception as e:
            logger.error(f"Failed to write sensor data: {e}", "SERVER")
    
    def read_drive_status(self) -> dict:
        """Đọc trạng thái drive"""
        try:
            slave = self.context[DEVICE_DRIVE["slave_id"]]
            
            # Read position (2 registers)
            pos_regs = slave.getValues(3, 0x1000, 2)
            pos = (pos_regs[0] << 16) | pos_regs[1]
            if pos & 0x80000000:
                pos = pos - (1 << 32)
            
            # Read status word
            status_word = slave.getValues(3, 0x1010, 1)[0]
            
            alarm = bool(status_word & 0x8000)
            inpos = bool(status_word & 0x0010)
            running = bool(status_word & 0x0004)
            step_on = bool(status_word & 0x0001)
            
            return {
                "position": pos,
                "status_word": status_word,
                "alarm": alarm,
                "in_position": inpos,
                "running": running,
                "step_on": step_on
            }
        except Exception as e:
            logger.error(f"Failed to read drive status: {e}", "SERVER")
            return {}
    
    def write_drive_position(self, position: int):
        """Ghi vị trí drive"""
        try:
            slave = self.context[DEVICE_DRIVE["slave_id"]]
            
            # Convert to unsigned 32-bit
            if position < 0:
                position = (1 << 32) + position
            
            hi = (position >> 16) & 0xFFFF
            lo = position & 0xFFFF
            
            slave.setValues(3, 0x1000, [hi, lo])
            
            logger.debug(f"Drive position updated: {position}", "SERVER")
            
        except Exception as e:
            logger.error(f"Failed to write drive position: {e}", "SERVER")
    
    def write_drive_status(self, status_word: int):
        """Ghi status word của drive"""
        try:
            slave = self.context[DEVICE_DRIVE["slave_id"]]
            slave.setValues(3, 0x1010, [status_word])
            
            logger.debug(f"Drive status updated: 0x{status_word:04X}", "SERVER")
            
        except Exception as e:
            logger.error(f"Failed to write drive status: {e}", "SERVER")


class ServerSimulator:
    """Simulator để tự động cập nhật dữ liệu sensor và drive"""
    
    def __init__(self, server: ModbusTCPServer):
        self.server = server
        self.running = False
        self.thread = None
        
        # Simulation parameters
        self.temp_base = 25.0
        self.humi_base = 50.0
        self.position = 0
        self.target_position = 0
        self.velocity = 0
        self.step_on = False
    
    def start(self):
        """Bắt đầu simulator"""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("Simulator started", "SIMULATOR")
    
    def stop(self):
        """Dừng simulator"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("Simulator stopped", "SIMULATOR")
    
    def _run(self):
        """Main simulation loop"""
        loop_count = 0
        
        while self.running:
            try:
                loop_count += 1
                
                # Update sensor data (every loop - 1 second)
                self._update_sensor()
                
                # Update drive (every loop)
                self._update_drive()
                
                # Log every 10 seconds
                if loop_count % 10 == 0:
                    sensor_data = self.server.read_sensor_data()
                    drive_data = self.server.read_drive_status()
                    
                    logger.debug(
                        f"Sensor: {sensor_data.get('temperature_c', 0):.1f}°C, "
                        f"{sensor_data.get('humidity_percent', 0):.1f}% | "
                        f"Drive: Pos={drive_data.get('position', 0)}, "
                        f"Running={drive_data.get('running', False)}",
                        "SIMULATOR"
                    )
                
                time.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Simulator error: {e}", "SIMULATOR")
                time.sleep(1.0)
    
    def _update_sensor(self):
        """Cập nhật giá trị sensor (nhiệt độ dao động nhẹ)"""
        # Random variation
        temp = self.temp_base + random.uniform(-2.0, 2.0)
        humi = self.humi_base + random.uniform(-5.0, 5.0)
        
        # Clamp values
        temp = max(-40.0, min(85.0, temp))
        humi = max(0.0, min(100.0, humi))
        
        self.server.write_sensor_data(temp, humi)
    
    def _update_drive(self):
        """Cập nhật trạng thái drive"""
        try:
            slave = self.server.context[DEVICE_DRIVE["slave_id"]]
            
            # Read control registers
            step_on_reg = slave.getValues(3, 0x0000, 1)[0]
            alarm_reset_reg = slave.getValues(3, 0x0001, 1)[0]
            stop_reg = slave.getValues(3, 0x0002, 1)[0]
            
            # Read current status
            current_status = self.server.read_drive_status()
            status_word = current_status.get("status_word", 0x0010)
            
            # Handle Step ON/OFF
            if step_on_reg == 1:
                self.step_on = True
                status_word |= 0x0001  # Set step_on bit
            else:
                self.step_on = False
                status_word &= ~0x0001  # Clear step_on bit
                self.velocity = 0
            
            # Handle Alarm Reset
            if alarm_reset_reg == 1:
                status_word &= ~0x8000  # Clear alarm bit
                slave.setValues(3, 0x0001, [0])  # Reset register
            
            # Handle Stop
            if stop_reg == 1:
                self.velocity = 0
                status_word &= ~0x0004  # Clear running bit
                status_word |= 0x0010  # Set in_position bit
                slave.setValues(3, 0x0002, [0])  # Reset register
            
            # Handle JOG command (0x0030-0x0033)
            jog_regs = slave.getValues(3, 0x0030, 4)
            jog_speed = (jog_regs[0] << 16) | jog_regs[1]
            jog_dir = jog_regs[3]  # 0=CCW, 1=CW
            
            if jog_speed > 0 and self.step_on:
                self.velocity = jog_speed if jog_dir == 1 else -jog_speed
                status_word |= 0x0004  # Set running bit
                status_word &= ~0x0010  # Clear in_position bit
            
            # Handle Absolute Move (0x0010-0x0013)
            abs_regs = slave.getValues(3, 0x0010, 4)
            abs_pos = (abs_regs[0] << 16) | abs_regs[1]
            if abs_pos & 0x80000000:
                abs_pos = abs_pos - (1 << 32)
            
            abs_speed = (abs_regs[2] << 16) | abs_regs[3]
            
            if abs_speed > 0 and self.step_on:
                self.target_position = abs_pos
                diff = self.target_position - self.position
                
                if abs(diff) > 10:
                    self.velocity = abs_speed if diff > 0 else -abs_speed
                    status_word |= 0x0004  # Running
                    status_word &= ~0x0010  # Not in position
                else:
                    self.velocity = 0
                    self.position = self.target_position
                    status_word &= ~0x0004  # Not running
                    status_word |= 0x0010  # In position
                    slave.setValues(3, 0x0010, [0, 0, 0, 0])  # Clear command
            
            # Handle Incremental Move (0x0020-0x0023)
            inc_regs = slave.getValues(3, 0x0020, 4)
            inc_offset = (inc_regs[0] << 16) | inc_regs[1]
            if inc_offset & 0x80000000:
                inc_offset = inc_offset - (1 << 32)
            
            inc_speed = (inc_regs[2] << 16) | inc_regs[3]
            
            if inc_speed > 0 and inc_offset != 0 and self.step_on:
                self.target_position = self.position + inc_offset
                self.velocity = inc_speed if inc_offset > 0 else -inc_speed
                status_word |= 0x0004  # Running
                status_word &= ~0x0010  # Not in position
                slave.setValues(3, 0x0020, [0, 0, 0, 0])  # Clear command
            
            # Update position based on velocity
            if self.velocity != 0 and self.step_on:
                # Simple simulation: move 1/10 of velocity per second
                self.position += int(self.velocity / 10)
            
            # Update registers
            self.server.write_drive_position(self.position)
            self.server.write_drive_status(status_word)
            
        except Exception as e:
            logger.error(f"Drive simulation error: {e}", "SIMULATOR")