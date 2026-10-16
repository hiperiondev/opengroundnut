# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Test helpers: load the application core the same way opengroundnut.py does.

The modules of src/ are executed into one shared namespace. Each test gets a
fresh namespace whose user data folder is a temporary folder, so the tests
never touch real settings or logbooks. The graphical interface is not loaded
and nothing is sent over the network.
"""

import os
import sys

import pytest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_DIR, "src")

CORE_MODULES = (
    "bootstrap.py", "events.py", "network.py", "audio.py", "aprs.py", "database.py",
    "callsign.py", "settings.py", "core.py",
)

for _import_dir in (SRC_DIR, PROJECT_DIR):
    if _import_dir not in sys.path:
        sys.path.insert(0, _import_dir)


def load_core(data_dir, initialize=True):
    """A namespace with the application core loaded; user files go to data_dir."""
    namespace = {
        "__name__": "opengroundnut_test",
        "APP_DIR": str(data_dir),
        "DATA_DIR": str(data_dir),
        "RES_DIR": PROJECT_DIR,
        "SRC_DIR": SRC_DIR,
        "debug_mode": False,
    }
    for module in CORE_MODULES:
        path = os.path.join(SRC_DIR, module)
        with open(path, encoding="utf-8") as source:
            exec(compile(source.read(), path, "exec"), namespace)
    namespace["load_language"]("en")
    if initialize:
        namespace["initialize_application"]()
    return namespace


@pytest.fixture
def core(tmp_path):
    """The application core with fresh settings and an empty logbook."""
    return load_core(tmp_path)
