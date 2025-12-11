@echo off
:: ==============================================================================
:: KingAI TunerPro XDF + BIN Universal Exporter - Windows Installer
:: ==============================================================================
:: Author: KingAI (Jason King)
:: GitHub: KingAiCodeForge
:: Supports: Windows 10 and Windows 11
:: ==============================================================================

echo.
echo ==============================================================================
echo   KingAI TunerPro XDF + BIN Universal Exporter - Installer
echo ==============================================================================
echo   Author: KingAI (Jason King)
echo   GitHub: KingAiCodeForge
echo ==============================================================================
echo.

:: Check for Administrator privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Not running as Administrator.
    echo           Some features like PATH modification may require elevation.
    echo.
    echo           To run as Administrator:
    echo           Right-click this file and select "Run as administrator"
    echo.
    pause
)

:: Get the directory where this script is located
set "INSTALL_DIR=%~dp0"
set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

echo [INFO] Installation directory: %INSTALL_DIR%
echo.

:: Check if Python is installed
echo [STEP 1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo         Please install Python from: https://www.python.org/downloads/
    echo         Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo         Found Python %PYTHON_VERSION%
echo.

:: Check pip installation
echo [STEP 2/4] Checking pip installation...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip is not installed!
    echo         Installing pip...
    python -m ensurepip --default-pip
)
echo         pip is available
echo.

:: Install requirements
echo [STEP 3/4] Installing Python dependencies...
echo.
python -m pip install -r "%INSTALL_DIR%\requirements.txt" --upgrade
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Some dependencies may have failed to install.
    echo           The CLI tool will still work (GUI requires PySide6).
    echo.
) else (
    echo.
    echo         Dependencies installed successfully!
)
echo.

:: Add to PATH (User PATH - doesn't require admin)
echo [STEP 4/4] Adding to User PATH...
echo.

:: Check if already in PATH
echo %PATH% | find /i "%INSTALL_DIR%" >nul
if %errorlevel% equ 0 (
    echo         Already in PATH - skipping.
) else (
    :: Add to User PATH via registry
    for /f "tokens=2*" %%a in ('reg query HKCU\Environment /v Path 2^>nul') do set "USER_PATH=%%b"
    
    if defined USER_PATH (
        setx PATH "%USER_PATH%;%INSTALL_DIR%" >nul 2>&1
    ) else (
        setx PATH "%INSTALL_DIR%" >nul 2>&1
    )
    
    if %errorlevel% equ 0 (
        echo         Added to User PATH successfully!
        echo         NOTE: You need to restart your terminal for PATH changes to take effect.
    ) else (
        echo [WARNING] Could not modify PATH automatically.
        echo           To add manually:
        echo           1. Open System Properties ^> Environment Variables
        echo           2. Under "User variables", edit "Path"
        echo           3. Add: %INSTALL_DIR%
    )
)
echo.

:: Create convenient batch wrapper for CLI
echo Creating command shortcuts...
(
echo @echo off
echo python "%INSTALL_DIR%\tunerpro_exporter.py" %%*
) > "%INSTALL_DIR%\tunerpro-export.bat"

(
echo @echo off
echo python "%INSTALL_DIR%\exporter_gui.py"
) > "%INSTALL_DIR%\tunerpro-export-gui.bat"

echo         Created: tunerpro-export.bat (CLI tool)
echo         Created: tunerpro-export-gui.bat (GUI tool)
echo.

:: Summary
echo ==============================================================================
echo   INSTALLATION COMPLETE!
echo ==============================================================================
echo.
echo   CLI Usage (from any directory):
echo     tunerpro-export ^<xdf_file^> ^<bin_file^> ^<output_file^> [format]
echo.
echo     Formats: txt, json, md, csv, text, all
echo.
echo   Examples:
echo     tunerpro-export "tune.xdf" "ecu.bin" "export.txt" txt
echo     tunerpro-export "tune.xdf" "ecu.bin" "export.json" json
echo     tunerpro-export "tune.xdf" "ecu.bin" "export" all
echo.
echo   GUI Usage:
echo     tunerpro-export-gui
echo.
echo   Or run directly:
echo     python "%INSTALL_DIR%\tunerpro_exporter.py" ^<args^>
echo     python "%INSTALL_DIR%\exporter_gui.py"
echo.
echo ==============================================================================
echo.
pause
