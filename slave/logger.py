# slave/logger.py
"""
Event logger with different levels and components
"""
import time
from datetime import datetime
from enum import Enum


class LogLevel(Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class LogComponent(Enum):
    RS485 = "RS485"
    SENSOR = "SENSOR"
    DRIVER = "DRIVER"
    UI = "UI"
    SYSTEM = "SYSTEM"


class EventLogger:
    def __init__(self, max_lines=200):
        self.max_lines = max_lines
        self.logs = []
        
    def add_log(self, level: LogLevel, component: LogComponent, message: str):
        """Add a log entry"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # milliseconds
        log_entry = f"[{timestamp}] {level.value:5s} {component.value:7s} {message}"
        
        self.logs.append(log_entry)
        
        # Keep only the last max_lines
        if len(self.logs) > self.max_lines:
            self.logs = self.logs[-self.max_lines:]
        
        return log_entry
    
    def info(self, component: LogComponent, message: str):
        """Log INFO level"""
        return self.add_log(LogLevel.INFO, component, message)
    
    def warn(self, component: LogComponent, message: str):
        """Log WARN level"""
        return self.add_log(LogLevel.WARN, component, message)
    
    def error(self, component: LogComponent, message: str):
        """Log ERROR level"""
        return self.add_log(LogLevel.ERROR, component, message)
    
    def log_tx(self, component: LogComponent, frame: bytes):
        """Log transmitted frame"""
        from modbus_rtu import bytes_to_hex
        hex_str = bytes_to_hex(frame)
        return self.info(component, f"TX: {hex_str}")
    
    def log_rx(self, component: LogComponent, frame: bytes):
        """Log received frame"""
        from modbus_rtu import bytes_to_hex
        hex_str = bytes_to_hex(frame)
        return self.info(component, f"RX: {hex_str}")
    
    def get_all_logs(self):
        """Get all log entries"""
        return self.logs.copy()
    
    def clear(self):
        """Clear all logs"""
        self.logs.clear()
    
    def export_to_file(self, filepath: str) -> bool:
        """Export logs to text file"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("SLAVE LAYER - EVENT LOG\n")
                f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                
                for log in self.logs:
                    f.write(log + "\n")
                
                f.write("\n" + "=" * 80 + "\n")
                f.write(f"Total entries: {len(self.logs)}\n")
            
            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False