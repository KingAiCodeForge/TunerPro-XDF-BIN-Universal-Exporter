@echo off
setlocal
if /i "%~1"=="--help" (
  echo Usage: install.bat [--gui]
  echo Creates a new local .venv; does not change global packages or PATH.
  exit /b 0
)
if not "%~1"=="" if /i not "%~1"=="--gui" (
  echo [ERROR] Usage: install.bat [--gui]
  exit /b 2
)
REM Install only into a project-local environment. No Administrator or PATH edits.
set "PYTHON_CMD=python"
if defined KINGAI_PYTHON set "PYTHON_CMD=%KINGAI_PYTHON%"
"%PYTHON_CMD%" -c "import sys; raise SystemExit(sys.version_info < (3,10))" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.10+ is required. Set KINGAI_PYTHON to its executable path.
  exit /b 1
)
if exist "%~dp0.venv" (
  echo [ERROR] .venv already exists. Use it or choose a clean project copy.
  exit /b 1
)
"%PYTHON_CMD%" -m venv "%~dp0.venv"
if errorlevel 1 exit /b 1
"%~dp0.venv\Scripts\python.exe" -m pip install "%~dp0."
if errorlevel 1 exit /b 1
if /i "%~1"=="--gui" (
  "%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 exit /b 1
)
echo Installed into the local .venv. Use launch_cli.bat or launch_gui.bat.
exit /b 0
