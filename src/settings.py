# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Settings (stored with TinyDB), room scanner and alarm list.

The settings live in database/settings.json, a TinyDB file holding a single
document with one entry per section:

    {"general": {"callsign": "NOCALL", ...}, "rx_control": {...}, "scan": {...}, ...}

Values keep their natural type: texts, whole numbers, and lists for the
alarm callsigns and the scan rooms. The whole document is saved in one
write, so the file is never left with half of a change.
"""

# Receive control modes: how the client knows the radio is receiving a
# station that must be sent to the network.
RX_MODES = ["Manual", "VOX", "Serial CD", "Serial CTS", "Serial DSR"]

# Transmit control modes: how the client keys the radio while the room is heard.
TX_MODES = ["Manual", "Serial RTS", "Serial DTR"]

# Transmit time-outs offered in the settings, in seconds (TOT_MIN to TOT_MAX).
TOT_VALUES = ["30", "60", "120", "180", "240", "300"]

# Highest DMR id that fits the 3 bytes of a voice frame.
DMRID_MAX = 0xFFFFFF

# TinyDB table and document that hold the settings.
SETTINGS_TABLE = "settings"
SETTINGS_DOC_ID = 1

# Version of the layout of settings.json, stored in its "meta" table.
SETTINGS_SCHEMA_VERSION = 1

# Settings of a new installation. Every section and key the program uses is
# listed here, so a fresh settings.json shows all of them. Settings saved by
# the user always win over these values.
DEFAULT_SETTINGS = {
    "general": {
        # Callsign (letters, numbers and "/", up to 8 characters) and DMR ID (0 = none).
        "callsign": "NOCALL",
        "dmr_id": 0,
        # Short text shown next to the callsign while transmitting (20 characters).
        "message": "",
        # Peanut access code of the callsign and the Peanut master server.
        "access_code": "",
        "master": DEFAULT_MASTER,
        "always_on_top": 0,
        # Short beep when another station stops talking (1 = on).
        "roger_beep": 1,
        # Audio devices as "number:name"; empty means the system default device.
        "input_device": "",
        "output_device": "",
        "eqsl_user": "",
        "eqsl_password": "",
        "eqsl_qth": "",
        "qrz_user": "",
        "qrz_password": "",
        "qrz_api_key": "",
        # Interface language code, one of LANGUAGES.
        "language": DEFAULT_LANGUAGE,
        # Window scale, SCALE_MIN to SCALE_MAX.
        "scale": 1,
        # 1 when running under Wine: serial ports are not listed automatically.
        "wine": 0,
    },
    "rx_control": {
        # Manual, VOX, Serial CD, Serial CTS or Serial DSR.
        "mode": "Manual",
        "vox_threshold": 200,
        "vox_delay": 50,
        "vox_return": 5,
        "serial_port": "",
    },
    "tx_control": {
        # Manual, Serial RTS or Serial DTR.
        "mode": "Manual",
        # Ctrl key as push-to-talk (1 = on).
        "ctrl_key_ptt": 0,
        "serial_port": "",
        # Longest transmission, in seconds (TOT_MIN to TOT_MAX).
        "timeout": 180,
    },
    "auto": {
        # Connect automatically at startup (1 = on) to this room.
        "connect_at_start": 0,
        "room": "",
    },
    "alarms": {
        # Callsigns that raise an alarm when they join or leave.
        "callsigns": [],
    },
    "scan": {
        # Rooms visited by the scanner and the time spent in each one (250 to 60000 ms).
        "rooms": [],
        "interval_ms": 1000,
    },
    "aprs": {
        # Send the position to APRS-IS when transmitting (1 = on).
        "enabled": 0,
        "host": "rotate.aprs2.net",
        "port": 14580,
        "latitude": "",
        "longitude": "",
    },
    "update": {
        # Plain-text file holding the latest version number; empty disables the check.
        "version_url": "",
    },
}


def settings_path():
    """Location of the settings TinyDB file, in the database folder of the user data folder."""
    return os.path.join(database_dir(), "settings.json")


def _default_settings():
    """A fresh, independent copy of DEFAULT_SETTINGS."""
    return json.loads(json.dumps(DEFAULT_SETTINGS))


def _merge_settings(stored):
    """The default settings with the stored values of every known section and key laid over them.

    Sections and keys the program does not use are left out, so the next
    save removes them from the file.
    """
    merged = _default_settings()
    for section, values in (stored or {}).items():
        if isinstance(values, dict) and section in merged:
            merged[section].update({key: value for key, value in values.items() if key in merged[section]})
    return merged


class SettingsStore:
    """The settings, kept in memory and saved to database/settings.json with TinyDB.

    The whole settings document is read by load() and written by save().
    In between, values are read and changed in memory, which is fast and
    safe from any thread. get() returns text, getint() and getfloat()
    convert it and raise ValueError when that is not possible.
    """

    def __init__(self, file_path):
        self.file_path = file_path
        self._db = open_tinydb(file_path, private=True)
        self._data = _default_settings()

    # Loading and saving -------------------------------------------------

    def load(self):
        """Read the settings file and return the problems found as warnings.

        A file that cannot be read is kept as settings.json.bak and the
        default settings are used. When there is no settings file yet, the
        defaults are written.
        """
        warnings = []
        stored = None
        with _db_lock:
            try:
                stored = self._db.table(SETTINGS_TABLE).get(doc_id=SETTINGS_DOC_ID)
            except UNREADABLE_DATA_ERRORS as exc:
                log.error("%s cannot be read (%s); default settings are used.", self.file_path, exc)
                warnings.append(("storage.settings_unreadable", (set_aside_unreadable_file(self.file_path),)))
                self._db = open_tinydb(self.file_path, private=True)
            if stored is None:
                self._data = _default_settings()
                self.save()
                self._db.table(META_TABLE).upsert(
                    TinyDocument({"schema_version": SETTINGS_SCHEMA_VERSION}, doc_id=META_DOC_ID)
                )
            else:
                self._data = _merge_settings(stored)
        return warnings

    def save(self):
        """Write every section to the settings file in a single step."""
        with _db_lock:
            snapshot = json.loads(json.dumps(self._data))
            self._db.table(SETTINGS_TABLE).upsert(TinyDocument(snapshot, doc_id=SETTINGS_DOC_ID))

    # Sections ------------------------------------------------------------

    def sections(self):
        return list(self._data.keys())

    def has_section(self, section):
        return section in self._data

    def add_section(self, section):
        self._data.setdefault(section, {})

    def has_option(self, section, key):
        return key in self._data.get(section, {})

    # Reading -------------------------------------------------------------

    def get_value(self, section, key, fallback=None):
        """A value exactly as stored (text, number or list), or fallback when missing."""
        return self._data.get(section, {}).get(key, fallback)

    def get(self, section, key, fallback=None):
        """A value as text, or fallback when it is missing. Lists are joined with commas."""
        value = self.get_value(section, key, None)
        if value is None:
            return fallback
        if isinstance(value, (list, tuple)):
            return ",".join(str(item) for item in value)
        return str(value)

    def get_list(self, section, key):
        """A list value as a list of non-empty texts (a comma-separated text is split too)."""
        value = self.get_value(section, key, [])
        items = value if isinstance(value, (list, tuple)) else str(value).split(",")
        return [str(item).strip() for item in items if str(item).strip()]

    def getint(self, section, key, fallback=None):
        """A whole number, or fallback when it is missing. Raises ValueError when it is not a number."""
        text = self.get(section, key, None)
        return fallback if text is None else int(text.strip())

    def getfloat(self, section, key, fallback=None):
        """A decimal number, or fallback when it is missing. Raises ValueError when it is not a number."""
        text = self.get(section, key, None)
        return fallback if text is None else float(text.strip())

    # Changing ------------------------------------------------------------

    def set(self, section, key, value):
        """Change a value in memory; save() writes it to the file."""
        self._data.setdefault(section, {})[key] = value


# ---------------------------------------------------------------------------
# Room scanner
# ---------------------------------------------------------------------------

# Set to stop the running scanner thread; a new event is made for every start.
_scan_stop_event = None

# Room the station was in when the scanner started; it returns there on stop.
_room_before_scan = None

# How long the scanner stays in a room after the last voice frame, in milliseconds.
SCAN_VOICE_HOLD_MS = 5000


def scan_debug(message):
    """Scanner diagnostics, shown only when the application runs with --debug."""
    log.debug("[SCAN] %s", message)


def toggle_scan():
    """Start the scanner, or stop it when it is running."""
    scan_debug("SCAN toggled; scanner_running={}, session_active={}".format(scanner_running, session_active))
    if scanner_running:
        scanner_stop("SCAN toggled")
    else:
        scanner_start()


def _valid_scan_rooms():
    """Unique, non-empty scan rooms in their configured order."""
    global scan_room_list
    rooms = []
    for item in scan_room_list or []:
        room = str(item).strip()
        if room and room not in rooms:
            rooms.append(room)
    if rooms != list(scan_room_list or []):
        scan_room_list = rooms
    return rooms


def scan_rooms():
    """Rooms the scanner visits, in order."""
    return list(_valid_scan_rooms())


def _scan_interval_ms():
    """Time spent in each room, from the scan interval_ms setting (250-60000, default 1000)."""
    try:
        if config.has_option("scan", "interval_ms"):
            return max(250, min(60000, config.getint("scan", "interval_ms")))
    except ValueError as exc:
        scan_debug("Invalid SCAN interval in the settings ({}); using 1000 ms".format(exc))
    return 1000


def scanner_start():
    """Start rotating through the scan rooms. Returns True when it started.

    It needs a connection and at least one scan room; otherwise a "warning"
    event explains why it did not start.
    """
    global last_voice_ms, scan_index, scanner_running, _scan_stop_event, _room_before_scan
    scan_debug("Start requested: connected={}, configured_rooms={}".format(session_active, list(scan_room_list or [])))
    rooms = _valid_scan_rooms()
    if not session_active:
        scan_debug("Start refused: not connected to the Peanut server")
        emit_event("warning", title=tr("app.title"), message=tr("scan.needs_connection"))
        return False
    if not rooms:
        scan_debug("Start refused: no rooms configured")
        emit_event("warning", title=tr("app.title"), message=tr("scan.no_rooms"))
        return False

    if _scan_stop_event is not None:
        _scan_stop_event.set()
    stop_event = threading.Event()
    _scan_stop_event = stop_event
    _room_before_scan = active_room
    scan_index %= len(rooms)
    scanner_running = True
    last_voice_ms = monotonic_ms()
    resume_scanner()
    emit_event("scan_state", active=True)
    scan_debug("Scanner enabled: {} room(s), interval={} ms".format(len(rooms), _scan_interval_ms()))
    threading.Thread(target=_scanner_loop, args=(stop_event,), name="room-scanner", daemon=True).start()
    return True


def scanner_stop(reason="user requested", restore_room=True):
    """Stop the scanner.

    With restore_room=True (and while connected) the station goes back to the
    room it was in when the scanner started.
    """
    global scanner_running, active_room
    scan_debug("Stop requested: {}".format(reason))
    was_scanning = scanner_running
    scanner_running = False
    if _scan_stop_event is not None:
        _scan_stop_event.set()
    emit_event("scan_state", active=False)
    if was_scanning and restore_room and session_active and _room_before_scan and _room_before_scan != active_room:
        active_room = _room_before_scan
        pong()
        emit_event("scan_room", room=active_room)


def _scanner_loop(stop_event):
    """Visit the next scan room every interval until the scanner is stopped."""
    while not stop_event.is_set():
        if not scanner_room():
            return
        stop_event.wait(_scan_interval_ms() / 1000.0)


def scanner_room():
    """Move to the next scan room, unless the scanner is paused.

    Incoming audio and our own transmissions pause the rotation; it resumes
    SCAN_VOICE_HOLD_MS after the last voice frame. Returns False when the
    scanner has stopped.
    """
    global scan_index, active_room, last_voice_ms
    if not session_active:
        scanner_stop("connection lost", restore_room=False)
        return False
    if not scanner_running:
        return False
    try:
        rooms = _valid_scan_rooms()
        if not rooms:
            scanner_stop("no rooms configured")
            return False
        if ptt_pressed or tx_active:
            # Never change room in the middle of our own transmission.
            last_voice_ms = monotonic_ms()
            scan_debug("Paused while transmitting in room {!r}".format(active_room))
            return True
        scan_index %= len(rooms)
        if scan_paused:
            scan_debug("Paused for incoming audio; current room={!r}".format(active_room))
        else:
            active_room = rooms[scan_index]
            scan_debug("Switching to room {}/{}: {!r}".format(scan_index + 1, len(rooms), active_room))
            emit_event("scan_room", room=active_room)
            pong()
            scan_index = (scan_index + 1) % len(rooms)
        if scan_paused and monotonic_ms() - last_voice_ms > SCAN_VOICE_HOLD_MS:
            resume_scanner()
        return True
    except Exception:
        log.exception("Unexpected scanner error")
        scanner_stop("unexpected error")
        return False


def pause_scanner():
    """Incoming audio: keep the scanner in the current room for a while."""
    global last_voice_ms, scan_paused
    if not scan_paused:
        scan_debug("Audio activity detected; pausing scan")
    scan_paused = True
    last_voice_ms = monotonic_ms()


def resume_scanner():
    """Let the scanner move on to the next room again."""
    global scan_paused
    was_paused = scan_paused
    scan_paused = False
    if was_paused:
        scan_debug("Scanner resumed")


# ---------------------------------------------------------------------------
# Saving the settings
# ---------------------------------------------------------------------------

def save_settings():
    """Save the settings to database/settings.json.

    The file is replaced in a single step (see SafeJSONStorage), so a crash
    never leaves a half-written file. On Linux and macOS it is readable by
    its owner only, because it holds the access code and passwords.
    """
    config.save()


def _ensure_section(section):
    if not config.has_section(section):
        config.add_section(section)


# ---------------------------------------------------------------------------
# Alarms and scan list
# ---------------------------------------------------------------------------

def _new_alarm_state():
    return {"state": "off", "time": "", "room": ""}


def save_alarm_list():
    """Save the watched callsigns as the alarms callsigns list."""
    _ensure_section("alarms")
    with state_lock:
        calls = sorted(watched_calls.keys())
    config.set("alarms", "callsigns", calls)
    save_settings()


def save_scan_list():
    """Save the scan rooms as the scan rooms list."""
    _ensure_section("scan")
    config.set("scan", "rooms", list(scan_room_list))
    save_settings()


def _merge_alarm_calls(calls):
    """Replace the watched callsigns; calls already watched keep their state."""
    global watched_calls
    cleaned = {clean_callsign(call) for call in calls}
    cleaned.discard("")
    with state_lock:
        watched_calls = {call: watched_calls.get(call, _new_alarm_state()) for call in cleaned}


def set_alarm_callsigns(calls):
    """Replace the watched callsigns and save them.

    Calls already watched keep their state; new ones start as offline.
    """
    _merge_alarm_calls(calls)
    save_alarm_list()


def set_scan_rooms(rooms):
    """Replace the rooms visited by the scanner, restart from the first one and save them."""
    global scan_room_list, scan_index
    scan_room_list = list(dict.fromkeys(str(room).strip().upper() for room in rooms if str(room).strip()))
    scan_index = 0
    save_scan_list()
    scan_debug("Saved scan room list: {}".format(scan_room_list))


# ---------------------------------------------------------------------------
# Settings form
# ---------------------------------------------------------------------------

def _int_or_none(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _float_or_none(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _flag(value):
    """A checkbox value as 1 (ticked) or 0."""
    return 1 if _int_or_none(value) == 1 else 0


def _number_or_text(value):
    """A whole number when the text is one; otherwise the text, stripped."""
    number = _int_or_none(value)
    return number if number is not None else str(value).strip()


def validate_setup(values):
    """Check the settings form. Returns (message, field name) of the first problem, or None."""
    form_callsign = clean_callsign(values.get("form_callsign", ""))
    if len(form_callsign) < 3:
        return (tr("form.callsign_missing"), "form_callsign")
    if len(form_callsign) > 8 or form_callsign != str(values.get("form_callsign", "")).strip().upper():
        return (tr("form.callsign_invalid"), "form_callsign")

    dmr = str(values.get("form_dmr_id", "") or "").strip()
    if dmr and (_int_or_none(dmr) is None or not 0 <= int(dmr) <= DMRID_MAX):
        return (tr("form.dmr_id_invalid"), "form_dmr_id")

    scale = _int_or_none(values.get("form_scale_value"))
    if scale is None or not SCALE_MIN <= scale <= SCALE_MAX:
        return (tr("form.scale_invalid"), "form_scale")

    if values.get("form_rx_mode") not in RX_MODES:
        return (tr("form.rx_mode_invalid"), "form_rx_mode")
    if values["form_rx_mode"].startswith("Serial") and not values.get("form_rx_port"):
        return (tr("form.rx_port_missing"), "form_rx_port")
    if values.get("form_tx_mode") not in TX_MODES:
        return (tr("form.tx_mode_invalid"), "form_tx_mode")
    if values["form_tx_mode"].startswith("Serial") and not values.get("form_tx_port"):
        return (tr("form.tx_port_missing"), "form_tx_port")

    for field, low, high in (("vox_threshold", 1, 32767), ("vox_delay", 1, 500), ("vox_return", 0, 50)):
        number = _int_or_none(values.get(field))
        if number is None or not low <= number <= high:
            return (tr("form.vox_invalid"), field)

    tot = _int_or_none(values.get("form_tx_timeout"))
    if tot is None or not TOT_MIN <= tot <= TOT_MAX:
        return (tr("form.tx_timeout_invalid"), "form_tx_timeout")

    if int(values.get("form_auto_connect") or 0) == 1 and not values.get("form_auto_room"):
        return (tr("form.auto_room_missing"), "form_auto_room")

    if int(values.get("form_aprs_enabled") or 0) == 1:
        if len(str(values.get("form_aprs_host", "")).strip()) < 4:
            return (tr("form.aprs_host_invalid"), "form_aprs_host")
        aprs_port = _int_or_none(values.get("form_aprs_port"))
        if aprs_port is None or not 1 <= aprs_port <= 65535:
            return (tr("form.aprs_port_invalid"), "form_aprs_port")
        lat = _float_or_none(values.get("form_aprs_latitude"))
        if lat is None or not -90.0 <= lat <= 90.0:
            return (tr("form.aprs_latitude_invalid"), "form_aprs_latitude")
        lon = _float_or_none(values.get("form_aprs_longitude"))
        if lon is None or not -180.0 <= lon <= 180.0:
            return (tr("form.aprs_longitude_invalid"), "form_aprs_longitude")
    return None


def save_setup(values):
    """Validate and persist a plain settings dictionary; return a UI-neutral result.

    The result is {"status": "validation_error", "message", "focus"} or
    {"status": "saved", "needs_restart": bool, "warnings": [texts]}.
    """
    problem = validate_setup(values)
    if problem is not None:
        return {"status": "validation_error", "message": problem[0], "focus": problem[1]}

    new_call = clean_callsign(values["form_callsign"])
    new_scale = int(values["form_scale_value"])
    warnings = []
    if utils.access_code_for(new_call) != str(values.get("form_access_code", "")).strip():
        warnings.append(tr("login.wrong_code"))

    for section in ("general", "rx_control", "tx_control", "auto", "scan", "aprs"):
        _ensure_section(section)

    def put(section, key, value):
        config.set(section, key, value)

    # A server name that is not in the (possibly unloaded) server list keeps
    # the master in use, so an offline save never erases the server.
    master = master_of_server(values.get("form_server", "")) or master_host or DEFAULT_MASTER

    # Every value is stored with its natural type: numbers and checkboxes as
    # whole numbers, everything else as text.
    put("general", "callsign", new_call)
    put("general", "dmr_id", _int_or_none(values.get("form_dmr_id")) or 0)
    put("general", "message", str(values["form_message"]))
    put("general", "access_code", str(values["form_access_code"]).strip())
    put("general", "master", master)
    put("general", "always_on_top", _flag(values["form_always_on_top"]))
    put("general", "roger_beep", _flag(values["form_roger_beep"]))
    put("general", "input_device", str(values["input_device"]))
    put("general", "output_device", str(values["output_device"]))
    put("general", "eqsl_user", str(values["eqsl_user"]))
    put("general", "eqsl_password", str(values["form_eqsl_password"]))
    put("general", "eqsl_qth", str(values["eqsl_qth"]))
    put("general", "qrz_user", str(values["qrz_user"]))
    put("general", "qrz_password", str(values["form_qrz_password"]))
    put("general", "qrz_api_key", str(values["form_qrz_api_key"]))
    put("general", "language", str(values["form_language"]))
    put("general", "scale", new_scale)

    put("rx_control", "mode", values["form_rx_mode"])
    put("rx_control", "vox_threshold", int(values["vox_threshold"]))
    put("rx_control", "vox_delay", int(values["vox_delay"]))
    put("rx_control", "vox_return", int(values["vox_return"]))
    put("rx_control", "serial_port", str(values["form_rx_port"]) if values["form_rx_mode"].startswith("Serial") else "")

    put("tx_control", "mode", values["form_tx_mode"])
    put("tx_control", "ctrl_key_ptt", _flag(values["form_ctrl_key_ptt"]))
    put("tx_control", "serial_port", str(values["form_tx_port"]) if values["form_tx_mode"].startswith("Serial") else "")
    put("tx_control", "timeout", int(values["form_tx_timeout"]))

    put("auto", "connect_at_start", _flag(values["form_auto_connect"]))
    put("auto", "room", str(values["form_auto_room"]))
    put("aprs", "enabled", _flag(values["form_aprs_enabled"]))
    put("aprs", "host", str(values["form_aprs_host"]).strip())
    put("aprs", "port", _number_or_text(values["form_aprs_port"]))
    put("aprs", "latitude", str(values["form_aprs_latitude"]).strip())
    put("aprs", "longitude", str(values["form_aprs_longitude"]).strip())

    save_settings()

    needs_restart = values["form_language"] != language_setting or new_scale != ui_scale_setting
    return {"status": "saved", "needs_restart": needs_restart, "warnings": warnings}


def reload_settings():
    """Read the settings again and refresh what depends on them (station, rooms, serial ports)."""
    load_settings()
    close_serial_ports()
    open_serial_ports()
    lookup_queue.put((my_call, ""))
    start_worker(load_room_list, True, name="load-rooms")


# ---------------------------------------------------------------------------
# Reading the settings
# ---------------------------------------------------------------------------

def _config_int(value, default):
    """Turn a configuration value into an int, or return default when it is not a number."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _opt(section, key, default=""):
    """A setting as text, or default when it is missing."""
    return config.get(section, key, fallback=default)


