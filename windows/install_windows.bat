@echo off
setlocal
cd /d %~dp0

if not exist .venv (
  py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo OK. Now run:
echo   run_gui.bat
echo or:
echo   python clawbridge.py --help
echo.
pause
