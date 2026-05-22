from __future__ import annotations

import re
import subprocess
from typing import Dict, Optional

METRIC_KEYS = ("Voltage", "Load")
HEX_BLOB_RE = re.compile(r"<([0-9a-fA-F\s]+)>")
HEX_LITERAL_RE = re.compile(r"0x([0-9a-fA-F]+)")
VALUE_RE = re.compile(r'"?([^\"]+)"?\s*=\s*(0x[0-9a-fA-F]+|<[^>]+>|[0-9]+(?:\.[0-9]+)?)')

# Word-boundary patterns prevent false matches like "Offload" → Load, "VoltageRegulator" fragments
_WORD_VOLTAGE_RE = re.compile(r'\bvoltage\b', re.IGNORECASE)
_WORD_LOAD_RE = re.compile(r'\bload\b', re.IGNORECASE)

# Matches the IOKitDiagnostics blob line — contains thousands of ClassName=N pairs
# that cause massive false-positive scanning. We skip it entirely.
# ioreg prefixes lines with tree chars (spaces and |) before the key name.
_IOKIT_DIAG_RE = re.compile(r'^[|\s]*"?IOKitDiagnostics"?\s*=')

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

    # Word-boundary match only: prevents "Offload", "Download", "VoltageRegulator" etc.
    if _WORD_VOLTAGE_RE.search(normalized):
        return "Voltage"
    if _WORD_LOAD_RE.search(normalized):
        return "Load"
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
        # Skip large blobs (hashes, UUIDs, etc.) — no UPS metric needs more than 4 bytes
        if len(hex_bytes) > 8:
            return None
        try:
            raw = bytes.fromhex(hex_bytes)
            if not raw:
                return None
            parsed = int.from_bytes(raw, byteorder="little", signed=False)
            return float(parsed)
        except (ValueError, OverflowError):
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

    # Drop the IOKitDiagnostics line — it embeds thousands of ClassName=N pairs
    # that generate massive false-positive hits with no UPS relevance.
    filtered_lines = [l for l in output.splitlines() if not _IOKIT_DIAG_RE.match(l)]
    filtered = "\n".join(filtered_lines)

    for match in VALUE_RE.finditer(filtered):
        raw_key = match.group(1)
        key = _metric_for_key(raw_key)
        if key is None:
            continue
        value_text = match.group(2)
        parsed = _parse_value_token(value_text)
        if parsed is None:
            continue

        _debug_print(debug, f"[debug] hit key={raw_key!r} -> {key!r}, value={value_text!r}, parsed={parsed}")

        if key == "Voltage" and not (85 <= parsed <= 250):
            _debug_print(debug, f"[debug]   skipped: voltage {parsed} out of range 85-250")
            continue
        if key == "Load" and not (0 <= parsed <= 100):
            _debug_print(debug, f"[debug]   skipped: load {parsed} out of range 0-100")
            continue
        metrics[key] = parsed

    if len(metrics) == len(METRIC_KEYS):
        return metrics

    # Fallback: scan line by line for key + nearby number
    for line in filtered_lines:
        for key in METRIC_KEYS:
            if _line_contains_metric(line, key) and key not in metrics:
                numbers = re.findall(r"[0-9]+(?:\.[0-9]+)?", line)
                if numbers:
                    value = float(numbers[-1])
                    _debug_print(debug, f"[debug] fallback line key={key}, value={value}, line={line!r}")
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


def _run_hid_ups_query(debug: bool = False) -> Optional[Dict[str, float]]:
    """Search IOService IOHIDDevice entries for UPS metrics (macOS HID power device path)."""
    try:
        completed = subprocess.run(
            ["ioreg", "-p", "IOService", "-c", "IOHIDDevice", "-l"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        output = completed.stdout or ""
        _debug_print(debug, f"[debug] IOHIDDevice query: {len(output)} bytes")

        if not re.search(r"UPS|APC|Back-UPS|Power Conversion|051[Dd]|1309", output, re.IGNORECASE):
            _debug_print(debug, "[debug] IOHIDDevice: no UPS/APC signature found")
            return None

        metrics = parse_ioreg_output(output, debug=debug)
        _debug_print(debug, f"[debug] IOHIDDevice parsed: {metrics}")
        return metrics if len(metrics) == len(METRIC_KEYS) else None
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        _debug_print(debug, f"[debug] IOHIDDevice query failed: {exc}")
        return None


# Matches both pmset UPS output formats:
#   new: " UPS Power:  100%; fully charged; (no estimate)"
#   old: " -Back-UPS NS 1500M2 ...  (id=22675456)\t100%; AC attached; not charging present: true"
_PMSET_UPS_RE = re.compile(
    r"(?:UPS\s+Power\s*:|\(id=\d+\))\s+(\d+)%\s*;\s*([^;\n]+)",
    re.IGNORECASE,
)


def _parse_pmset_batt(debug: bool = False) -> Optional[Dict[str, float]]:
    """Fall back to pmset for macOS-managed UPS.

    Voltage is 120.0 V (AC nominal) when charging/charged, 0.0 V when on battery.
    Load is battery charge percentage (the only value pmset exposes).
    """
    try:
        completed = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = completed.stdout or ""
        _debug_print(debug, f"[debug] pmset output:\n{output.rstrip()}")

        match = _PMSET_UPS_RE.search(output)
        if not match:
            _debug_print(debug, "[debug] pmset: no 'UPS Power' line found")
            return None

        charge_pct = float(match.group(1))
        status = match.group(2).strip().lower()
        on_battery = "discharging" in status
        voltage = 0.0 if on_battery else 120.0

        _debug_print(
            debug,
            f"[debug] pmset: charge={charge_pct}%, status={status!r}, "
            f"on_battery={on_battery}, voltage={voltage}",
        )

        if 0.0 <= charge_pct <= 100.0:
            return {"Voltage": voltage, "Load": charge_pct}
        return None
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        _debug_print(debug, f"[debug] pmset query failed: {exc}")
        return None


def get_ups_metrics(debug: bool = False) -> Optional[Dict[str, float]]:
    for plane in ("IOUSB", "IOPower"):
        metrics = _run_ioreg_query(plane, debug=debug)
        if metrics is not None:
            return metrics

    metrics = _run_hid_ups_query(debug=debug)
    if metrics is not None:
        return metrics

    return _parse_pmset_batt(debug=debug)
