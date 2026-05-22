from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from ups_monitor.poller import UPSPoller, UPSMetrics


def test_poller_emits_metrics_demo():
    app = QCoreApplication.instance() or QCoreApplication([])
    poller = UPSPoller(poll_interval=0.1, demo=True)

    received = []
    connected_states = []

    def on_metrics(metrics):
        received.append(metrics)

    def on_connection(connected):
        connected_states.append(connected)

    poller.metrics_updated.connect(on_metrics)
    poller.connection_changed.connect(on_connection)

    poller.start()
    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec()
    poller.stop()

    assert len(received) >= 1
    assert all(isinstance(metric, UPSMetrics) for metric in received)
    assert connected_states == [True]
