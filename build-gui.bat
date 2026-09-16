@echo off
cd /d "%~dp0"
py -3 -m pip install -e ".[gui]"
py -3 -m pip install -U pyinstaller
py -3 devscripts\build_gui.py %*
