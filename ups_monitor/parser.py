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
