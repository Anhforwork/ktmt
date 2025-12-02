# slave/serial_handler.py
"""
Serial communication handler with logging
"""
import serial
import time
import threading
from logger import EventLogger, LogComponent


class SerialHandler:
    def __init__(self, logger: EventLogger):
        self.logger = logger
        self.ser = None
        self.ser_lock = threading.Lock()
        self.is_connected = False
        
    def connect(self, port: str, baudrate: int, parity='E', stopbits=1, bytesize=8):
        """Connect to serial port"""
        if self.ser and self.ser.is_open:
            self.logger.warn(LogComponent.RS485, "Already connected")
            return False
        
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                parity=parity,
                stopbits=stopbits,
                bytesize=bytesize,
                timeout=1.0
            )
            time.sleep(0.1)
            self.is_connected = True
            
            parity_str = f"{bytesize}{parity}{stopbits}"
            self.logger.info(LogComponent.RS485, f"Open {port} {baudrate} {parity_str}")
            return True
            
        except Exception as e:
            self.logger.error(LogComponent.RS485, f"Connection failed: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from serial port"""
        if self.ser:
            try:
                port_name = self.ser.port
                self.ser.close()
                self.logger.info(LogComponent.RS485, f"Closed {port_name}")
            except Exception as e:
                self.logger.error(LogComponent.RS485, f"Close error: {e}")
            finally:
                self.ser = None
                self.is_connected = False
    
    def send_frame(self, frame: bytes, component: LogComponent) -> bytes:
        """Send frame and receive response with logging"""
        if not self.ser or not self.ser.is_open:
            self.logger.error(component, "Serial port not open")
            return b""
        
        with self.ser_lock:
            try:
                # Clear buffer
                self.ser.reset_input_buffer()
                
                # Log TX
                self.logger.log_tx(component, frame)
                
                # Send
                self.ser.write(frame)
                self.ser.flush()
                time.sleep(0.02)
                
                # Receive
                resp = b""
                start = time.time()
                timeout = 1.0
                
                while time.time() - start < timeout:
                    chunk = self.ser.read(256)
                    if chunk:
                        resp += chunk
                        time.sleep(0.03)
                    else:
                        if resp:
                            break
                        time.sleep(0.01)
                
                # Log RX
                if resp:
                    self.logger.log_rx(component, resp)
                else:
                    self.logger.warn(component, f"Timeout (no response)")
                
                return resp
                
            except Exception as e:
                self.logger.error(component, f"Communication error: {e}")
                return b""
    
    def get_status(self) -> dict:
        """Get connection status"""
        if self.ser and self.ser.is_open:
            return {
                'connected': True,
                'port': self.ser.port,
                'baudrate': self.ser.baudrate,
                'parity': self.ser.parity,
                'stopbits': self.ser.stopbits,
                'bytesize': self.ser.bytesize
            }
        else:
            return {'connected': False}