from __future__ import annotations

import csv
import os
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from .poller import UPSMetrics


class CSVLogger:
    def __init__(self, filename: str = "ups_metrics.csv"):
        self.filename = Path(filename)
        self._queue: queue.Queue[Optional[UPSMetrics]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def log(self, metrics: UPSMetrics) -> None:
        if not self._stop_event.is_set():
            self._queue.put(metrics)

    def _worker(self) -> None:
        create_header = not self.filename.exists() or self.filename.stat().st_size == 0
        os.makedirs(self.filename.parent, exist_ok=True)

        with open(self.filename, "a", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            if create_header:
                with self._lock:
                    writer.writerow(["timestamp", "voltage", "load"])
                    csv_file.flush()

            while True:
                item = self._queue.get()
                if item is None:
                    break
                with self._lock:
                    writer.writerow([
                        item.timestamp.isoformat(sep=" ", timespec="seconds"),
                        f"{item.voltage:.2f}",
                        f"{item.load:.2f}",
                    ])
                    csv_file.flush()

    def export_to(self, destination: str) -> None:
        destination_path = Path(destination)
        if not self.filename.exists():
            raise FileNotFoundError(f"Source log file not found: {self.filename}")

        os.makedirs(destination_path.parent, exist_ok=True)
        with self._lock:
            with open(self.filename, "r", encoding="utf-8") as source_file:
                with open(destination_path, "w", newline="", encoding="utf-8") as destination_file:
                    destination_file.write(source_file.read())
