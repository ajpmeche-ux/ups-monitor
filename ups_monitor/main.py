from __future__ import annotations

import argparse
import platform
import sys
from typing import Optional

from PySide6.QtWidgets import QApplication

from .logger import CSVLogger
from .poller import UPSPoller
from .ui import MainWindow


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="UPS Monitor for APC UPS devices on macOS")
    parser.add_argument("--demo", action="store_true", help="Run the interface with simulated UPS metrics")
    parser.add_argument("--debug", action="store_true", help="Print debug diagnostics from ioreg polling")
    args = parser.parse_args(argv or sys.argv[1:])

    if not args.demo and platform.system() != "Darwin":
        print("This UPS Monitor app is designed to run on macOS unless --demo is enabled.")
        return 1

    app = QApplication(sys.argv)
    logger = CSVLogger("ups_metrics.csv")
    logger.start()

    window = MainWindow()

    poller = UPSPoller(poll_interval=2.0, demo=args.demo, debug=args.debug)
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
