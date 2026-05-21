import csv
import tempfile

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
