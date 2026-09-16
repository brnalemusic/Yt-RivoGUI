#!/usr/bin/env python3
"""Root forwarder to devscripts/update-version.py."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == '__main__':
    target = Path(__file__).resolve().parent / 'devscripts' / 'update-version.py'
    runpy.run_path(str(target), run_name='__main__')
