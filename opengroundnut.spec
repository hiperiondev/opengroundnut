# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

# PyInstaller recipe for a single-folder build of OpenGroundnut.
#
#   python -m pip install pyinstaller
#   pyinstaller opengroundnut.spec
#
# On macOS the result is also an application bundle, OpenGroundnut.app.
#
# The program runs its modules from source files, so the src folder is bundled
# as data next to the other resources (data, flags, lang, fonts). The user
# files (the database folder with the TinyDB files, images, peanut.log) are
# created next to the executable on the first run, or in the user's own data
# folder when the program folder cannot be written to.

import ast
import importlib.util
import os
import sys

# Folder of the application modules, relative to the project root.
SRC = "src"

MODULES = [
    "bootstrap.py", "events.py", "network.py", "audio.py", "aprs.py", "database.py",
    "callsign.py", "settings.py", "core.py", "gui.py", "utils.py",
]

# The modules import utils by name, so src has to be importable while the
# build looks for their dependencies, just as it is when the program runs.
if SRC not in sys.path:
    sys.path.insert(0, SRC)

datas = [(os.path.join(SRC, name), SRC) for name in MODULES] + [
    ("data", "data"),
    ("flags", "flags"),
    ("lang", "lang"),
    ("fonts", "fonts"),
]


def _imports_of(file_name):
    """Every module a source file imports (top level and inside functions)."""
    with open(file_name, encoding="utf-8") as source:
        tree = ast.parse(source.read())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
            # "from PIL import ImageDraw" may name a submodule.
            found.update("{}.{}".format(node.module, alias.name) for alias in node.names if alias.name != "*")
    return {name for name in found if importlib.util.find_spec(name.split(".")[0]) is not None and _exists(name)}


def _exists(module_name):
    """True when a module (or a name inside a package) can be imported here."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


# The modules are executed from source at run time, so PyInstaller cannot
# see what they import: their imports are listed here, read from the files.
hiddenimports = sorted(
    set().union(*(_imports_of(os.path.join(SRC, name)) for name in MODULES))
    | {"lang"} | {"lang." + code for code in ("en", "de", "es", "fr", "it", "pt")} | {"PIL.ImageTk", "PIL._tkinter_finder"}
)

a = Analysis(
    ["opengroundnut.py"],
    pathex=[".", SRC],
    datas=datas,
    hiddenimports=hiddenimports,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="opengroundnut",
    console=False,
    icon="data/app.ico",
)
coll = COLLECT(exe, a.binaries, a.datas, name="opengroundnut")

# On macOS the folder is also wrapped as an application bundle
# (dist/OpenGroundnut.app). PyInstaller converts the icon with Pillow.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="OpenGroundnut.app",
        icon="data/app.ico",
        bundle_identifier="net.opengroundnut.client",
        info_plist={
            "NSMicrophoneUsageDescription": "OpenGroundnut sends your voice to the Peanut network.",
            "NSHighResolutionCapable": True,
        },
    )
