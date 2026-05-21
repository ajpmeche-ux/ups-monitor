from __future__ import annotations

import collections
from typing import Deque

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QFrame,
)

from .poller import UPSMetrics


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("UPS Monitor")
        self.resize(1000, 640)

        self._samples: Deque[UPSMetrics] = collections.deque(maxlen=50)

        self.status_label = QLabel("Disconnected")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedHeight(34)
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        self._update_status(False)

        self.voltage_label = QLabel("Voltage: -- V")
        self.voltage_label.setAlignment(Qt.AlignCenter)
        self.voltage_label.setFont(QFont("Arial", 11, QFont.Bold))

        self.load_label = QLabel("Load: -- %")
        self.load_label.setAlignment(Qt.AlignCenter)
        self.load_label.setFont(QFont("Arial", 11, QFont.Bold))

        self.last_updated_label = QLabel("Last update: --")
        self.last_updated_label.setAlignment(Qt.AlignCenter)
        self.last_updated_label.setFont(QFont("Arial", 10))

        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setFont(QFont("Arial", 10))
        self.error_label.setStyleSheet("color: #ffcc00;")
        self.error_label.setVisible(False)

        header_layout = QHBoxLayout()
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.voltage_label)
        header_layout.addWidget(self.load_label)
        header_layout.addWidget(self.last_updated_label)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Voltage (V)", "Load (%)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setFrameShape(QFrame.StyledPanel)

        pg.setConfigOptions(antialias=True)

        self.voltage_chart = pg.PlotWidget()
        self.voltage_chart.setBackground("#111111")
        self.voltage_chart.showGrid(x=True, y=True, alpha=0.3)
        self.voltage_chart.setLabel("left", "Voltage", units="V")
        self.voltage_chart.setLabel("bottom", "Samples")
        self.voltage_chart.setYRange(0, 260)
        self._voltage_curve = self.voltage_chart.plot(pen=pg.mkPen("#8fc31f", width=2), name="Voltage")

        self.load_chart = pg.PlotWidget()
        self.load_chart.setBackground("#111111")
        self.load_chart.showGrid(x=True, y=True, alpha=0.3)
        self.load_chart.setLabel("left", "Load", units="%")
        self.load_chart.setLabel("bottom", "Samples")
        self.load_chart.setYRange(0, 100)
        self._load_curve = self.load_chart.plot(pen=pg.mkPen("#42a5f5", width=2), name="Load")

        layout = QVBoxLayout()
        layout.addLayout(header_layout)
        layout.addWidget(self.error_label)
        layout.addWidget(self.table)
        layout.addWidget(self.voltage_chart)
        layout.addWidget(self.load_chart)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _update_status(self, connected: bool) -> None:
        if connected:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet(
                "background-color: #2e7d32; color: white; border-radius: 6px; padding: 4px;"
            )
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet(
                "background-color: #b71c1c; color: white; border-radius: 6px; padding: 4px;"
            )

    def on_metrics(self, metrics: UPSMetrics) -> None:
        self._samples.append(metrics)
        self.voltage_label.setText(f"Voltage: {metrics.voltage:.2f} V")
        self.load_label.setText(f"Load: {metrics.load:.2f} %")
        self.last_updated_label.setText(f"Last update: {metrics.timestamp.strftime('%H:%M:%S')}")
        self._refresh_table()
        self._refresh_chart()

    def set_connected(self, connected: bool) -> None:
        self._update_status(connected)

    def set_error_message(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self._samples))
        for row, item in enumerate(reversed(self._samples)):
            self.table.setItem(row, 0, QTableWidgetItem(item.timestamp.strftime("%Y-%m-%d %H:%M:%S")))
            self.table.setItem(row, 1, QTableWidgetItem(f"{item.voltage:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{item.load:.2f}"))

    def _refresh_chart(self) -> None:
        x = list(range(len(self._samples)))
        voltages = [entry.voltage for entry in self._samples]
        loads = [entry.load for entry in self._samples]
        self._voltage_curve.setData(x, voltages)
        self._load_curve.setData(x, loads)
