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
if "%~1"=="" (
  "%PYTHON_CMD%" "%~dp0tunerpro_exporter.py" --help
) else (
  "%PYTHON_CMD%" "%~dp0tunerpro_exporter.py" %*
)
exit /b %errorlevel%
