#!/usr/bin/env bash
# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

# Start OpenGroundnut with the environment created by install_linux.sh.
# Extra arguments are passed on, for example:  ./run_linux.sh --debug
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    echo "Run ./install_linux.sh first." >&2
    exit 1
fi
exec .venv/bin/python opengroundnut.py "$@"
