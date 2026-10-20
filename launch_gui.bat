@echo off
setlocal
set "PYTHON_CMD=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
if defined KINGAI_PYTHON set "PYTHON_CMD=%KINGAI_PYTHON%"
"%PYTHON_CMD%" -c "import sys; raise SystemExit(sys.version_info < (3,10))" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.10+ is required. Set KINGAI_PYTHON to its executable path.
  exit /b 1
)
"%PYTHON_CMD%" -c "import PySide6" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PySide6 is missing. Run install.bat --gui in a clean project copy.
  exit /b 1
)
"%PYTHON_CMD%" "%~dp0exporter_gui.py" %*
exit /b %errorlevel%
