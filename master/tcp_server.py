import socket
import threading
import json
from PyQt5.QtCore import QObject, pyqtSignal

from utils import SignalEmitter

# Configuration
SERVER_PORT = 5002
BUFFER_SIZE = 4096


class TCPServerForC(QObject):
    command_received = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.signals = SignalEmitter()
        self.server_socket = None
        self.client_c = None
        self.running = True
        
        self._start_server()

    def _start_server(self):
        def server_thread():
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind(("0.0.0.0", SERVER_PORT))
                self.server_socket.listen(1)

                self.signals.log_signal.emit(f"Server for Layer C started on port {SERVER_PORT}")

                while self.running:
                    try:
                        self.server_socket.settimeout(1.0)
                        client, addr = self.server_socket.accept()

                        if self.client_c:
                            try:
                                self.client_c.close()
                            except:
                                pass

                        self.client_c = client
                        self.signals.connection_signal.emit("c", "Connected")
                        self.signals.log_signal.emit(f"Layer C connected: {addr}")

                        threading.Thread(target=self._handle_client,
                                       args=(client,), daemon=True).start()
                    except socket.timeout:
                        continue
            except Exception as e:
                self.signals.log_signal.emit(f"Server for C error: {e}")

        threading.Thread(target=server_thread, daemon=True).start()

    def _handle_client(self, client):
        buffer = ""
        try:
            while self.running:
                data = client.recv(BUFFER_SIZE).decode('utf-8')
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            command = json.loads(line)
                            self._handle_command(command)
                        except json.JSONDecodeError as e:
                            self.signals.log_signal.emit(f"JSON error from C: {e}")
        except Exception as e:
            self.signals.log_signal.emit(f"Error from C: {e}")
        finally:
            if client is self.client_c:
                self.client_c = None
            try:
                client.close()
            except:
                pass
            self.signals.connection_signal.emit("c", "Waiting for connection...")
            self.signals.log_signal.emit("Layer C disconnected")

    def _handle_command(self, command):
        cmd_type = command.get('type')
        source = command.get('source', 'Layer_C')

        if cmd_type == 'heartbeat':
            return

        self.signals.forward_signal.emit(cmd_type)
        self.signals.log_signal.emit(f"Received from C: {cmd_type}")

        allowed = {'motor_control', 'jog_control', 'stop_motor',
                   'release_control', 'emergency_stop', 'set_mode'}
        if cmd_type not in allowed:
            self.signals.log_signal.emit(f"Rejected: unsupported command '{cmd_type}'")
            return

        self.command_received.emit(command)

    def send_to_c(self, data):
        if not self.client_c:
            return
        try:
            message = json.dumps(data) + '\n'
            self.client_c.sendall(message.encode('utf-8'))
        except Exception as e:
            self.signals.log_signal.emit(f"Send to C error: {e}")
            self.client_c = None

    def stop(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        if self.client_c:
            try:
                self.client_c.close()
            except:
                pass