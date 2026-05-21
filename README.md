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
