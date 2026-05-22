#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo " UPS Monitor Diagnostic"
echo " $(date)"
echo "============================================================"
echo

echo "--- IOUSB plane (UPS/power-related entries) ---"
ioreg -p IOUSB -w0 -l | grep -nE 'UPS|APC|Voltage|Load|Current|Battery|Manufacturer|Product|Vendor|idVendor|idProduct|051d|1309' || echo "(nothing matched)"

echo
echo "--- IOPower plane (UPS/power-related entries) ---"
ioreg -p IOPower -w0 -l | grep -nE 'UPS|APC|Voltage|Load|Current|Battery|Manufacturer|Product|Vendor' || echo "(nothing matched)"

echo
echo "--- IOService plane (UPS/power-related entries) ---"
ioreg -p IOService -w0 -l | grep -nE 'UPS|APC|Voltage|Load|Current|Battery|Manufacturer|Product|idVendor|051d|1309' || echo "(nothing matched)"

echo
echo "--- APC vendor device subtree (IOService, vendor 0x051d) ---"
ioreg -p IOService -w0 -l | awk '
  /051d|APC|Back-UPS|American Power/{found=1; depth=0}
  found {
    print NR": "$0
    if (/\{/) depth++
    if (/\}/) { depth--; if (depth<=0) {found=0} }
  }
' | head -200 || echo "(no APC vendor block found)"

echo
if command -v system_profiler >/dev/null 2>&1; then
  echo "--- system_profiler USB summary ---"
  system_profiler SPUSBDataType | grep -nE 'UPS|APC|Battery|Manufacturer|Product Name|Vendor|Current Available|Current Required' || echo "(nothing matched)"
fi

echo
echo "--- All USB devices (name + vendor) ---"
system_profiler SPUSBDataType 2>/dev/null | grep -E '^\s+(Product Name|Vendor Name|Manufacturer|Location ID):' | head -60 || echo "(system_profiler not available)"

echo
echo "--- pmset UPS status (macOS power management) ---"
pmset -g batt || echo "(pmset not available)"

echo
echo "--- IOService HID devices (UPS-related) ---"
ioreg -p IOService -c IOHIDDevice -w0 -l | grep -i -B2 -A30 'UPS|APC|Back-UPS|Power Conversion|051[Dd]|1309' || echo "(no UPS HID device found)"

echo
echo "============================================================"
echo " If the UPS appears above but Voltage/Load fields are missing,"
echo " copy this output and share it so the parser can be updated."
echo "============================================================"
