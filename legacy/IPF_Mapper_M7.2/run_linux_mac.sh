#!/usr/bin/env sh
cd "$(dirname "$0")"
python3 -c "import PySide6" 2>/dev/null || python3 -m pip install -r requirements.txt
python3 main.py
