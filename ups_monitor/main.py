from __future__ import annotations

import platform
import sys

from PySide6.QtWidgets import QApplication

from .logger import CSVLogger
from .poller import UPSPoller
from .ui import MainWindow


def main() -> int:
    if platform.system() != "Darwin":
        print("This UPS Monitor app is designed to run on macOS.")
        return 1

    app = QApplication(sys.argv)
    logger = CSVLogger("ups_metrics.csv")
    logger.start()

    window = MainWindow()

    poller = UPSPoller(poll_interval=2.0)
    poller.metrics_updated.connect(window.on_metrics)
    poller.metrics_updated.connect(logger.log)
    poller.connection_changed.connect(window.set_connected)
    poller.error.connect(window.set_error_message)

    def stop_all() -> None:
        poller.stop()
        logger.stop()

    window.destroyed.connect(lambda _: stop_all())
    window.show()
    poller.start()

    try:
        return app.exec()
    finally:
        stop_all()


if __name__ == "__main__":
    raise SystemExit(main())
