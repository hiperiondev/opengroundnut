#!/usr/bin/env python3
# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Lint the modules of src/ the way they really run: joined in load order.

The modules are executed in one shared namespace by opengroundnut.py, so a
name defined in one module is used by the others without an import. Linting
each file alone would report those names as undefined; this script writes
the modules and the interface into one temporary file and runs ruff on it.

    python tools/lint_shared_namespace.py
"""

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Same order as opengroundnut.py.
LOAD_ORDER = [
    "src/bootstrap.py", "src/events.py", "src/network.py", "src/audio.py", "src/aprs.py",
    "src/database.py", "src/callsign.py", "src/settings.py", "src/core.py",
    "src/gui.py",
]

# Names that opengroundnut.py defines before the first module runs.
PRELUDE = 'APP_DIR = DATA_DIR = RES_DIR = SRC_DIR = ""\ndebug_mode = False\n'


def main():
    parts = [PRELUDE]
    for relative in LOAD_ORDER:
        with open(os.path.join(ROOT, relative), encoding="utf-8") as source:
            parts.append("# ---- {}\n{}\n".format(relative, source.read()))
    handle, joined = tempfile.mkstemp(prefix="opengroundnut-joined-", suffix=".py")
    with os.fdopen(handle, "w", encoding="utf-8") as output:
        output.write("".join(parts))
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--config", os.path.join(ROOT, "pyproject.toml"), joined]
        )
    finally:
        os.remove(joined)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
