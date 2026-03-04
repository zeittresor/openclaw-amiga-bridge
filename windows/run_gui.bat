@echo off
setlocal
cd /d %~dp0
call .venv\Scripts\activate.bat 2>nul
python clawbridge_gui.py
