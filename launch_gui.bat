@echo off
REM ================================================================================
REM  KingAI TunerPro Exporter - GUI Launcher
REM  Author: KingAI / Jason King
REM  Repository: https://github.com/KingAiCodeForge/kingai-tunerpro-exporter
REM ================================================================================

title KingAI TunerPro Exporter - GUI

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please run install.bat first or install Python 3.8+
    pause
    exit /b 1
)

REM Check for PySide6
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PySide6 is not installed!
    echo Installing now...
    pip install PySide6
)

REM Launch the GUI
echo Starting KingAI TunerPro Exporter GUI...
python "%~dp0exporter_gui.py"
