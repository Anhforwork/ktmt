"""
Modbus service for Layer B -> Layer A (Modbus TCP) using pyModbusTCP.

Tested API target: pyModbusTCP==0.3.0
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal
from pyModbusTCP.client import ModbusClient


def regs_to_s32(hi: int, lo: int) -> int:
    val = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
    if val & 0x80000000:
        val -= (1 << 32)
    return val


def s32_to_regs(val: int) -> Tuple[int, int]:
    if val < 0:
        val = (1 << 32) + val
    hi = (val >> 16) & 0xFFFF
    lo = val & 0xFFFF
    return hi, lo


class ModbusService(QObject):
    log = pyqtSignal(str)
    connection_changed = pyqtSignal(str)   # "Connected" / "Disconnected" / "Connecting..."
    status_updated = pyqtSignal(dict)      # parsed status dict

    def __init__(
        self,
        host: str,
        port: int,
        ir_base: int,
        ir_count: int,
        hr_target_addr: int,
        hr_mode_addr: int,
        hr_cmd_addr: int,
        hr_cmd_count: int,
        poll_interval_s: float = 0.5,
        timeout_s: float = 3.0,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._host = host
        self._port = port

        self._ir_base = ir_base
        self._ir_count = ir_count

        self._hr_target_addr = hr_target_addr
        self._hr_mode_addr = hr_mode_addr
        self._hr_cmd_addr = hr_cmd_addr
        self._hr_cmd_count = hr_cmd_count

        self._poll_interval_s = float(poll_interval_s)
        self._timeout_s = float(timeout_s)

        self._lock = threading.Lock()
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._connected = False

        # IMPORTANT: use same high-level client API as original file
        self._client = ModbusClient(
            host=self._host,
            port=self._port,
            auto_open=False,
            auto_close=False,
            timeout=self._timeout_s
        )

    # ---------- lifecycle ----------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self.connection_changed.emit("Connecting...")
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        self.log.emit(f"ModbusService started (target {self._host}:{self._port})")

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        try:
            with self._lock:
                self._client.close()
        except Exception:
            pass
        if self._connected:
            self._connected = False
            self.connection_changed.emit("Disconnected")
        self.log.emit("ModbusService stopped")

    # ---------- internals ----------
    def _ensure_open(self) -> bool:
        try:
            if self._client.is_open:
                return True
            ok = self._client.open()
            return bool(ok)
        except Exception:
            return False

    def _set_connected(self, connected: bool) -> None:
        if connected and not self._connected:
            self._connected = True
            self.connection_changed.emit("Connected")
            self.log.emit("Connected to Layer A (Modbus TCP)")
        elif (not connected) and self._connected:
            self._connected = False
            self.connection_changed.emit("Disconnected")
            self.log.emit("Disconnected from Layer A (Modbus TCP)")

    def _poll_loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                status = self.poll_status()
                if status is not None:
                    self.status_updated.emit(status)
            except Exception as e:
                self.log.emit(f"Error polling A via Modbus: {e}")
                self._set_connected(False)
            time.sleep(self._poll_interval_s)

    # ---------- API ----------
    def poll_status(self) -> Optional[Dict]:
        """
        Reads input registers from Layer A and parses them into a status dict.
        Returns None when device didn't respond.
        """
        with self._lock:
            if not self._ensure_open():
                self._set_connected(False)
                return None

            regs = self._client.read_input_registers(self._ir_base, self._ir_count)

        if regs is None or len(regs) < self._ir_count:
            self._set_connected(False)
            return None

        self._set_connected(True)

        pos_hi, pos_lo, speed, temp10, humi10, status_word, \
        cnt_val, cnt_target, auto_code, mode_val, step_state, jog_state = regs[:12]

        position = regs_to_s32(pos_hi, pos_lo)

        parsed = {
            "position": position,
            "speed": int(speed),
            "temperature": float(temp10) / 10.0,
            "humidity": float(humi10) / 10.0,
            "driver_alarm": bool(status_word & (1 << 0)),
            "driver_inpos": bool(status_word & (1 << 1)),
            "driver_running": bool(status_word & (1 << 2)),
            "counter_value": int(cnt_val),
            "counter_target": int(cnt_target),
            "auto_state_code": int(auto_code),
            "mode": int(mode_val),
            "step_enabled": bool(step_state),
            "jog_state": int(jog_state),
            "timestamp": time.time(),
        }
        return parsed

    def write_target(self, target: int) -> bool:
        """Writes target count to Layer A holding register."""
        if target < 0 or target > 65535:
            self.log.emit(f"Target {target} out of 16-bit range")
            return False

        with self._lock:
            if not self._ensure_open():
                self._set_connected(False)
                self.log.emit(f"Cannot open Modbus to {self._host}:{self._port}")
                return False

            ok = self._client.write_single_register(self._hr_target_addr, int(target))

        if not ok:
            self.log.emit(f"Write HR{self._hr_target_addr} failed: {self._client.last_error_txt}")
            return False
        self.log.emit(f"Target {target} → A HR{self._hr_target_addr} SUCCESS")
        return True

    def write_mode(self, mode: int) -> bool:
        """Writes mode to Layer A: 0=AUTO, 1=MANUAL."""
        if mode not in (0, 1):
            return False

        with self._lock:
            if not self._ensure_open():
                self._set_connected(False)
                self.log.emit(f"Cannot open Modbus to {self._host}:{self._port}")
                return False

            ok = self._client.write_single_register(self._hr_mode_addr, int(mode))

        if not ok:
            self.log.emit(f"Write HR{self._hr_mode_addr} failed: {self._client.last_error_txt}")
            return False
        self.log.emit(f"Mode {mode} → A HR{self._hr_mode_addr} SUCCESS")
        return True

    def write_cmd_packet(
        self,
        cmd: int,
        pos: Optional[int] = None,
        speed: Optional[int] = None,
        origin_source: str = "Layer_B",
        priority: Optional[int] = None,
    ) -> bool:
        """
        Writes a 6-register command packet to Layer A holding registers.
        Packet format must match Layer A.
        """
        if "Layer_C" in origin_source or "Machine_C" in origin_source:
            source_code = 3
            prio = int(priority if priority is not None else 3)
        elif "Layer_B" in origin_source or "Machine_B" in origin_source:
            source_code = 2
            prio = int(priority if priority is not None else 2)
        else:
            source_code = 2
            prio = int(priority if priority is not None else 2)

        pos_hi, pos_lo = (0, 0) if pos is None else s32_to_regs(int(pos))
        spd = int(speed if speed is not None else 0) & 0xFFFFFFFF

        regs = [0] * self._hr_cmd_count
        regs[0] = int(cmd) & 0xFFFF
        regs[1] = int(pos_hi) & 0xFFFF
        regs[2] = int(pos_lo) & 0xFFFF
        regs[3] = int(spd) & 0xFFFF
        regs[4] = int(source_code) & 0xFFFF
        regs[5] = int(prio) & 0xFFFF

        with self._lock:
            if not self._ensure_open():
                self._set_connected(False)
                self.log.emit(f"Cannot open Modbus to {self._host}:{self._port}")
                return False
            ok = self._client.write_multiple_registers(self._hr_cmd_addr, regs)

        if not ok:
            self.log.emit(f"Write HR{self._hr_cmd_addr}.. failed: {self._client.last_error_txt}")
            return False

        self.log.emit(f"CMD packet sent to A @HR{self._hr_cmd_addr}: {regs}")
        return True
