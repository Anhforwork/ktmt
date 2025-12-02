# master/modbus_client.py
"""
Modbus TCP Client for Master Layer
"""
import threading
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

import config


class ModbusMasterClient:
    def __init__(self, logger):
        self.logger = logger
        self.client = None
        self.connected = False
        self.lock = threading.Lock()
        
        # Statistics
        self.commands_sent = 0
        self.status_reads = 0
        self.errors = 0
        
    def connect(self):
        """Connect to Slave Modbus TCP Server"""
        try:
            self.client = ModbusTcpClient(
                host=config.SLAVE_HOST,
                port=config.SLAVE_MODBUS_PORT,
                timeout=config.MODBUS_TIMEOUT
            )
            
            if self.client.connect():
                self.connected = True
                from logger import LogComponent
                self.logger.info(
                    LogComponent.MODBUS,
                    f"Connected to Slave at {config.SLAVE_HOST}:{config.SLAVE_MODBUS_PORT}"
                )
                return True
            else:
                from logger import LogComponent
                self.logger.error(
                    LogComponent.MODBUS,
                    f"Failed to connect to {config.SLAVE_HOST}:{config.SLAVE_MODBUS_PORT}"
                )
                return False
                
        except Exception as e:
            from logger import LogComponent
            self.logger.error(LogComponent.MODBUS, f"Connection error: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from server"""
        if self.client:
            try:
                self.client.close()
                self.connected = False
                from logger import LogComponent
                self.logger.info(LogComponent.MODBUS, "Disconnected from Slave")
            except Exception as e:
                from logger import LogComponent
                self.logger.error(LogComponent.MODBUS, f"Disconnect error: {e}")
    
    def read_holding_registers(self, address, count):
        """Read holding registers"""
        if not self.connected:
            return None
        
        with self.lock:
            try:
                result = self.client.read_holding_registers(address, count, device_id=1)
                
                if result.isError():
                    self.errors += 1
                    from logger import LogComponent
                    self.logger.warn(
                        LogComponent.MODBUS,
                        f"Error reading HR[{address}:{address+count}]"
                    )
                    return None
                
                return result.registers
                
            except Exception as e:
                self.errors += 1
                from logger import LogComponent
                self.logger.error(LogComponent.MODBUS, f"Read HR error: {e}")
                return None
    
    def write_single_register(self, address, value):
        """Write single holding register"""
        if not self.connected:
            return False
        
        with self.lock:
            try:
                from logger import LogComponent
                self.logger.info(
                    LogComponent.MODBUS,
                    f"Write HR[{address}] = {value}"
                )
                
                result = self.client.write_register(address, value, device_id=1)
                
                if result.isError():
                    self.errors += 1
                    self.logger.error(
                        LogComponent.MODBUS,
                        f"Error writing HR[{address}]"
                    )
                    return False
                
                self.commands_sent += 1
                return True
                
            except Exception as e:
                self.errors += 1
                from logger import LogComponent
                self.logger.error(LogComponent.MODBUS, f"Write register error: {e}")
                return False
    
    def write_multiple_registers(self, address, values):
        """Write multiple holding registers"""
        if not self.connected:
            return False
        
        with self.lock:
            try:
                from logger import LogComponent
                self.logger.info(
                    LogComponent.MODBUS,
                    f"Write HR[{address}:{address+len(values)}] = {values}"
                )
                
                result = self.client.write_registers(address, values, device_id=1)
                
                if result.isError():
                    self.errors += 1
                    self.logger.error(
                        LogComponent.MODBUS,
                        f"Error writing multiple registers at HR[{address}]"
                    )
                    return False
                
                self.commands_sent += 1
                return True
                
            except Exception as e:
                self.errors += 1
                from logger import LogComponent
                self.logger.error(LogComponent.MODBUS, f"Write registers error: {e}")
                return False
    
    def read_input_registers(self, address, count):
        """Read input registers (status from slave)"""
        if not self.connected:
            return None
        
        with self.lock:
            try:
                result = self.client.read_input_registers(address, count, device_id=1)
                
                if result.isError():
                    self.errors += 1
                    return None
                
                self.status_reads += 1
                return result.registers
                
            except Exception as e:
                self.errors += 1
                return None
    
    def get_statistics(self):
        """Get client statistics"""
        return {
            'connected': self.connected,
            'commands_sent': self.commands_sent,
            'status_reads': self.status_reads,
            'errors': self.errors
        }