from __future__ import annotations

import re
import subprocess
from typing import Dict, Optional

METRIC_KEYS = ("Voltage", "Load")
HEX_BLOB_RE = re.compile(r"<([0-9a-fA-F\s]+)>")
HEX_LITERAL_RE = re.compile(r"0x([0-9a-fA-F]+)")
VALUE_RE = re.compile(r'"?([^\"]+)"?\s*=\s*(0x[0-9a-fA-F]+|<[^>]+>|[0-9]+(?:\.[0-9]+)?)')
KEY_RE = re.compile(r'"?(Voltage|Load)"?')

METRIC_KEY_ALIASES = {
    "Voltage": "Voltage",
    "Input Voltage": "Voltage",
    "Output Voltage": "Voltage",
    "Line Voltage": "Voltage",
    "Actual Voltage": "Voltage",
    "Estimated Voltage": "Voltage",
    "Measured Voltage": "Voltage",
    "UPS Voltage": "Voltage",
    "Load": "Load",
    "Input Load": "Load",
    "Output Load": "Load",
    "Line Load": "Load",
    "Actual Load": "Load",
    "Estimated Load": "Load",
    "Measured Load": "Load",
    "UPS Load": "Load",
    "Load Percentage": "Load",
    "Battery Load": "Load",
}

ACCEPTED_PREFIXES = {"", "Input", "Output", "Line", "Actual", "Estimated", "Measured", "UPS"}


def _debug_print(enabled: bool, *args) -> None:
    if enabled:
        print(*args)


def _metric_for_key(raw_key: str) -> Optional[str]:
    normalized = raw_key.strip().strip('"').strip()
    lower_key = normalized.lower()

    if normalized in METRIC_KEY_ALIASES:
        return METRIC_KEY_ALIASES[normalized]
    if lower_key in (key.lower() for key in METRIC_KEY_ALIASES):
        return METRIC_KEY_ALIASES[next(key for key in METRIC_KEY_ALIASES if key.lower() == lower_key)]

    if "voltage" in lower_key:
        return "Voltage"
    if "load" in lower_key:
        return "Load"

    for suffix in ("Voltage", "Load"):
        if normalized.endswith(suffix):
            prefix = normalized[: -len(suffix)].strip()
            if prefix in ACCEPTED_PREFIXES:
                return suffix
    return None


def _line_contains_metric(line: str, key: str) -> bool:
    prefixes = "|".join(re.escape(prefix) for prefix in ACCEPTED_PREFIXES if prefix)
    pattern = rf'(?:(?:^|["\s])(?:{prefixes})\s+)?{re.escape(key)}(?:$|["\s])'
    return re.search(pattern, line, re.IGNORECASE) is not None


def _parse_value_token(value_token: str) -> Optional[float]:
    value_token = value_token.strip()

    if value_token.startswith("<") and value_token.endswith(">"):
        match = HEX_BLOB_RE.match(value_token)
        if not match:
            return None
        hex_bytes = match.group(1).replace(" ", "")
        try:
            raw = bytes.fromhex(hex_bytes)
            if not raw:
                return None
            parsed = int.from_bytes(raw, byteorder="little", signed=False)
            return float(parsed)
        except ValueError:
            return None

    if value_token.startswith("0x") or value_token.startswith("0X"):
        match = HEX_LITERAL_RE.match(value_token)
        if match:
            try:
                return float(int(match.group(1), 16))
            except ValueError:
                return None

    try:
        return float(value_token)
    except ValueError:
        return None


def parse_ioreg_output(output: str, debug: bool = False) -> Dict[str, float]:
    metrics: Dict[str, float] = {}

    if debug:
        _debug_print(debug, f"[debug] scanning output for metric aliases")

    for match in VALUE_RE.finditer(output):
        raw_key = match.group(1)
        key = _metric_for_key(raw_key)
        value_text = match.group(2)
        parsed = _parse_value_token(value_text)

        if debug:
            _debug_print(debug, f"[debug] candidate key={raw_key!r} -> {key!r}, value={value_text!r}, parsed={parsed}")

        if key is None or parsed is None:
            continue
        if key == "Voltage" and not (85 <= parsed <= 250):
            continue
        if key == "Load" and not (0 <= parsed <= 100):
            continue
        metrics[key] = parsed

    if len(metrics) == len(METRIC_KEYS):
        return metrics

    # fallback extraction by key and numeric token on the same line
    for line in output.splitlines():
        for key in METRIC_KEYS:
            if _line_contains_metric(line, key) and key not in metrics:
                numbers = re.findall(r"[0-9]+(?:\.[0-9]+)?", line)
                if numbers:
                    value = float(numbers[-1])
                    if debug:
                        _debug_print(debug, f"[debug] fallback candidate line={line!r}, key={key}, value={value}")
                    if key == "Voltage" and 85 <= value <= 250:
                        metrics[key] = value
                    elif key == "Load" and 0 <= value <= 100:
                        metrics[key] = value

    # If still incomplete, try APC / Back-UPS specific heuristics
    apc_match = re.search(r"Back-UPS|American Power Conversion|idVendor\"?\s*=\s*1309|Vendor ID:\s*0x051d",
                          output,
                          re.IGNORECASE)
    if apc_match and (len(metrics) != len(METRIC_KEYS)):
        lines = output.splitlines()
        # find first occurrence line index for the device name
        start_idx = 0
        for i, ln in enumerate(lines):
            if re.search(r"Back-UPS|American Power Conversion", ln, re.IGNORECASE):
                start_idx = i
                break

        window = "\n".join(lines[start_idx : start_idx + 120])

        # try to extract explicit voltage/load aliases from the device subtree
        found_metrics: Dict[str, float] = {}
        for match in VALUE_RE.finditer(window):
            raw_key = match.group(1)
            key = _metric_for_key(raw_key)
            value_text = match.group(2)
            parsed = _parse_value_token(value_text)
            if debug:
                _debug_print(debug, f"[debug] subtree candidate key={raw_key!r} -> {key!r}, value={value_text!r}, parsed={parsed}")
            if key is None or parsed is None:
                continue
            if key == "Voltage" and not (85 <= parsed <= 250):
                continue
            if key == "Load" and not (0 <= parsed <= 100):
                continue
            found_metrics[key] = parsed

        if debug and not found_metrics:
            for i, line in enumerate(window.splitlines(), start=1):
                if re.search(r"Voltage|Load|Power|Watts|Current|Battery|UPS", line, re.IGNORECASE):
                    _debug_print(debug, f"[debug] subtree match line {i}: {line}")

        for key, value in found_metrics.items():
            if key not in metrics:
                metrics[key] = value

    return metrics


def _run_ioreg_query(plane: str, debug: bool = False) -> Optional[Dict[str, float]]:
    try:
        completed = subprocess.run(
            ["ioreg", "-p", plane, "-l"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        output = completed.stdout or completed.stderr or ""
        _debug_print(debug, f"[debug] ioreg plane={plane}, output length={len(output)}")
        metrics = parse_ioreg_output(output, debug=debug)
        _debug_print(debug, f"[debug] parsed {metrics} from plane {plane}")
        return metrics if len(metrics) == len(METRIC_KEYS) else None
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        _debug_print(debug, f"[debug] ioreg query failed for plane={plane}: {exc}")
        return None


def get_ups_metrics(debug: bool = False) -> Optional[Dict[str, float]]:
    for plane in ("IOUSB", "IOPower"):
        metrics = _run_ioreg_query(plane, debug=debug)
        if metrics is not None:
            return metrics
    return None