def _opt_int(section, key, default, low, high):
    """A whole-number configuration value inside [low, high]; default (with a warning) otherwise."""
    text = _opt(section, key, None)
    if text is None or str(text).strip() == "":
        return default
    number = _config_int(text, None)
    if number is None or not low <= number <= high:
        config_warnings.append(("storage.value_invalid", (section, key, text)))
        return default
    return number


def load_settings():
    """Load the settings into the plain module-level variables (texts and ints).

    Missing or invalid values fall back to their defaults and are reported in
    config_warnings as (text key, format arguments) pairs, because the
    interface texts are loaded after the settings. Reading the settings
    never stops the program. A settings file that cannot be read at all is
    kept as settings.json.bak.
    """
    global always_on_top, qrz_api_key, aprs_host_setting, aprs_lat_setting, aprs_lon_setting, aprs_port_setting
    global roger_beep, callsign, aprs_enabled_setting, auto_connect_setting, vox_delay_setting, dmr_id, input_device
    global master_host, ctrl_key_ptt, language_setting, tx_message, my_call, output_device, qrz_password
    global access_code, eqsl_password, eqsl_qth_name, vox_return_setting, auto_room, rx_serial_port
    global rx_mode, scan_room_list, vox_threshold_setting, tx_serial_port, tx_mode
    global tx_timeout_setting, qrz_username, eqsl_username, running_under_wine, ui_scale_setting

    del config_warnings[:]
    config_warnings.extend(config.load())
    # The audio devices may have changed: they are looked up again.
    forget_audio_devices()

    my_call = clean_callsign(_opt("general", "callsign")) or "NOCALL"
    callsign = my_call
    dmr_id = _opt_int("general", "dmr_id", 0, 0, DMRID_MAX)
    tx_message = _opt("general", "message")
    access_code = str(_opt("general", "access_code")).strip()
    master_host = str(_opt("general", "master")).strip() or DEFAULT_MASTER
    always_on_top = _opt_int("general", "always_on_top", 0, 0, 1)
    roger_beep = _opt_int("general", "roger_beep", 0, 0, 1)
    eqsl_username = _opt("general", "eqsl_user")
    eqsl_password = _opt("general", "eqsl_password")
    eqsl_qth_name = _opt("general", "eqsl_qth")
    qrz_username = _opt("general", "qrz_user")
    qrz_password = _opt("general", "qrz_password")
    qrz_api_key = _opt("general", "qrz_api_key")
    # An empty device setting means "the system default device".
    input_device = str(_opt("general", "input_device")).strip()
    output_device = str(_opt("general", "output_device")).strip()
    language_setting = str(_opt("general", "language", DEFAULT_LANGUAGE)).strip() or DEFAULT_LANGUAGE
    if language_setting not in LANGUAGES:
        config_warnings.append(("storage.value_invalid", ("general", "language", language_setting)))
        language_setting = DEFAULT_LANGUAGE
    running_under_wine = str(_opt("general", "wine", "0")).strip() or "0"
    ui_scale_setting = _opt_int("general", "scale", 1, SCALE_MIN, SCALE_MAX)

    rx_mode = _opt("rx_control", "mode", "Manual") or "Manual"
    if rx_mode not in RX_MODES:
        config_warnings.append(("storage.value_invalid", ("rx_control", "mode", rx_mode)))
        rx_mode = "Manual"
    vox_threshold_setting = _opt_int("rx_control", "vox_threshold", 200, 1, 32767)
    vox_delay_setting = _opt_int("rx_control", "vox_delay", 50, 1, 500)
    vox_return_setting = _opt_int("rx_control", "vox_return", 5, 0, 50)
    rx_serial_port = str(_opt("rx_control", "serial_port")).strip()

    tx_mode = _opt("tx_control", "mode", "Manual") or "Manual"
    if tx_mode not in TX_MODES:
        config_warnings.append(("storage.value_invalid", ("tx_control", "mode", tx_mode)))
        tx_mode = "Manual"
    ctrl_key_ptt = _opt_int("tx_control", "ctrl_key_ptt", 0, 0, 1)
    tx_serial_port = str(_opt("tx_control", "serial_port")).strip()
    tx_timeout_setting = str(_opt_int("tx_control", "timeout", 180, TOT_MIN, TOT_MAX))

    auto_connect_setting = _opt_int("auto", "connect_at_start", 0, 0, 1)
    auto_room = str(_opt("auto", "room")).strip()
    _merge_alarm_calls(config.get_list("alarms", "callsigns"))

    # Room names are upper case on the server, so the saved ones are too
    # (a hand-edited settings file may hold them in any case).
    scan_room_list = list(dict.fromkeys(room.upper() for room in config.get_list("scan", "rooms")))

    aprs_enabled_setting = _opt_int("aprs", "enabled", 0, 0, 1)
    aprs_host_setting = str(_opt("aprs", "host", "rotate.aprs2.net")).strip()
    aprs_port_setting = str(_opt("aprs", "port", "14580")).strip()
    aprs_lat_setting = str(_opt("aprs", "latitude")).strip()
    aprs_lon_setting = str(_opt("aprs", "longitude")).strip()

    for key, arguments in config_warnings:
        log.warning("Settings: %s %s", key, arguments)


def config_warning_texts():
    """The problems found in the settings and database files as readable texts in the user's language."""
    return [tr(key).format(*arguments) for key, arguments in config_warnings]
