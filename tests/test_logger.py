import csv
import tempfile
from pathlib import Path

from datetime import datetime

from ups_monitor.logger import CSVLogger
from ups_monitor.poller import UPSMetrics


def test_csv_logger_writes_rows(tmp_path):
    filename = tmp_path / "ups_metrics.csv"
    logger = CSVLogger(str(filename))
    logger.start()

    metrics = UPSMetrics(timestamp=datetime(2026, 5, 21, 12, 0, 0), voltage=120.0, load=30.5)
    logger.log(metrics)
    logger.stop()

    with open(filename, newline="", encoding="utf-8") as csv_file:
        reader = list(csv.reader(csv_file))

    assert reader[0] == ["timestamp", "voltage", "load"]
    assert reader[1] == ["2026-05-21 12:00:00", "120.00", "30.50"]


def test_csv_logger_export_to(tmp_path: Path):
    source_file = tmp_path / "ups_metrics.csv"
    source_file.write_text("timestamp,voltage,load\n2026-05-22 12:00:00,120.00,35.00\n", encoding="utf-8")

    export_file = tmp_path / "exported_metrics.csv"
    logger = CSVLogger(str(source_file))

    logger.export_to(str(export_file))

    assert export_file.exists()
    assert export_file.read_text(encoding="utf-8") == source_file.read_text(encoding="utf-8")
