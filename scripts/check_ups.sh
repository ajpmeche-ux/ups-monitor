#!/usr/bin/env bash
set -euo pipefail

echo "Checking macOS UPS visibility via ioreg..."

ioreg -p IOUSB -w0 -l | grep -nE 'UPS|APC|Voltage|Load|Current|Battery|Manufacturer|Product|Vendor' || true

echo
if command -v system_profiler >/dev/null 2>&1; then
  echo "Also checking USB device summary..."
  system_profiler SPUSBDataType | grep -nE 'UPS|APC|Battery|Manufacturer|Product|Vendor' || true
fi
