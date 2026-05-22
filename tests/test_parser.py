import pytest

from ups_monitor.parser import parse_ioreg_output


def test_parse_ioreg_output_decimal_values():
    sample = '''
        "Voltage" = 120
        "Load" = 35
    '''
    metrics = parse_ioreg_output(sample)
    assert metrics["Voltage"] == 120.0
    assert metrics["Load"] == 35.0


def test_parse_ioreg_output_hex_blob():
    sample = '''
        "Voltage" = <78 00 00 00>
        "Load" = <23 00 00 00>
    '''
    metrics = parse_ioreg_output(sample)
    assert metrics["Voltage"] == 120.0
    assert metrics["Load"] == 35.0


def test_parse_ioreg_output_missing_values():
    sample = '"Voltage" = 120'
    metrics = parse_ioreg_output(sample)
    assert "Load" not in metrics
    assert metrics.get("Voltage") == 120.0


def test_parse_ioreg_output_load_range_filtering():
    sample = '''
        "USB Product Name" = "Back-UPS NS 1500M2"
        "Vendor ID" = 0x051d
        "Actual Load" = 42
        "Large Load" = 100000000
    '''
    metrics = parse_ioreg_output(sample)
    assert metrics["Load"] == 42.0
    assert metrics["Load"] <= 100.0
