@echo off
REM ================================================================================
REM  KingAI TunerPro Exporter - CLI Launcher
REM  Author: KingAI / Jason King
REM  Repository: https://github.com/KingAiCodeForge/kingai-tunerpro-exporter
REM ================================================================================

title KingAI TunerPro Exporter - CLI

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please run install.bat first or install Python 3.8+
    pause
    exit /b 1
)

echo ================================================================================
echo  KingAI TunerPro Exporter - Command Line Interface
echo  Usage: tunerpro_exporter.py [XDF_PATH] [BIN_PATH] [OUTPUT_PATH] [FORMAT]
echo ================================================================================
echo.

REM If arguments provided, run with them
if not "%~1"=="" (
    python "%~dp0tunerpro_exporter.py" %*
) else (
    echo No arguments provided. Running in interactive mode...
    echo.
    python "%~dp0tunerpro_exporter.py" --help
    echo.
    echo Example usage:
    echo   tunerpro_exporter.py "path/to/file.xdf" "path/to/file.bin" "output/folder/name" md
    echo.
    echo Supported formats: md, txt, html, json, csv, xml, all
)

pause
