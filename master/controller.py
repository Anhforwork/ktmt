# master/controller.py
"""
Master control logic - sends commands to Slave
"""
import config
from logger import LogComponent


class MasterController:
    def __init__(self, modbus_client, logger):
        self.modbus = modbus_client
        self.logger = logger
        
        # Current status from slave
        self.position = 0
        self.speed = 0
        self.temperature = 0.0
        self.humidity = 0.0
        self.driver_alarm = False
        self.driver_inpos = False
        self.driver_running = False
        self.counter_value = 0
        self.counter_target = 0
        self.auto_state = 0
        self.current_mode = 0
        self.step_enabled = False
        self.jog_state = 0
        
    def poll_status(self):
        """Poll status from slave via input registers"""
        if not self.modbus.connected:
            return False
        
        try:
            # Read IR[0:12]
            regs = self.modbus.read_input_registers(0, 12)
            
            if not regs or len(regs) < 12:
                return False
            
            # Parse data
            pos_hi, pos_lo = regs[0], regs[1]
            self.position = self._regs_to_s32(pos_hi, pos_lo)
            self.speed = regs[2]
            self.temperature = regs[3] / 10.0
            self.humidity = regs[4] / 10.0
            
            status_word = regs[5]
            self.driver_alarm = bool(status_word & (1 << 0))
            self.driver_inpos = bool(status_word & (1 << 1))
            self.driver_running = bool(status_word & (1 << 2))
            
            self.counter_value = regs[6]
            self.counter_target = regs[7]
            self.auto_state = regs[8]
            self.current_mode = regs[9]
            self.step_enabled = bool(regs[10])
            self.jog_state = regs[11]
            
            return True
            
        except Exception as e:
            self.logger.error(LogComponent.CONTROL, f"Poll status error: {e}")
            return False
    
    @staticmethod
    def _regs_to_s32(hi, lo):
        """Convert 2 registers to signed 32-bit"""
        val = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
        if val & 0x80000000:
            val = val - (1 << 32)
        return val
    
    @staticmethod
    def _s32_to_regs(val):
        """Convert signed 32-bit to 2 registers"""
        if val < 0:
            val = (1 << 32) + val
        hi = (val >> 16) & 0xFFFF
        lo = val & 0xFFFF
        return hi, lo
    
    def set_mode(self, mode):
        """Set mode: 0=AUTO, 1=MANUAL"""
        if mode not in (0, 1):
            self.logger.warn(LogComponent.CONTROL, f"Invalid mode: {mode}")
            return False
        
        mode_text = "AUTO" if mode == 0 else "MANUAL"
        self.logger.info(LogComponent.CONTROL, f"Setting mode to {mode_text}")
        
        success = self.modbus.write_single_register(config.HR_MODE_ADDR, mode)
        
        if success:
            self.current_mode = mode
            self.logger.info(LogComponent.CONTROL, f"Mode set to {mode_text}")
        else:
            self.logger.error(LogComponent.CONTROL, f"Failed to set mode to {mode_text}")
        
        return success
    
    def set_target(self, target):
        """Set counter target"""
        if target < 0 or target > 65535:
            self.logger.warn(LogComponent.CONTROL, f"Invalid target: {target}")
            return False
        
        self.logger.info(LogComponent.CONTROL, f"Setting target = {target}")
        
        success = self.modbus.write_single_register(config.HR_TARGET_ADDR, target)
        
        if success:
            self.logger.info(LogComponent.CONTROL, f"Target set to {target}")
        else:
            self.logger.error(LogComponent.CONTROL, f"Failed to set target")
        
        return success
    
    def send_command(self, cmd_code, position=None, speed=None):
        """Send command packet to slave"""
        if not self.modbus.connected:
            self.logger.error(LogComponent.CONTROL, "Not connected to slave")
            return False
        
        # Build command packet
        pos_hi, pos_lo = 0, 0
        if position is not None:
            pos_hi, pos_lo = self._s32_to_regs(position)
        
        spd = speed if speed is not None else 0
        spd = max(0, min(spd, 0xFFFF))
        
        cmd_regs = [
            cmd_code,
            pos_hi,
            pos_lo,
            spd,
            config.SOURCE_MASTER,
            config.SOURCE_PRIORITY
        ]
        
        cmd_names = {
            1: "STEP_ON", 2: "STEP_OFF", 3: "MOVE_ABS",
            5: "JOG_CW", 6: "JOG_CCW", 7: "STOP",
            8: "RESET_ALARM", 9: "EMERGENCY"
        }
        cmd_name = cmd_names.get(cmd_code, f"CMD_{cmd_code}")
        
        self.logger.info(
            LogComponent.CONTROL,
            f"Sending {cmd_name} - pos:{position}, speed:{speed}"
        )
        
        success = self.modbus.write_multiple_registers(config.HR_CMD_ADDR, cmd_regs)
        
        if success:
            self.logger.info(LogComponent.CONTROL, f"{cmd_name} sent successfully")
        else:
            self.logger.error(LogComponent.CONTROL, f"Failed to send {cmd_name}")
        
        return success
    
    def step_on(self):
        """Step ON"""
        return self.send_command(config.CMD_STEP_ON)
    
    def step_off(self):
        """Step OFF"""
        return self.send_command(config.CMD_STEP_OFF)
    
    def move_absolute(self, position, speed):
        """Move to absolute position"""
        return self.send_command(config.CMD_MOVE_ABS, position=position, speed=speed)
    
    def jog_cw(self, speed):
        """Jog clockwise"""
        return self.send_command(config.CMD_JOG_CW, speed=speed)
    
    def jog_ccw(self, speed):
        """Jog counter-clockwise"""
        return self.send_command(config.CMD_JOG_CCW, speed=speed)
    
    def stop(self):
        """Stop motor"""
        return self.send_command(config.CMD_STOP)
    
    def reset_alarm(self):
        """Reset alarm"""
        return self.send_command(config.CMD_RESET_ALARM)
    
    def emergency_stop(self):
        """Emergency stop"""
        return self.send_command(config.CMD_EMERGENCY)
    
    def get_status_dict(self):
        """Get current status as dictionary"""
        return {
            'position': self.position,
            'speed': self.speed,
            'temperature': self.temperature,
            'humidity': self.humidity,
            'driver_alarm': self.driver_alarm,
            'driver_inpos': self.driver_inpos,
            'driver_running': self.driver_running,
            'counter_value': self.counter_value,
            'counter_target': self.counter_target,
            'auto_state': self.auto_state,
            'auto_state_text': config.AUTO_STATE_MAP.get(self.auto_state, "Unknown"),
            'mode': self.current_mode,
            'step_enabled': self.step_enabled,
            'jog_state': self.jog_state
        }