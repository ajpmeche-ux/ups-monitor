# UPS Monitor

A macOS desktop monitor for APC UPS power metrics.

## Features
- Polls macOS `ioreg` output for `Voltage` and `Load`
- Displays the last 50 samples in a live updating table
- Shows a connected/disconnected status indicator
- Draws a live voltage chart using `pyqtgraph`
- Logs metrics asynchronously to `ups_metrics.csv`

## Requirements
- macOS (Intel or Apple Silicon)
- Python 3.11+
- `PySide6`
- `pyqtgraph`

## Installation
```bash
pip install -r requirements.txt
```

## Run
```bash
python -m ups_monitor
```

## Packaging for macOS
Install packaging tools and build the app:
```bash
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python setup.py py2app
```

The resulting macOS bundle will be available in `dist/UPS Monitor.app`.

## Testing
```bash
pytest -q
```

## Remote macOS installation

To install this app on a remote macOS machine, use the following commands:

```bash
ssh user@remote-machine
cd /path/where/you/want/it
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install git+https://github.com/ajpmeche-ux/ups-monitor.git
```

## Offline UI testing

You can run the app without a UPS connection using demo mode:

```bash
python -m ups_monitor --demo
```

This will show the full interface, charts, and sample data even when the UPS is unavailable.

## Debugging a connected UPS

If macOS shows the UPS as connected but the app still says "Disconnected", run the diagnostic helper on that machine:

```bash
bash scripts/check_ups.sh
```

This will print `ioreg` and USB device data related to UPS/Power devices.

If the checker shows the UPS but does not expose `Voltage` and `Load` fields, the current app parser will not detect it yet. I can then update the parser to support your device's actual property names.

Or clone the repo and install locally:

```bash
ssh user@remote-machine
cd /path/where/you/want/it
git clone https://github.com/ajpmeche-ux/ups-monitor.git
cd ups-monitor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Then run the app:

```bash
source .venv/bin/activate
python -m ups_monitor
```

If you want a one-shot install script, use `scripts/install_remote.sh`:

```bash
ssh user@remote-machine
bash -s < <(curl -fsSL https://raw.githubusercontent.com/ajpmeche-ux/ups-monitor/main/scripts/install_remote.sh)
```

## Publishing to GitHub

To create a public repository:

```bash
git init
git add .
git commit -m "Initial UPS Monitor app implementation"
```

Then create a repository on GitHub and add the remote:

```bash
git remote add origin https://github.com/<your-username>/ups-monitor.git
git branch -M main
git push -u origin main
```

A GitHub Actions workflow is included at `.github/workflows/python-app.yml` to run tests on each push and pull request.
