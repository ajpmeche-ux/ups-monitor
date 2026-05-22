from __future__ import annotations

import math
import time
import platform
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QThread, QObject, Signal

from .models import UPSMetrics
from .parser import get_ups_metrics


class UPSPoller(QObject):
    metrics_updated = Signal(object)
    connection_changed = Signal(bool)
    error = Signal(str)

    def __init__(self, poll_interval: float = 2.0, demo: bool = False, debug: bool = False, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.poll_interval = poll_interval
        self._base_interval = poll_interval
        self._running = False
        self._thread: Optional[QThread] = None
        self._last_connected: Optional[bool] = None
        self._failure_count = 0
        self._last_error_message: Optional[str] = None
        self.demo = demo
        self.debug = debug
        self._demo_step = 0

    def _next_demo_metrics(self) -> dict[str, float]:
        voltage = 120.0 + 6.0 * math.sin(self._demo_step * 0.6)
        load = 28.0 + 12.0 * (1.0 + math.cos(self._demo_step * 0.4)) / 2.0
        self._demo_step += 1
        return {"Voltage": round(voltage, 2), "Load": round(load, 2)}

    def _emit_error(self, message: str) -> None:
        if message != self._last_error_message:
            self._last_error_message = message
            self.error.emit(message)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._run)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
            self._thread = None

    def _run(self) -> None:
        if not self.demo and platform.system() != "Darwin":
            self._emit_error("UPS polling is supported only on macOS.")
            return

        while self._running:
            interval = self._base_interval
            try:
                raw_metrics = self._next_demo_metrics() if self.demo else get_ups_metrics(debug=self.debug)
                connected = bool(raw_metrics)

                if self._last_connected is None or connected != self._last_connected:
                    self._last_connected = connected
                    self.connection_changed.emit(connected)

                if connected and raw_metrics is not None:
                    self._failure_count = 0
                    self._emit_error("")
                    metrics = UPSMetrics(
                        timestamp=datetime.now(),
                        voltage=float(raw_metrics["Voltage"]),
                        load=float(raw_metrics["Load"]),
                    )
                    self.metrics_updated.emit(metrics)
                else:
                    self._failure_count += 1
                    backoff_steps = min(self._failure_count - 1, 5)
                    interval = min(self._base_interval * (2 ** backoff_steps), 60.0)
                    if self._failure_count == 1 or self._failure_count % 5 == 0:
                        self._emit_error("UPS disconnected or not found. Reconnecting...")

            except Exception as exc:  # noqa: BLE001
                self._failure_count += 1
                interval = min(self._base_interval * (2 ** min(self._failure_count - 1, 5)), 60.0)
                self._emit_error(f"Polling error: {exc}")

            elapsed = 0.0
            while self._running and elapsed < interval:
                time.sleep(0.1)
                elapsed += 0.1
