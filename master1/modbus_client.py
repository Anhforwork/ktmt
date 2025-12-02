import threading
import time
from pyModbusTCP.client import ModbusClient

from utils import SignalEmitter, regs_to_s32, s32_to_regs, AUTO_STATE_MAP

# Configuration
A_HOST = "192.168.1.220"
A_MODBUS_PORT = 502
A_HR_MODE_ADDR = 8
A_HR_CMD_ADDR = 10
A_HR_CMD_REG_COUNT = 6


class ModbusClientA:
    def __init__(self):
        self.signals = SignalEmitter()
        self.client = None
        self.running = True
        self.modbus_lock = threading.Lock()
        self.modbus_connected = False
        self.commands_forwarded = 0
        
        self._init_client()
        
    def _init_client(self):
        try:
            self.client = ModbusClient(
                host=A_HOST,
                port=A_MODBUS_PORT,
                auto_open=True,
                auto_close=False,
                timeout=3.0
            )
            self.signals.log_signal.emit("Modbus client to Layer A initialized")
        except Exception as e:
            self.signals.log_signal.emit(f"Error init Modbus client: {e}")

    def start_polling(self):
        def poll_loop():
            while self.running:
                self.poll_status()
                time.sleep(0.5)
        t = threading.Thread(target=poll_loop, daemon=True)
        t.start()

    def poll_status(self):
        """Read Input Registers 0..11 from Layer A"""
        if not self.client:
            return
            
        try:
            with self.modbus_lock:
                regs = self.client.read_input_registers(0, 12)

            if regs is None:
                if self.modbus_connected:
                    self.modbus_connected = False
                    self.signals.connection_signal.emit("a", "Disconnected")
                return

            if not self.modbus_connected:
                self.modbus_connected = True
                self.signals.connection_signal.emit("a", "Connected")
                self.signals.log_signal.emit("Connected to Layer A (Modbus TCP)")

            if len(regs) < 12:
                return

            # Parse registers
            pos_hi, pos_lo, speed, temp10, humi10, status_word, \
                cnt_val, cnt_target, auto_code, mode_val, \
                step_state, jog_state = regs

            position = regs_to_s32(pos_hi, pos_lo)
            
            status_data = {
                'position': position,
                'speed': speed,
                'temperature': temp10 / 10.0,
                'humidity': humi10 / 10.0,
                'driver_alarm': bool(status_word & (1 << 0)),
                'driver_inpos': bool(status_word & (1 << 1)),
                'driver_running': bool(status_word & (1 << 2)),
                'counter_value': cnt_val,
                'counter_target': cnt_target,
                'auto_state_code': auto_code,
                'auto_state_text': AUTO_STATE_MAP.get(auto_code, "Unknown"),
                'mode': mode_val,
                'step_enabled': bool(step_state),
                'jog_state': jog_state,
            }
            
            self.signals.status_update.emit(status_data)

        except Exception as e:
            self.signals.log_signal.emit(f"Error polling A via Modbus: {e}")
            if self.modbus_connected:
                self.modbus_connected = False
                self.signals.connection_signal.emit("a", "Disconnected")

    def set_mode(self, mode: int):
        """Write mode to HR_MODE_ADDR on Layer A: 0=AUTO, 1=MANUAL"""
        if not self.client:
            self.signals.log_signal.emit("Modbus client A not initialized")
            return False

        if mode not in (0, 1):
            return False

        try:
            with self.modbus_lock:
                if not self.client.is_open:
                    self.signals.log_signal.emit(f"Modbus not open. Reconnecting to {A_HOST}:{A_MODBUS_PORT}...")
                    if not self.client.open():
                        self.signals.log_signal.emit(f"Cannot connect to {A_HOST}:{A_MODBUS_PORT}")
                        return False

                mode_text = "AUTO" if mode == 0 else "MANUAL"
                self.signals.log_signal.emit(f"Writing MODE={mode} ({mode_text}) to HR{A_HR_MODE_ADDR}...")
                ok = self.client.write_single_register(A_HR_MODE_ADDR, mode)

            if ok:
                self.signals.log_signal.emit(f"Mode set to {mode_text}")
                return True
            else:
                error_msg = self.client.last_error_txt
                self.signals.log_signal.emit(f"Failed to write mode to A: {error_msg}")
                return False
                
        except Exception as e:
            self.signals.log_signal.emit(f"Exception writing mode to A: {e}")
            return False

    def write_cmd_to_a(self, cmd, pos=None, speed=None, 
                      origin_source="Layer_B", priority=None):
        """Write command packet to HR[A_HR_CMD_ADDR..] of A"""
        if not self.client:
            self.signals.log_signal.emit("Modbus client A not initialized")
            return False

        # Determine source code and priority
        if "Layer_C" in origin_source or "Machine_C" in origin_source:
            source_code = 3
            prio = priority if priority is not None else 3
        elif "Layer_B" in origin_source or "Machine_B" in origin_source:
            source_code = 2
            prio = priority if priority is not None else 2
        else:
            source_code = 2
            prio = priority if priority is not None else 2

        # Prepare position registers
        pos_hi = 0
        pos_lo = 0
        if pos is not None:
            pos_hi, pos_lo = s32_to_regs(pos)

        spd = speed if speed is not None else 0
        spd &= 0xFFFFFFFF

        # Build register array
        regs = [0] * A_HR_CMD_REG_COUNT
        regs[0] = cmd
        regs[1] = pos_hi
        regs[2] = pos_lo
        regs[3] = spd & 0xFFFF
        regs[4] = source_code
        regs[5] = prio

        try:
            with self.modbus_lock:
                if not self.client.is_open:
                    self.signals.log_signal.emit(f"Modbus not open. Reconnecting to {A_HOST}:{A_MODBUS_PORT}...")
                    if not self.client.open():
                        self.signals.log_signal.emit(f"Cannot connect to {A_HOST}:{A_MODBUS_PORT}")
                        return False

                self.signals.log_signal.emit(f"Writing CMD packet to HR{A_HR_CMD_ADDR}: {regs}")
                ok = self.client.write_multiple_registers(A_HR_CMD_ADDR, regs)

            if ok:
                self.commands_forwarded += 1
                self.signals.log_signal.emit(f"CMD={cmd} sent to A successfully")
                return True
            else:
                error_msg = self.client.last_error_txt
                self.signals.log_signal.emit(f"Failed to write holding registers: {error_msg}")
                return False
        except Exception as e:
            self.signals.log_signal.emit(f"Error writing cmd to A: {e}")
            return False

    def execute_command(self, command, from_c: bool):
        """Execute command from GUI or Layer C"""
        cmd_type = command.get('type')
        source = command.get('source', 'Layer_C' if from_c else 'Layer_B')
        priority = command.get('priority', 3 if from_c else 2)
        data = command.get('data', {})

        if cmd_type == 'heartbeat':
            return

        if cmd_type == 'set_mode':
            mode = int(data.get('mode', 0))
            self.set_mode(mode)

        elif cmd_type == 'motor_control':
            step_cmd = data.get('step_command')
            alarm_reset = data.get('alarm_reset', False)

            if step_cmd == 'on':
                if self.write_cmd_to_a(1, origin_source=source, priority=priority):
                    self.signals.log_signal.emit("STEP ON (via Modbus) from " + source)
            elif step_cmd == 'off':
                if self.write_cmd_to_a(2, origin_source=source, priority=priority):
                    self.signals.log_signal.emit("STEP OFF (via Modbus) from " + source)
            elif alarm_reset:
                if self.write_cmd_to_a(8, origin_source=source, priority=priority):
                    self.signals.log_signal.emit("RESET ALARM (via Modbus) from " + source)
            else:
                pos = int(data.get('position', 0))
                speed = int(data.get('speed', 1000))
                if self.write_cmd_to_a(3, pos=pos, speed=speed,
                                      origin_source=source, priority=priority):
                    self.signals.log_signal.emit(f"MOVE ABS (Modbus) from {source}: pos={pos:,} @ {speed:,}pps")

        elif cmd_type == 'jog_control':
            speed = int(data.get('speed', 0))
            direction = int(data.get('direction', 1))
            cmd = 5 if direction > 0 else 6
            if self.write_cmd_to_a(cmd, speed=speed, origin_source=source, priority=priority):
                dir_str = "CW" if direction > 0 else "CCW"
                self.signals.log_signal.emit(f"JOG {dir_str} (Modbus) from {source}: {speed:,}pps")

        elif cmd_type == 'stop_motor':
            if self.write_cmd_to_a(7, origin_source=source, priority=priority):
                self.signals.log_signal.emit(f"STOP (Modbus) from {source}")

        elif cmd_type == 'release_control':
            if self.write_cmd_to_a(7, origin_source="Local", priority=1):
                self.signals.log_signal.emit("RELEASE CONTROL → Local (via Modbus)")

        elif cmd_type == 'emergency_stop':
            if self.write_cmd_to_a(9, origin_source=source, priority=priority):
                self.signals.log_signal.emit(f"EMERGENCY STOP (Modbus) from {source}")

    def stop(self):
        self.running = False
        if self.client:
            try:
                self.client.close()
            except:
                pass