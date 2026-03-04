@echo off
setlocal
cd /d %~dp0
call .venv\Scripts\activate.bat 2>nul

REM Example base path on Windows (adjust!)
set BASE=C:\Amiga\Shared\openclaw

python clawbridge.py send --base "%BASE%" --cmd "version" --wait
python clawbridge.py snap --base "%BASE%" --window "WinUAE" --open
