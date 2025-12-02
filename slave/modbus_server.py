# slave/modbus_server.py
"""
Modbus TCP Server using pymodbus
"""
import threading
import time
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusDeviceContext as ModbusSlaveContext

import config


class ModbusTCPServer:
    def __init__(self, logger):
        self.logger = logger
        self.running = False
        self.server_thread = None
        
        # Datastore
        self.store = None
        self.context = None
        
        # Statistics
        self.read_count = 0
        self.write_count = 0
        
    def start(self):
        """Start Modbus TCP Server"""
        try:
            # Create datastore
            # HR = Holding Registers (address 40000+)
            # IR = Input Registers (address 30000+)
            # CO = Coils (address 00000+)
            # DI = Discrete Inputs (address 10000+)
            
            self.store = ModbusSlaveContext(
                di=ModbusSequentialDataBlock(0, [0] * 100),  # Discrete Inputs
                co=ModbusSequentialDataBlock(0, [0] * 100),  # Coils
                hr=ModbusSequentialDataBlock(0, [0] * 100),  # Holding Registers
                ir=ModbusSequentialDataBlock(0, [0] * 100),  # Input Registers
            )
            
            self.context = ModbusServerContext(slaves={1: self.store}, single=False)
            
            # Device identification (not available in pymodbus 3.x)
            identity = None
            
            # Initialize registers
            self._init_registers()
            
            # Start server in thread
            self.running = True
            self.server_thread = threading.Thread(
                target=self._server_loop,
                args=(identity,),
                daemon=True
            )
            self.server_thread.start()
            
            from logger import LogComponent
            self.logger.info(
                LogComponent.SYSTEM,
                f"Modbus TCP Server started on {config.MODBUS_TCP_HOST}:{config.MODBUS_TCP_PORT}"
            )
            return True
            
        except Exception as e:
            from logger import LogComponent
            self.logger.error(LogComponent.SYSTEM, f"Failed to start Modbus server: {e}")
            return False
    
    def _init_registers(self):
        """Initialize holding registers"""
        hr_init = [0] * 100
        hr_init[config.HR_TARGET_ADDR] = 0
        hr_init[config.HR_MODE_ADDR] = 0
        hr_init[config.HR_CMD_ADDR] = 0
        
        # Write to store
        self.context[1].setValues(3, 0, hr_init)  # function code 3 = holding registers
    
    def _server_loop(self, identity):
        """Server loop"""
        try:
            StartTcpServer(
                context=self.context,
                identity=identity,
                address=(config.MODBUS_TCP_HOST, config.MODBUS_TCP_PORT)
            )
        except Exception as e:
            from logger import LogComponent
            self.logger.error(LogComponent.SYSTEM, f"Modbus server error: {e}")
    
    def stop(self):
        """Stop server"""
        self.running = False
        from logger import LogComponent
        self.logger.info(LogComponent.SYSTEM, "Modbus TCP Server stopped")
    
    def get_holding_registers(self, address, count):
        """Read holding registers"""
        try:
            if not self.context:
                return None
            
            values = self.context[1].getValues(3, address, count)
            self.read_count += 1
            return values
        except Exception as e:
            from logger import LogComponent
            self.logger.error(LogComponent.SYSTEM, f"Error reading HR{address}: {e}")
            return None
    
    def set_holding_registers(self, address, values):
        """Write holding registers"""
        try:
            if not self.context:
                return False
            
            if not isinstance(values, list):
                values = [values]
            
            self.context[1].setValues(3, address, values)
            self.write_count += 1
            
            from logger import LogComponent
            self.logger.info(
                LogComponent.SYSTEM,
                f"HR[{address}] written: {values}"
            )
            return True
        except Exception as e:
            from logger import LogComponent
            self.logger.error(LogComponent.SYSTEM, f"Error writing HR{address}: {e}")
            return False
    
    def get_input_registers(self, address, count):
        """Read input registers"""
        try:
            if not self.context:
                return None
            
            values = self.context[1].getValues(4, address, count)
            return values
        except Exception as e:
            return None
    
    def set_input_registers(self, address, values):
        """Write input registers (for status update)"""
        try:
            if not self.context:
                return False
            
            if not isinstance(values, list):
                values = [values]
            
            self.context[1].setValues(4, address, values)
            return True
        except Exception as e:
            return False
    
    def get_statistics(self):
        """Get server statistics"""
        return {
            'running': self.running,
            'reads': self.read_count,
            'writes': self.write_count
        }