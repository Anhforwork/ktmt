"""
Entry point for Layer B SCADA Supervisor.

Install deps:
  pip install pyqt5 pyModbusTCP==0.3.0
Run:
  python main.py
"""
import sys

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor

import config
from modbus_service import ModbusService
from c_server import JsonTcpServer
from ui import LayerBMainWindow


def apply_fusion_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#f6f7fb"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f3f4f6"))
    pal.setColor(QPalette.Button, QColor("#eef2ff"))
    pal.setColor(QPalette.Text, QColor("#111827"))
    pal.setColor(QPalette.ButtonText, QColor("#111827"))
    pal.setColor(QPalette.Highlight, QColor("#6366f1"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)


def main() -> int:
    app = QApplication(sys.argv)
    apply_fusion_theme(app)

    modbus = ModbusService(
        host=config.A_HOST,
        port=config.A_MODBUS_PORT,
        ir_base=config.A_IR_BASE_ADDR,
        ir_count=config.A_IR_COUNT,
        hr_target_addr=config.A_HR_TARGET_ADDR,
        hr_mode_addr=config.A_HR_MODE_ADDR,
        hr_cmd_addr=config.A_HR_CMD_ADDR,
        hr_cmd_count=config.A_HR_CMD_REG_COUNT,
        poll_interval_s=0.5,
        timeout_s=3.0,
    )

    server_c = JsonTcpServer(port=config.SERVER_PORT, buffer_size=config.BUFFER_SIZE)

    win = LayerBMainWindow(modbus, server_c)
    win.show()

    # start background services
    modbus.start()
    server_c.start()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
