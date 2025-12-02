# plc_controller.py
"""
PLC Controller - Logic điều khiển AUTO/MANUAL
"""

import time
import threading
from pyModbusTCP.server import ModbusServer

from config import (
    MODBUS_TCP_PORT, HR_TARGET_ADDR, HR_MODE_ADDR, HR_CMD_ADDR,
    HR_CMD_REG_COUNT, AUTO_MOVE_PULSES, AUTO_MOVE_SPEED,
    AUTO_STATE_MAP
)
from device_manager import DeviceManager


class PLCController:
    """Điều khiển logic AUTO và MANUAL"""
    
    def __init__(self, device_manager: DeviceManager, log_callback=None):
        self.device_manager = device_manager
        self.log_callback = log_callback
        
        # Modbus TCP Server
        self.modbus_server = None
        self.running = True
        
        # AUTO logic
        self.auto_enabled = True
        self.motor_state = "Idle"
        self.last_motor_cmd_time = time.time()
        self.last_tcp_target = 0
        self._last_mode_logged = -1
        
    def log(self, msg: str):
        """Ghi log"""
        if self.log_callback:
            self.log_callback(msg)
    
    def start_modbus_server(self, status_callback=None):
        """Khởi động Modbus TCP Server"""
        def server_thread():
            try:
                self.modbus_server = ModbusServer(
                    host="0.0.0.0",
                    port=MODBUS_TCP_PORT,
                    no_block=True
                )
                self.modbus_server.start()
                
                # Init registers
                self.modbus_server.data_bank.set_input_registers(0, [0] * 32)
                hr_init = [0] * 100
                hr_init[HR_TARGET_ADDR] = 0
                hr_init[HR_MODE_ADDR] = 0
                hr_init[HR_CMD_ADDR] = 0
                self.modbus_server.data_bank.set_holding_registers(0, hr_init)
                
                if status_callback:
                    status_callback(f"Listening on {MODBUS_TCP_PORT}")
                self.log(f"Modbus TCP Server started on port {MODBUS_TCP_PORT}")
                
                while self.running:
                    time.sleep(0.5)
            except Exception as e:
                self.log(f"Modbus server error: {e}")
                if status_callback:
                    status_callback("Modbus server error")
        
        threading.Thread(target=server_thread, daemon=True).start()
    
    def stop_modbus_server(self):
        """Dừng Modbus TCP Server"""
        self.running = False
        if self.modbus_server:
            try:
                self.modbus_server.stop()
            except:
                pass
    
    def get_mode(self) -> int:
        """Đọc MODE từ HR_MODE_ADDR (0=AUTO, 1=MANUAL)"""
        if not self.modbus_server:
            return 0
        try:
            m = self.modbus_server.data_bank.get_holding_registers(HR_MODE_ADDR, 1)
            if m and len(m) >= 1:
                mode = m[0]
                if mode != self._last_mode_logged:
                    self.log(f"MODE from HR{HR_MODE_ADDR} = {mode}")
                    self._last_mode_logged = mode
                return mode
        except Exception as e:
            self.log(f"Error reading HR_MODE: {e}")
        return 0
    
    def check_target_from_tcp(self):
        """Kiểm tra và cập nhật target từ Layer B/C"""
        if not self.modbus_server:
            return
        
        try:
            hr = self.modbus_server.data_bank.get_holding_registers(HR_TARGET_ADDR, 1)
            if not hr or len(hr) < 1:
                return
            
            target = hr[0]
            
            # Thay đổi target → gửi xuống Arduino
            if target != self.last_tcp_target:
                self.last_tcp_target = target
                self.log(f"TARGET HR{HR_TARGET_ADDR} = {target} → gửi xuống Arduino")
                
                if self.device_manager.set_counter_target(target):
                    self.log(f"Arduino nhận target = {target}")
                    self.device_manager.counter_target = target
                else:
                    self.log("Arduino không confirm target")
        
        except Exception as e:
            self.log(f"Error reading HR{HR_TARGET_ADDR}: {e}")
    
    def process_manual_command(self):
        """Xử lý lệnh MANUAL từ Layer B/C"""
        if not self.modbus_server:
            return
        
        try:
            regs = self.modbus_server.data_bank.get_holding_registers(
                HR_CMD_ADDR, HR_CMD_REG_COUNT
            )
            if not regs or len(regs) < HR_CMD_REG_COUNT:
                return
            
            cmd, pos_hi, pos_lo, speed, source_code, priority = regs
            
            if cmd == 0:
                return
            
            # Chuyển đổi position
            pos_val = ((pos_hi & 0xFFFF) << 16) | (pos_lo & 0xFFFF)
            if pos_val & 0x80000000:
                pos_val -= (1 << 32)
            
            src_text = "B" if source_code == 2 else ("C" if source_code == 3 else "Unknown")
            
            self.log(
                f"MANUAL CMD={cmd} from {src_text} "
                f"prio={priority}, pos={pos_val}, speed={speed}"
            )
            
            # Xử lý từng lệnh
            success = False
            if cmd == 1:  # STEP ON
                success = self.device_manager.motor_step_on()
            elif cmd == 2:  # STEP OFF
                success = self.device_manager.motor_step_off()
            elif cmd == 3:  # MOVE ABS
                success = self.device_manager.motor_move_absolute(pos_val, speed)
            elif cmd == 5:  # JOG CW
                success = self.device_manager.motor_jog_cw(speed)
            elif cmd == 6:  # JOG CCW
                success = self.device_manager.motor_jog_ccw(speed)
            elif cmd == 7:  # STOP
                success = self.device_manager.motor_stop()
            elif cmd == 8:  # RESET ALARM
                success = self.device_manager.motor_reset_alarm()
            elif cmd == 9:  # EMERGENCY STOP
                success = self.device_manager.motor_stop()
            
            # Clear CMD
            self.modbus_server.data_bank.set_holding_registers(HR_CMD_ADDR, [0])
        
        except Exception as e:
            self.log(f"Error in process_manual_command: {e}")
    
    def auto_cycle(self):
        """Chu kỳ AUTO - lặp nhiều chu kỳ"""
        # Cập nhật target từ Layer B/C
        self.check_target_from_tcp()
        
        # Đọc MODE
        mode = self.get_mode()
        
        # ---------- MANUAL MODE ----------
        if mode == 1:
            self.motor_state = "Manual"
            self.process_manual_command()
            return
        
        # ---------- AUTO MODE ----------
        if not self.auto_enabled:
            self.motor_state = "Disabled"
            return
        
        if self.device_manager.driver_alarm:
            if self.motor_state != "Alarm":
                self.log("AUTO stopped: driver alarm.")
            self.motor_state = "Alarm"
            return
        
        if self.device_manager.counter_target <= 0:
            self.motor_state = "Waiting target"
            return
        
        # 1. Counter DONE và motor KHÔNG chạy → phát lệnh chạy motor
        if (self.device_manager.counter_done and 
            self.motor_state not in ("Motor running", "Alarm")):
            
            if self.device_manager.motor_move_absolute(AUTO_MOVE_PULSES, AUTO_MOVE_SPEED):
                self.device_manager.current_speed = AUTO_MOVE_SPEED
                self.motor_state = "Motor running"
                self.last_motor_cmd_time = time.time()
                self.log(
                    f"AUTO: count reached target "
                    f"({self.device_manager.counter_value}/"
                    f"{self.device_manager.counter_target}), "
                    f"run motor +{AUTO_MOVE_PULSES} pulses."
                )
            return
        
        # 2. Motor đang chạy → chờ INPOS hoặc TIMEOUT
        if self.motor_state == "Motor running":
            if self.device_manager.driver_inpos:
                if self.device_manager.reset_counter():
                    self.motor_state = "Waiting reset"
                    self.last_motor_cmd_time = time.time()
                    self.log("AUTO: motor in-position, reset counter (HR3=1).")
            elif time.time() - self.last_motor_cmd_time > 10:
                self.motor_state = "Timeout motor"
                self.log("AUTO: timeout waiting for motor InPos.")
            return
        
        # 3. Đang chờ Arduino RESET counter
        if self.motor_state == "Waiting reset":
            if (self.device_manager.counter_value == 0 and 
                not self.device_manager.counter_done):
                self.motor_state = "Idle"
                self.log("AUTO: new cycle started (counter reset).")
            return
        
        # 4. Các trạng thái còn lại
        if self.motor_state not in (
            "Idle", "Waiting count", "Waiting target", "Timeout motor"
        ):
            self.motor_state = "Waiting count"
        elif not self.device_manager.counter_done:
            self.motor_state = "Waiting count"
    
    def update_input_registers(self):
        """Cập nhật Input Registers cho Layer B/C"""
        if not self.modbus_server:
            return
        
        try:
            pos = self.device_manager.current_position
            if pos < 0:
                pos_val = (1 << 32) + pos
            else:
                pos_val = pos
            pos_hi = (pos_val >> 16) & 0xFFFF
            pos_lo = pos_val & 0xFFFF
            
            speed = max(0, min(int(self.device_manager.current_speed), 0xFFFF))
            temp = max(-32768, min(int(self.device_manager.temperature * 10), 32767)) & 0xFFFF
            humi = max(0, min(int(self.device_manager.humidity * 10), 0xFFFF))
            
            status_word = 0
            if self.device_manager.driver_alarm:
                status_word |= 1 << 0
            if self.device_manager.driver_inpos:
                status_word |= 1 << 1
            if self.device_manager.driver_running:
                status_word |= 1 << 2
            
            auto_code = AUTO_STATE_MAP.get(self.motor_state, 0)
            mode_val = self.get_mode()
            
            regs = [
                pos_hi,
                pos_lo,
                speed,
                temp,
                humi,
                status_word,
                self.device_manager.counter_value,
                self.device_manager.counter_target,
                auto_code,
                mode_val,
            ]
            self.modbus_server.data_bank.set_input_registers(0, regs)
        except Exception as e:
            self.log(f"Error updating input regs: {e}")