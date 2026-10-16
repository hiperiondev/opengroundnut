#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""OpenGroundnut entry point.

The application modules live in the src/ folder. The application core
(bootstrap, events, network, audio, aprs, database, callsign, settings and
core) is loaded first and works on its own: it never uses a window, a widget
or any graphics library. It reports what happens through events.py.

The graphical interface (gui.py) is loaded last. It subscribes to the core
events, shows them and passes the user's actions back to the core functions.

Every module is executed inside this one shared namespace, in the order
listed below, so the modules can use each other's functions and state
directly. The "Architecture" section of README.md describes the layout.
"""

import os
import sys
import tempfile
import traceback

# Folder of the program itself. A frozen build (PyInstaller) is the folder of
# the executable; a normal run is the folder of this script, whatever the
# current directory is.
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _folder_is_writable(folder):
    """True when files can be created in a folder (it is created when missing)."""
    try:
        os.makedirs(folder, exist_ok=True)
        handle, probe = tempfile.mkstemp(prefix=".write-test-", dir=folder)
        os.close(handle)
        os.remove(probe)
        return True
    except OSError:
        return False


def _personal_data_folder():
    """The usual folder for application data of the current user on this system."""
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA") or home, "OpenGroundnut")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", "OpenGroundnut")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share"), "opengroundnut")


# Folder that holds the user's files (the database folder with the settings,
# logbook and RadioID list, the images folder and the log). It is the
# program folder, so everything travels with the program; when the program
# was installed where the user cannot write (for example under
# "C:\Program Files"), the user's own data folder is used instead.
DATA_DIR = APP_DIR if _folder_is_writable(APP_DIR) else _personal_data_folder()

# Folder that holds the read-only resources shipped with the program (src,
# data, flags, lang and fonts). PyInstaller unpacks them into sys._MEIPASS;
# otherwise they live in APP_DIR.
RES_DIR = getattr(sys, "_MEIPASS", APP_DIR)

# Folder that holds the application modules (bootstrap.py, core.py, gui.py, ...).
SRC_DIR = os.path.join(RES_DIR, "src")

# RES_DIR lets the language files be imported as the lang package, and
# SRC_DIR lets the modules import their helper module utils by name.
for _import_dir in (SRC_DIR, RES_DIR):
    if _import_dir not in sys.path:
        sys.path.insert(0, _import_dir)


def _load_module(file_name):
    """Run one of the application modules from src/ inside this shared namespace."""
    module_path = os.path.join(SRC_DIR, file_name)
    with open(module_path, encoding="utf-8") as source:
        exec(compile(source.read(), module_path, "exec"), globals())


def _report_startup_failure():
    """Tell the user why the program could not start, even without a console."""
    details = traceback.format_exc()
    logger = globals().get("log")
    if logger is not None:
        logger.critical("The program could not start:\n%s", details)
    if sys.stderr is not None:
        print(details, file=sys.stderr)
    try:
        import tkinter
        from tkinter import messagebox

        window = tkinter.Tk()
        window.withdraw()
        messagebox.showerror(
            "OpenGroundnut",
            "The program could not start.\n\n{}\n\nMore details are in {}".format(
                details.strip().splitlines()[-1], os.path.join(DATA_DIR, "peanut.log")
            ),
            parent=window,
        )
        window.destroy()
    except Exception:
        pass


# --debug enables the detailed protocol and scanner logs. It is removed from
# sys.argv so no other argument handling ever sees it.
debug_mode = "--debug" in sys.argv
if debug_mode:
    sys.argv = [arg for arg in sys.argv if arg != "--debug"]

try:
    _load_module("bootstrap.py")
    setup_logging(debug_mode)
    if debug_mode:
        log.debug("Debug mode enabled: scanner and Peanut UDP protocol logs are active.")
    if DATA_DIR != APP_DIR:
        log.info("The program folder cannot be written to; user files are kept in %s", DATA_DIR)

    # Application core: no graphical code in any of these modules.
    for _core_module in ("events.py", "network.py", "audio.py", "aprs.py", "database.py",
                         "callsign.py", "settings.py", "core.py"):
        _load_module(_core_module)

    # Mute the noisy messages of ALSA and JACK before anything touches the
    # sound system. This has to happen early, because the audio device list
    # can be built while the configuration is read, long before PyAudio is
    # started.
    silence_audio_library_messages()

    initialize_application()

    load_language(language_setting)

    # Graphical interface: the window is built and shown first, then the core
    # starts its network and audio work in the background (start_application),
    # so a slow or missing network never delays the window.
    _load_module("gui.py")
    start_gui()
except SystemExit:
    raise
except Exception:
    _report_startup_failure()
    sys.exit(1)

run_gui(on_ready=start_application)
