# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""OpenGroundnut (opengroundnut) - shared imports and runtime state of the application core.

Nothing in here knows about the graphical interface: this file only holds
the libraries, the small helpers and the state shared by the network, audio,
database, callsign, settings and core modules.

APP_DIR, DATA_DIR, RES_DIR, SRC_DIR and debug_mode are defined by
opengroundnut.py before this file runs.
"""

import os
import sys

# Standard library modules. These are always available.
import csv
import importlib
import json
import logging
import logging.handlers
import math
import platform
import queue
import random
import re
import shutil
import socket
import struct
import tempfile
import threading
import unicodedata
import urllib.parse
import array
import traceback
import wave
import webbrowser
import zlib
from ctypes import CFUNCTYPE, c_char_p, c_int, cdll
from datetime import datetime, timezone
from os.path import exists
from time import localtime, monotonic, sleep, strftime, time

# PortAudio asks the JACK sound server for its devices every time it starts.
# Without these settings JACK tries to start a server of its own and prints
# several lines of complaints when there is none. They only change JACK's
# behavior and are set before PyAudio is loaded.
os.environ.setdefault("JACK_NO_START_SERVER", "1")
os.environ.setdefault("JACK_NO_AUDIO_RESERVATION", "1")

# Name of the pip package that provides each module whose package has a
# different name.
_PIP_PACKAGE_OF_MODULE = {
    "bs4": "beautifulsoup4",
    "PIL": "Pillow",
    "serial": "pyserial",
    "pyaudio": "PyAudio",
}

# Third-party packages. A missing one is reported with the name pip knows it
# by and a hint on how to install the requirements, instead of a bare traceback.
try:
    import aprslib
    import pyaudio
    import requests
    import serial
    import serial.tools.list_ports
    import xmltodict
    from bs4 import BeautifulSoup

    # TinyDB keeps every piece of persistent data: settings, logbook,
    # bookmarks and the RadioID user list. The names get a "Tiny" prefix so
    # they never clash with other names of the shared namespace.
    from tinydb import Query as TinyQuery
    from tinydb import TinyDB
    from tinydb.storages import Storage as TinyStorage
    from tinydb.table import Document as TinyDocument
except ImportError as missing_package:
    _missing_module = str(getattr(missing_package, "name", None) or missing_package).split(".")[0]
    _missing_text = (
        "Fatal error: the Python package '{}' is not installed.\n"
        "Install the requirements with:  python -m pip install -r requirements.txt".format(
            _PIP_PACKAGE_OF_MODULE.get(_missing_module, _missing_module)
        )
    )
    if sys.stderr is not None:
        print(_missing_text, file=sys.stderr)
    # Started without a console (pythonw.exe or the stand-alone program),
    # nobody would see the text above, so it is also shown in a window.
    try:
        import tkinter
        from tkinter import messagebox

        _message_root = tkinter.Tk()
        _message_root.withdraw()
        messagebox.showerror("OpenGroundnut", _missing_text, parent=_message_root)
        _message_root.destroy()
    except Exception:
        pass
    sys.exit(1)

# utils is a regular module that lives next to this file in src/; the entry
# point puts src/ on sys.path so it can be imported by name.
import utils


# ---------------------------------------------------------------------------
# Program identity
# ---------------------------------------------------------------------------

# Name and version shown to the user and sent as the HTTP User-Agent.
APP_NAME = "OpenGroundnut"
APP_DISPLAY_VERSION = "1.0"

# Protocol version sent to the Peanut server in the INFO message. The server
# checks it, so it is kept separate from the display version.
PROTOCOL_VERSION = "0.11"

# Device type sent in the INFO message. The Peanut clients known to the
# network report WINDOWS or ANDROID, and other station lists may only show
# those two values, so this desktop client reports itself as WINDOWS on
# every operating system to be listed like any other desktop client.
DEVICE_NAME = "WINDOWS"


# ---------------------------------------------------------------------------
# Interface languages
# ---------------------------------------------------------------------------

# Language codes of the translations in the lang folder (lang/<code>.py).
# English is the reference translation and the default.
LANGUAGES = ("en", "de", "es", "fr", "it", "pt")
DEFAULT_LANGUAGE = "en"

# Texts of the language in use, and the English ones that fill any gap.
_texts = {}
_reference_texts = {}


def load_language(code):
    """Load the interface texts of a language code and return the code in use.

    An unknown code loads English. Every text is looked up with tr().
    """
    global _texts, _reference_texts
    if code not in LANGUAGES:
        code = DEFAULT_LANGUAGE
    _reference_texts = dict(importlib.import_module("lang." + DEFAULT_LANGUAGE).TEXTS)
    _texts = dict(importlib.import_module("lang." + code).TEXTS)
    return code


def language_names():
    """{code: name of the language written in that language} for every translation."""
    return {code: importlib.import_module("lang." + code).LANGUAGE_NAME for code in LANGUAGES}


def tr(key):
    """Interface text of a key in the language in use.

    A key the translation lacks is shown in English, and a key unknown to
    English too is shown as it is, so a missing text is visible but harmless.
    """
    return _texts.get(key) or _reference_texts.get(key) or key


# ---------------------------------------------------------------------------
# Network endpoints and limits
# ---------------------------------------------------------------------------

# UDP port of every Peanut server.
PEANUT_UDP_PORT = 6667

# List of Peanut master servers.
MASTERS_URL_PATH = "www.pa7lim.nl/masters.json"

# Default master server, used when the configuration names none.
DEFAULT_MASTER = "peanut.pa7lim.nl"

# Timeouts for every HTTP request, as (connect seconds, read seconds).
HTTP_TIMEOUT = (5, 15)

# Rooms used for server development. They are never shown in the Monitor,
# never stored as bookmarks and only listed for the callsigns below.
DEVELOPER_ROOMS = {"DEVTEST"}
DEVELOPER_CALLS = {"PA7LIM"}


# ---------------------------------------------------------------------------
# User interface limits shared by the core and the interface
# ---------------------------------------------------------------------------

# Allowed range of the "scale" setting (1 = normal size).
SCALE_MIN = 1
SCALE_MAX = 3

# Allowed range of the transmit time-out, in seconds.
TOT_MIN = 30
TOT_MAX = 300

# Longest recording kept, in seconds (frames beyond it are dropped).
RECORDING_MAX_SECONDS = 4 * 3600


# ---------------------------------------------------------------------------
# File locations
# ---------------------------------------------------------------------------

def app_path(*parts):
    """Path of a user file or folder, inside the user data folder (DATA_DIR).

    DATA_DIR is the program folder whenever it can be written to, so the
    settings travel with the program; otherwise it is a folder of the user's
    own (see opengroundnut.py).
    """
    return os.path.join(DATA_DIR, *parts)


def resource_path(relative_path):
    """Path of a read-only resource shipped with the program (RES_DIR)."""
    return os.path.join(RES_DIR, relative_path)


def ensure_dir(folder):
    """Create a folder (and its parents) when it does not exist yet; return it."""
    os.makedirs(folder, exist_ok=True)
    return folder


def database_dir():
    """Folder holding every TinyDB file (settings, logbook, RadioID list)."""
    return app_path("database")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger("peanut")


def setup_logging(debug=False):
    """Send log messages to the console and to peanut.log in the program folder.

    With debug=True every DEBUG message is shown too (protocol packets,
    scanner decisions). The log file rotates at 1 MB and keeps three copies.
    """
    level = logging.DEBUG if debug else logging.INFO
    log.setLevel(level)
    log.propagate = False
    for handler in list(log.handlers):
        log.removeHandler(handler)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s")
    # Without a console (pythonw.exe or the stand-alone program) there is no
    # standard error stream, so only the log file is used.
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        log.addHandler(console)
    try:
        log_file = logging.handlers.RotatingFileHandler(
            app_path("peanut.log"), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        log_file.setFormatter(formatter)
        log.addHandler(log_file)
    except OSError as exc:
        log.warning("The log file cannot be written: %s", exc)
    install_exception_logging()


def install_exception_logging():
    """Write every error nobody caught to the log, from any thread.

    Without this, an error in a thread or at start-up only reaches the
    console, which does not exist when the program runs without one.
    """

    def log_uncaught(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        log.critical(
            "Unexpected error:\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        )

    def log_uncaught_in_thread(args):
        if args.exc_type is SystemExit:
            return
        log.critical(
            "Unexpected error in thread %s:\n%s",
            getattr(args.thread, "name", "?"),
            "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
        )

    sys.excepthook = log_uncaught
    threading.excepthook = log_uncaught_in_thread


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

def start_worker(target, *args, name=None):
    """Run target(*args) in a named daemon thread and return the thread.

    An exception raised by the worker is written to the log instead of
    vanishing, so a failing background task is always visible.
    """
    worker_name = name or getattr(target, "__name__", "worker")

    def runner():
        try:
            target(*args)
        except Exception:
            log.exception("Background task %s failed", worker_name)

    thread = threading.Thread(target=runner, name=worker_name, daemon=True)
    thread.start()
    return thread


def monotonic_ms():
    """Milliseconds from a clock that never jumps (unlike the wall clock on DST or NTP changes)."""
    return monotonic() * 1000.0


# Protects the transmit counters, the alarm tables and the connection flags,
# which are changed from more than one thread.
state_lock = threading.RLock()


# ---------------------------------------------------------------------------
# Text helpers for the fixed-width protocol fields
# ---------------------------------------------------------------------------

def ascii_text(text):
    """Plain ASCII version of a text: accents are removed, other symbols dropped.

    "Café crème" becomes "Cafe creme". The Peanut protocol fields are ASCII.
    """
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return normalized.encode("ascii", "ignore").decode("ascii")


def ascii_field(text, width):
    """ASCII text cut to `width` characters and right-aligned in a field of that width."""
    return ascii_text(text)[:width].rjust(width)


# Characters that can appear in a callsign (portable calls use "/").
_CALLSIGN_ALLOWED = re.compile(r"[^A-Z0-9/]")


def clean_callsign(text):
    """Upper-case callsign with every character other than A-Z, 0-9 and "/" removed."""
    return _CALLSIGN_ALLOWED.sub("", ascii_text(text).upper())


def pcm_rms(pcm):
    """Root-mean-square level of 16-bit signed little-endian mono audio.

    The result goes from 0 (silence) to 32767 (full scale), the same scale
    the VOX threshold uses.
    """
    samples = array.array("h")
    usable = len(pcm) - (len(pcm) % 2)
    samples.frombytes(bytes(pcm[:usable]))
    if not samples:
        return 0
    if sys.byteorder == "big":
        samples.byteswap()
    return int(math.sqrt(sum(sample * sample for sample in samples) / len(samples)))


def format_duration(seconds):
    """A duration as MM:SS, or H:MM:SS from one hour on."""
    seconds = max(0, int(round(seconds)))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return "{}:{:02d}:{:02d}".format(hours, minutes, secs)
    return "{:02d}:{:02d}".format(minutes, secs)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

# One HTTP session shared by every request, so connections are reused.
http_session = requests.Session()


def http_user_agent():
    """Identifiable User-Agent, as QRZ.com and other services require."""
    station = str(globals().get("my_call") or "").strip()
    agent = "{}/{}".format(APP_NAME, APP_DISPLAY_VERSION)
    return "{} ({})".format(agent, station) if station and station != "NOCALL" else agent


def http_headers(extra=None):
    """Headers sent with every HTTP request."""
    headers = {"User-Agent": http_user_agent()}
    if extra:
        headers.update(extra)
    return headers


# Scheme ("https" or "http") that worked last time for each Peanut host.
_host_schemes = {}

# Hosts that may always be reached over plain HTTP when HTTPS fails for any
# reason (no HTTPS service, unusable certificate). Every other host only
# falls back to HTTP when its HTTPS port actively refuses the connection.
# A certificate error, a time-out, a proxy refusal or a name that cannot be
# resolved never leads to plain HTTP: blocking HTTPS is exactly what an
# attacker on the network would do in order to serve fake server lists.
PLAIN_HTTP_HOSTS = set()


def _https_port_refused(exc):
    """True when a request failed because the host refused the HTTPS connection.

    requests wraps the operating system error several layers deep, so the
    chain of causes is followed until a ConnectionRefusedError is found.
    """
    if isinstance(exc, requests.exceptions.ProxyError):
        return False
    pending = [exc]
    seen = set()
    while pending:
        error = pending.pop()
        if not isinstance(error, BaseException) or id(error) in seen:
            continue
        seen.add(id(error))
        if isinstance(error, ConnectionRefusedError):
            return True
        pending.extend((error.__cause__, error.__context__, getattr(error, "reason", None)))
        pending.extend(getattr(error, "args", ()))
    return False


def http_get_with_fallback(host_and_path, timeout=HTTP_TIMEOUT):
    """GET host/path over HTTPS, falling back to plain HTTP only for a host without HTTPS.

    A host is considered to have no HTTPS when its HTTPS port refuses the
    connection, or when it is listed in PLAIN_HTTP_HOSTS. The scheme that
    worked is remembered per host, so the fallback costs time only once.
    Raises requests.exceptions.RequestException when no allowed scheme answers.
    """
    host = host_and_path.split("/", 1)[0]
    schemes = [_host_schemes[host]] if host in _host_schemes else ["https", "http"]
    last_error = None
    for scheme in schemes:
        try:
            response = http_session.get(
                "{}://{}".format(scheme, host_and_path), headers=http_headers(), timeout=timeout
            )
        except requests.exceptions.SSLError as exc:
            # SSLError is a kind of ConnectionError, so it is checked first.
            if host not in PLAIN_HTTP_HOSTS:
                log.warning("The HTTPS certificate of %s is not valid; plain HTTP is not used: %s", host, exc)
                raise
            last_error = exc
            continue
        except requests.exceptions.ConnectionError as exc:
            last_error = exc
            if scheme == "https" and host not in PLAIN_HTTP_HOSTS and not _https_port_refused(exc):
                # The host may well have HTTPS and simply be unreachable
                # right now; plain HTTP is not tried.
                break
            continue
        if scheme == "http" and host not in _host_schemes:
            log.info("%s has no HTTPS service; plain HTTP is used.", host)
        _host_schemes[host] = scheme
        return response
    if host in _host_schemes:
        # The remembered scheme stopped working: try both again next time.
        del _host_schemes[host]
    raise last_error


# ---------------------------------------------------------------------------
# Runtime state shared by the core modules
# ---------------------------------------------------------------------------

master_host = ""

callsign = ""

my_call = ""

tx_message = ""

# Value of the RSSI byte of every voice frame this client sends.
RSSI_BYTE_VALUE = 1

tx_active = False

heard_call = ""

watchdog_active = False

connection_closed = False

lookups_stopped = False

active_monitor_stopped = False

# True from the moment the user connects until the user (or the program)
# disconnects. The server may not have accepted the login yet: see link_up.
session_active = False

# True once the server accepted the login (ACK or first PING received).
link_up = False

# True while the user wants to stay connected; automatic reconnections only
# happen while it is set.
user_wants_connection = False

speaker_muted = False

ptt_pressed = False

recording_active = False

scanner_running = False

ptt_allowed = False

qrz_cache = {}

radioid_cache = {}

# Callsigns waiting for a picture and identity lookup.
lookup_queue = queue.Queue()

room_list = []

server_list = []

active_transmissions = []

room_groups = []

watched_calls = {}

alarm_history = {}

active_room = None

# Room currently chosen by the user. The interface keeps it up to date; the
# core uses it to connect and to auto-start.
selected_room = ""

start_time = time()

start_time_ptt = time()

auto_room = ""

running_under_wine = ""

last_ping_ms = 0

last_rx_ms = 0

last_tx_ms = 0

link_status = 0

previous_link_status = 0

link_state = 0

tx_sequence = 0

session_id = 1

serial_port_list = []

serial_rx = None

serial_tx = None

recording_enabled = False

scan_room_list = []

scan_paused = False

scan_index = 0

last_voice_ms = 0

last_aprs_beacon = 0

ui_scale_setting = 1

# Problems found while reading the settings and the database files, as
# (language key, format arguments) pairs. They are shown once the interface is up.
config_warnings = []

# Set once by shutdown(); every background loop of the core ends when it is True.
app_closing = False


# ---------------------------------------------------------------------------
# ALSA error handler type
# ---------------------------------------------------------------------------

ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)


def py_error_handler(filename, line, function, err, fmt):
    """Receive ALSA's diagnostic messages and drop them (they are only noise for users)."""
    pass


c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
