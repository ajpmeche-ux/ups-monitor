from __future__ import annotations

import re
import subprocess
from typing import Dict, Optional

METRIC_KEYS = ("Voltage", "Load")
HEX_BLOB_RE = re.compile(r"<([0-9a-fA-F\s]+)>")
VALUE_RE = re.compile(r'"?([^\"]+)"?\s*=\s*([0-9]+(?:\.[0-9]+)?|<[^>]+>)')
KEY_RE = re.compile(r'"?(Voltage|Load)"?')

METRIC_KEY_ALIASES = {
    "Voltage": "Voltage",
    "Input Voltage": "Voltage",
    "Output Voltage": "Voltage",
    "Actual Voltage": "Voltage",
    "Estimated Voltage": "Voltage",
    "Measured Voltage": "Voltage",
    "UPS Voltage": "Voltage",
    "Load": "Load",
    "Input Load": "Load",
    "Output Load": "Load",
    "Actual Load": "Load",
    "Estimated Load": "Load",
    "Measured Load": "Load",
    "UPS Load": "Load",
}

ACCEPTED_PREFIXES = {"", "Input", "Output", "Actual", "Estimated", "Measured", "UPS"}


def _metric_for_key(raw_key: str) -> Optional[str]:
    normalized = raw_key.strip().strip('"').strip()
    if normalized in METRIC_KEY_ALIASES:
        return METRIC_KEY_ALIASES[normalized]

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
        if len(hex_bytes) // 2 > 4:
            return None
        try:
            raw = bytes.fromhex(hex_bytes)
            if not raw:
                return None
            parsed = int.from_bytes(raw, byteorder="little", signed=False)
            return float(parsed)
        except ValueError:
            return None

    try:
        return float(value_token)
    except ValueError:
        return None


def parse_ioreg_output(output: str) -> Dict[str, float]:
    metrics: Dict[str, float] = {}

    for match in VALUE_RE.finditer(output):
        raw_key = match.group(1)
        key = _metric_for_key(raw_key)
        if key is None:
            continue
        value_text = match.group(2)
        parsed = _parse_value_token(value_text)
        if parsed is None:
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

        # try to extract numeric tokens and hex blobs from the device subtree
        candidates: list[float] = []
        for line in window.splitlines():
            if re.search(r"Voltage|Load|Power|Watts|Current|Battery|UPS", line, re.IGNORECASE):
                candidates.extend(float(n) for n in re.findall(r"[0-9]+(?:\.[0-9]+)?", line))

        for hx in HEX_BLOB_RE.findall(window):
            hex_text = hx.replace(" ", "")
            if len(hex_text) // 2 > 4:
                continue
            try:
                raw = bytes.fromhex(hex_text)
                if raw:
                    val = int.from_bytes(raw, byteorder="little", signed=False)
                    candidates.append(float(val))
            except ValueError:
                pass

        def choose_voltage(cands: list[float]) -> Optional[float]:
            filtered = [v for v in cands if 85 <= v <= 250]
            if not filtered:
                return None
            targets = (120.0, 230.0)
            return float(min(filtered, key=lambda v: min(abs(v - t) for t in targets)))

        def choose_load(cands: list[float]) -> Optional[float]:
            filtered = [v for v in cands if 0 <= v <= 100]
            if not filtered:
                return None
            return float(max(filtered))

        if "Voltage" not in metrics:
            vol = choose_voltage(candidates)
            if vol is not None:
                metrics["Voltage"] = vol
        if "Load" not in metrics:
            ld = choose_load(candidates)
            if ld is not None:
                metrics["Load"] = ld

    return metrics


def get_ups_metrics() -> Optional[Dict[str, float]]:
    try:
        completed = subprocess.run(
            ["ioreg", "-p", "IOUSB", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = completed.stdout or completed.stderr or ""
        metrics = parse_ioreg_output(output)
        if len(metrics) == len(METRIC_KEYS):
            return metrics
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    return None
