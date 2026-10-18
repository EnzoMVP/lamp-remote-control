"""Launcher without a console window (pythonw) and the PyInstaller entry point."""

import sys

from app.main import main

sys.exit(main())
