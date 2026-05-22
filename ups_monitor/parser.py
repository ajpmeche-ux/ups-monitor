from __future__ import annotations

import re
import subprocess
from typing import Dict, Optional

METRIC_KEYS = ("Voltage", "Load")
HEX_BLOB_RE = re.compile(r"<([0-9a-fA-F\s]+)>")
VALUE_RE = re.compile(r'"?([A-Za-z]+)"?\s*=\s*([0-9]+(?:\.[0-9]+)?|<[^>]+>)')
KEY_RE = re.compile(r'"?(Voltage|Load)"?')


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

    try:
        return float(value_token)
    except ValueError:
        return None


def parse_ioreg_output(output: str) -> Dict[str, float]:
    metrics: Dict[str, float] = {}

    for match in VALUE_RE.finditer(output):
        key = match.group(1)
        if key not in METRIC_KEYS:
            continue
        value_text = match.group(2)
        parsed = _parse_value_token(value_text)
        if parsed is not None:
            metrics[key] = parsed

    if len(metrics) == len(METRIC_KEYS):
        return metrics

    # fallback extraction by key and numeric token on the same line
    for line in output.splitlines():
        for key in METRIC_KEYS:
            if key in line and key not in metrics:
                numbers = re.findall(r"[0-9]+(?:\.[0-9]+)?", line)
                if numbers:
                    metrics[key] = float(numbers[-1])

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
        nums = [float(n) for n in re.findall(r"[0-9]+(?:\.[0-9]+)?", window)]
        hex_matches = HEX_BLOB_RE.findall(window)
        for hx in hex_matches:
            try:
                raw = bytes.fromhex(hx.replace(" ", ""))
                if raw:
                    val = int.from_bytes(raw, byteorder="little", signed=False)
                    nums.append(float(val))
            except ValueError:
                pass

        def choose_voltage(candidates: list[float]) -> Optional[float]:
            if not candidates:
                return None
            # prefer ~120 or ~230 values
            targets = (120.0, 230.0)
            best = min(candidates, key=lambda v: min(abs(v - t) for t in targets))
            return float(best)

        def choose_load(candidates: list[float]) -> Optional[float]:
            if not candidates:
                return None
            # prefer percentage-like values 0-100
            pct = [v for v in candidates if 0 <= v <= 100]
            if pct:
                return float(max(pct))
            # fallback: choose a value that looks like watts (<5000)
            watts = [v for v in candidates if 0 <= v <= 5000]
            if watts:
                return float(max(watts))
            return None

        vol = choose_voltage(nums)
        ld = choose_load(nums)
        if vol is not None and "Voltage" not in metrics:
            metrics["Voltage"] = vol
        if ld is not None and "Load" not in metrics:
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
