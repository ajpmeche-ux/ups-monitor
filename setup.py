from setuptools import setup

APP = ["ups_monitor/main.py"]
OPTIONS = {
    "argv_emulation": False,
    "packages": ["ups_monitor"],
    "includes": ["PySide6", "pyqtgraph", "numpy"],
    "plist": {
        "CFBundleName": "UPS Monitor",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleIdentifier": "com.example.upsmonitor",
        "NSHighResolutionCapable": True,
    },
    "arch": "universal2",
    "semi_standalone": True,
}

setup(
    app=APP,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
