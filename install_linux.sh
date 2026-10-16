#!/usr/bin/env bash
# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

# Prepare OpenGroundnut on Linux: a private Python environment (.venv) in the
# program folder with every package of requirements.txt. Run it once, and
# again after updating the program; then start it with ./run_linux.sh
#
# PyAudio and Tk need a few system packages first. On Debian, Ubuntu and
# Raspberry Pi OS:
#     sudo apt install python3-venv python3-tk python3-dev portaudio19-dev
# On Fedora:
#     sudo dnf install python3-tkinter python3-devel portaudio-devel
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is not installed." >&2
    exit 1
fi

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo "OpenGroundnut needs Python 3.9 or newer (found $(python3 --version 2>&1))." >&2
    exit 1
fi

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "Python's Tk support is missing (install python3-tk or python3-tkinter)." >&2
    exit 1
fi

if [ ! -x .venv/bin/python ]; then
    echo "Creating the Python environment in .venv ..."
    python3 -m venv .venv
fi

echo "Installing the required packages ..."
.venv/bin/python -m pip install --upgrade pip
if ! .venv/bin/python -m pip install -r requirements.txt; then
    echo >&2
    echo "The packages could not be installed. When PyAudio fails to build," >&2
    echo "install the PortAudio development files (portaudio19-dev or" >&2
    echo "portaudio-devel) and run this script again." >&2
    exit 1
fi

chmod +x run_linux.sh
echo
echo "Done. Start OpenGroundnut with:  ./run_linux.sh"
