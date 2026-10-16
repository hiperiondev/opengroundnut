@echo off
rem SPDX-License-Identifier: WTFPL
rem
rem This program is free software. It comes without any warranty, to the
rem extent permitted by applicable law. You can redistribute it and/or modify
rem it under the terms of the Do What The Fuck You Want To Public License,
rem Version 2, as published by Sam Hocevar. See LICENSE.md for more details.
rem
rem Start OpenGroundnut with the environment created by install_windows.bat.
rem Extra arguments are passed on, for example:  run_windows.bat --debug
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
    echo Run install_windows.bat first.
    exit /b 1
)
if "%~1"=="" (
    start "" .venv\Scripts\pythonw.exe opengroundnut.py
) else (
    .venv\Scripts\python.exe opengroundnut.py %*
)
