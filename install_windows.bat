@echo off
rem SPDX-License-Identifier: WTFPL
rem
rem This program is free software. It comes without any warranty, to the
rem extent permitted by applicable law. You can redistribute it and/or modify
rem it under the terms of the Do What The Fuck You Want To Public License,
rem Version 2, as published by Sam Hocevar. See LICENSE.md for more details.
rem
rem Prepare OpenGroundnut on Windows: a private Python environment (.venv) in
rem the program folder with every package of requirements.txt. Run it once,
rem and again after updating the program; then start it with run_windows.bat
rem
rem Python 3 must be installed from python.org with the "py" launcher
rem (selected by default in the installer). PyAudio, the sound library,
rem publishes ready-made packages for Python 3.9 to 3.13 only, so the newest
rem of those versions found on this computer is used.
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python 3 is not installed. Download it from https://www.python.org/downloads/
    pause
    exit /b 1
)

if exist .venv\Scripts\python.exe goto install

set "PYVER="
for %%V in (3.13 3.12 3.11 3.10 3.9) do (
    if not defined PYVER (
        py -%%V -c "import sys" >nul 2>nul && set "PYVER=%%V"
    )
)
if not defined PYVER (
    echo No Python version between 3.9 and 3.13 was found.
    echo Install Python 3.13 from https://www.python.org/downloads/ and run this script again.
    pause
    exit /b 1
)

echo Creating the Python environment in .venv with Python %PYVER% ...
py -%PYVER% -m venv .venv
if errorlevel 1 (
    echo The Python environment could not be created.
    pause
    exit /b 1
)

:install
echo Installing the required packages ...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo The packages could not be installed. If PyAudio failed, the Python
    echo version of .venv may be newer than the PyAudio packages available:
    echo delete the .venv folder, install Python 3.13 and run this script again.
    pause
    exit /b 1
)

echo.
echo Done. Start OpenGroundnut with run_windows.bat
pause
