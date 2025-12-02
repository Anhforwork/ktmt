"""
TCP JSON line server for Layer C -> Layer B.

Protocol: each JSON object is sent as a single line ended by '\n'.
"""
from __future__ import annotations

import json
import socket
import threading
from typing import Optional, Dict

from PyQt5.QtCore import QObject, pyqtSignal


class JsonTcpServer(QObject):
    log = pyqtSignal(str)
    connection_changed = pyqtSignal(str)  # "Connected" / "Waiting for connection..." / "Error"
    command_received = pyqtSignal(dict)

    def __init__(self, port: int, buffer_size: int = 4096, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._port = int(port)
        self._buffer_size = int(buffer_size)

        self._server_sock: Optional[socket.socket] = None
        self._client_sock: Optional[socket.socket] = None
        self._client_lock = threading.Lock()

        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ---------- lifecycle ----------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.connection_changed.emit("Waiting for connection...")
        self.log.emit(f"Server for Layer C started on port {self._port}")

    def stop(self) -> None:
        self._stop_evt.set()
        self._close_client()
        try:
            if self._server_sock:
                self._server_sock.close()
        except Exception:
            pass
        self._server_sock = None
        self.log.emit("JsonTcpServer stopped")

    # ---------- sending ----------
    def send(self, data: Dict) -> None:
        """
        Best-effort send to connected client. Safe to call from UI thread.
        """
        with self._client_lock:
            sock = self._client_sock
        if not sock:
            return
        try:
            msg = json.dumps(data) + "\n"
            sock.sendall(msg.encode("utf-8"))
        except Exception as e:
            self.log.emit(f"Send to C error: {e}")
            self._close_client()

    # ---------- internals ----------
    def _close_client(self) -> None:
        with self._client_lock:
            sock = self._client_sock
            self._client_sock = None
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        self.connection_changed.emit("Waiting for connection...")

    def _run(self) -> None:
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind(("0.0.0.0", self._port))
            self._server_sock.listen(1)
            self._server_sock.settimeout(1.0)

            while not self._stop_evt.is_set():
                try:
                    client, addr = self._server_sock.accept()
                except socket.timeout:
                    continue

                # replace existing client if any
                self._close_client()
                with self._client_lock:
                    self._client_sock = client

                self.connection_changed.emit("Connected")
                self.log.emit(f"Layer C connected: {addr}")

                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()

        except Exception as e:
            self.log.emit(f"Server for C error: {e}")
            self.connection_changed.emit("Error")

    def _handle_client(self, client: socket.socket) -> None:
        buffer = ""
        try:
            while not self._stop_evt.is_set():
                data = client.recv(self._buffer_size).decode("utf-8", errors="replace")
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        cmd = json.loads(line)
                        if isinstance(cmd, dict):
                            self.command_received.emit(cmd)
                        else:
                            self.log.emit("Rejected: command is not a JSON object")
                    except json.JSONDecodeError as e:
                        self.log.emit(f"JSON error from C: {e}")
        except Exception as e:
            self.log.emit(f"Error from C: {e}")
        finally:
            # close if it's still the active client
            with self._client_lock:
                still_active = (self._client_sock is client)
            if still_active:
                self._close_client()
            try:
                client.close()
            except Exception:
                pass
            self.log.emit("Layer C disconnected")
