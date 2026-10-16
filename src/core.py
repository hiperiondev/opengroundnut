# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Application coordination: startup, connection, rooms, monitors, RadioID list and shutdown.

This module (like every other non-GUI module) never touches a window or a
widget. Whatever the user should see is published with emit_event() (see
events.py) and whatever the user decides reaches the core through the plain
functions defined here, such as connect_to_server(), enter_room() or
toggle_connection().
"""

import itertools

# The server sends a PING every few seconds; after this long without one the
# connection is considered lost and a reconnection starts.
SERVER_SILENCE_MS = 15000

# Wait before an automatic reconnection, in seconds.
RECONNECT_DELAY = 10

# Wait before the automatic connection at startup, in seconds (it gives the
# room list time to load).
AUTOSTART_DELAY = 10

# Most alarm log entries kept in memory.
ALARM_LOG_LIMIT = 1000

# Address of the RadioID user list.
RADIOID_USERS_URL = "https://database.radioid.net/static/user.csv"

# Waits between attempts while the server or room list cannot be loaded, in
# seconds (the last one repeats). A computer that starts before its network
# is up gets its lists as soon as the network appears.
LIST_RETRY_DELAYS = (5, 10, 30, 60)

# Once loaded, the room list is read again this often, in seconds, so new
# rooms appear without restarting the program.
ROOM_LIST_REFRESH_SECONDS = 600

# Wait before the first check of the stations online after connecting, in
# seconds; later checks follow every ONLINE_CHECK_SECONDS.
FIRST_ONLINE_CHECK_SECONDS = 3
ONLINE_CHECK_SECONDS = 20

# Worker threads of the current connection.
_rx_thread = None
_vox_thread = None

# Set to cancel a pending automatic reconnection or auto-start.
_reconnect_cancel = threading.Event()
_reconnect_pending = False
_autostart_cancel = threading.Event()

# True once the user pressed Connect or Disconnect: auto-start then stays out of the way.
_user_chose_connection = False

# Station lookup thread (one for the whole run).
_lookup_worker = None

# Set to make the server and room list worker load both lists right away.
_lists_wakeup = threading.Event()

# True once a room list has been loaded; the first one preselects the
# auto-start room.
_rooms_loaded_once = False


# ---------------------------------------------------------------------------
# Startup and shutdown
# ---------------------------------------------------------------------------

def initialize_application():
    """Prepare everything the application needs before any interface starts.

    Opens the settings (database/settings.json, created with the default
    values on the first start), lists the serial ports, opens the logbook
    and makes sure the picture folder exists.
    """
    global config
    ensure_dir(database_dir())
    config = SettingsStore(settings_path())
    load_settings()
    load_serial_ports()

    open_logbook()
    ensure_dir(app_path("images"))


def start_application():
    """Start the audio system, the background workers and the first server queries.

    Call it once the interface (if any) has registered its event listener and
    is visible, so the first events (server list, rooms, station data...)
    reach it. Every network request runs in the background. When the sound
    system cannot be started, everything else still starts and an "error"
    event explains why the station cannot connect.
    """
    global _lookup_worker
    for warning in config_warning_texts():
        emit_event("warning", title=tr("app.title"), message=warning)
    open_serial_ports()
    start_status_monitor()
    lookup_queue.put((my_call, ""))
    _lookup_worker = start_worker(station_lookup_loop, name="station-lookup")

    start_worker(_server_lists_worker, name="server-lists")
    start_worker(check_for_update, name="version-check")
    if not radioid_index_ready():
        # First start: the RadioID list is downloaded once in the background.
        start_worker(refresh_radioid_list, False, name="radioid-download")

    start_audio_system()

    if int(auto_connect_setting or 0) == 1:
        start_worker(auto_start_worker, name="auto-start")


def start_audio_system():
    """Start PortAudio. Returns True when it works; otherwise reports why and returns False."""
    global p
    try:
        p = pyaudio.PyAudio()
    except Exception as exc:
        p = None
        log.error("The sound system cannot be started: %s", exc)
        emit_event("error", title=tr("audio.title"), message=tr("audio.unavailable") + "\n" + str(exc))
        return False
    return True


def shutdown():
    """Stop every loop, leave the server and release audio and serial devices.

    Safe to call more than once and from any thread.
    """
    global lookups_stopped, active_monitor_stopped, app_closing, user_wants_connection, p
    with state_lock:
        if app_closing:
            return
        app_closing = True
    user_wants_connection = False
    _reconnect_cancel.set()
    _autostart_cancel.set()
    _lists_wakeup.set()
    lookups_stopped = True
    active_monitor_stopped = True
    if scanner_running:
        scanner_stop("closing", restore_room=False)
    if session_active:
        disconnect_from_server()
    close_serial_ports()
    stop_recording()
    portaudio, p = p, None
    if portaudio is not None:
        # PortAudio is released only when no audio thread can still be
        # using one of its streams, including the thread running this code;
        # otherwise the operating system frees it when the program ends.
        audio_threads = [
            thread for thread in (_rx_thread, _vox_thread, _tx_thread)
            if thread is not None and thread.is_alive()
        ]
        if audio_threads:
            log.warning("Audio threads still running at exit (%s); PortAudio is left to the system.",
                        ", ".join(thread.name for thread in audio_threads))
            return
        try:
            portaudio.terminate()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Serial ports (squelch input and PTT output)
# ---------------------------------------------------------------------------

def _open_serial_port(port_name):
    """Open a serial port without keying the radio; None (and an error event) on failure."""
    try:
        return utils.open_serial_quiet(port_name)
    except (OSError, serial.SerialException) as e:
        log.error("Serial port %s cannot be opened: %s", port_name, e)
        emit_event("error", title="Error", message=tr("serial.port_unavailable").format(port_name) + "\n" + str(e))
        return None


def open_serial_ports():
    """Open the serial ports chosen for receive and transmit control."""
    global serial_rx, serial_tx
    if rx_mode.startswith("Serial") and rx_serial_port:
        serial_rx = _open_serial_port(rx_serial_port)
    if tx_mode.startswith("Serial") and tx_serial_port:
        if tx_serial_port == rx_serial_port and serial_rx is not None:
            serial_tx = serial_rx
        else:
            serial_tx = _open_serial_port(tx_serial_port)


def close_serial_ports():
    """Release the PTT line and close the serial ports."""
    global serial_rx, serial_tx
    for port_handle in {id(port_item): port_item for port_item in (serial_tx, serial_rx) if port_item is not None}.values():
        try:
            if port_handle.is_open:
                port_handle.rts = False
                port_handle.dtr = False
                port_handle.close()
        except (OSError, serial.SerialException) as exc:
            log.warning("Serial port could not be closed cleanly: %s", exc)
    serial_rx = None
    serial_tx = None


def load_serial_ports():
    """List the serial ports at startup (not under Wine, where the list is unreliable)."""
    if running_under_wine == "1":
        return
    try:
        for found_port in utils.serial_ports():
            if found_port not in serial_port_list:
                serial_port_list.append(found_port)
    except Exception as exc:
        log.warning("Unable to list serial ports: %s", exc)


def rescan_serial_ports():
    """List the serial ports again (not under Wine) and return the sorted list."""
    load_serial_ports()
    return sorted(set(serial_port_list))


# ---------------------------------------------------------------------------
# Servers and rooms
# ---------------------------------------------------------------------------

def load_server_list(log_failure=True):
    """Load the list of Peanut master servers and publish their names.

    Returns True when the list was loaded. On failure the list already
    known is kept, and the server list worker tries again later;
    log_failure=False writes the failure to the debug log only.
    """
    global server_list
    try:
        resp = http_get_with_fallback(MASTERS_URL_PATH)
        servers = resp.json() if resp.status_code == 200 else None
    except (requests.exceptions.RequestException, ValueError) as e_req:
        log.log(logging.WARNING if log_failure else logging.DEBUG, "Failed to load masters.json: %s", e_req)
        return False
    if not isinstance(servers, list):
        log.warning("masters.json has an unexpected format")
        return False
    server_list = [item for item in servers if isinstance(item, dict) and item.get("name") and item.get("master")]
    names = [str(item["name"]) for item in server_list]
    emit_event("servers_loaded", names=names, current=master_host)
    return True


def load_room_list(initial_load=False, log_failure=True):
    """Load the rooms of the current server and publish the room groups.

    Returns True when the list was loaded. On failure the rooms already
    known are kept, and the server list worker tries again later;
    log_failure=False writes the failure to the debug log only.
    """
    global room_list, room_groups, _rooms_loaded_once
    try:
        resp = http_get_with_fallback(master_host + "/api/rooms4.json")
        rooms = resp.json() if resp.status_code == 200 else None
    except (requests.exceptions.RequestException, ValueError) as e_req:
        log.log(logging.WARNING if log_failure else logging.DEBUG, "Failed to load rooms4.json: %s", e_req)
        return False
    if not isinstance(rooms, list):
        log.warning("rooms4.json has an unexpected format")
        return False
    _rooms_loaded_once = True
    room_list = [item for item in rooms if isinstance(item, dict)]

    # The fixed entries are always available; local rooms have no country.
    groups = ["PEANUT", "ALL", tr("rooms.bookmarks")]
    for item in room_list:
        if item.get("type") != "local" and item.get("country"):
            groups.append(str(item["country"]).upper())
    room_groups = sorted(set(groups))
    emit_event("rooms_loaded", countries=list(room_groups), initial=initial_load)
    return True


def _server_lists_worker():
    """Keep the server and room lists loaded for the whole run.

    Until both lists are loaded they are tried again after each of the
    LIST_RETRY_DELAYS. Once loaded, the room list is read again every
    ROOM_LIST_REFRESH_SECONDS. refresh_server_lists() wakes the worker up so
    both lists are read at once.
    """
    servers_ok = False
    failures = 0
    while not app_closing:
        forced = _lists_wakeup.is_set()
        _lists_wakeup.clear()
        # A failure is written to the log once per outage, not on every retry.
        report = failures == 0 or forced
        if forced or not servers_ok:
            servers_ok = load_server_list(log_failure=report) or servers_ok
        rooms_ok = load_room_list(not _rooms_loaded_once, log_failure=report)
        if servers_ok and rooms_ok:
            failures = 0
            delay = ROOM_LIST_REFRESH_SECONDS
        else:
            delay = LIST_RETRY_DELAYS[min(failures, len(LIST_RETRY_DELAYS) - 1)]
            failures += 1
        _lists_wakeup.wait(delay)


def refresh_server_lists():
    """Load the server and room lists again now (the refresh button)."""
    _lists_wakeup.set()


def set_selected_room(room):
    """Remember the room the user has chosen (it is not entered yet)."""
    global selected_room
    selected_room = str(room or "").strip()


def enter_room(room):
    """Make a room the active one and announce it to the server when connected.

    Returns True when the room was entered. The room never changes in the
    middle of our own transmission, because every frame of a transmission
    must name the same room; a "warning" event explains it instead. A room
    chosen by the user while the scanner runs stops the scanner in that room.
    """
    global active_room
    room = str(room or "").strip()
    if not room:
        return False
    if ptt_pressed or tx_active:
        emit_event("warning", title=tr("app.title"), message=tr("rooms.busy_transmitting"))
        return False
    if scanner_running:
        scanner_stop("room chosen by the user", restore_room=False)
    active_room = room
    if session_active:
        pong()
        start_worker(refresh_online_list, name="online-list")
    return True


def set_mute(muted):
    """Mute (True) or unmute (False) the received audio.

    Muting also releases the serial PTT line of a radio link while a room is
    heard, so the radio never transmits a silent carrier.
    """
    global speaker_muted
    speaker_muted = bool(muted)
    if link_state == 1:
        _set_serial_tx_line(not speaker_muted)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def station_is_configured():
    """True when a real callsign and an access code have been entered.

    Fresh settings hold the placeholder callsign NOCALL and an empty
    code, so the station has nothing to log in with yet.
    """
    call = str(my_call or "").strip().upper()
    return bool(call) and call != "NOCALL" and bool(str(access_code or "").strip())


def connect_to_server(quiet=False, room=None):
    """Connect to the server and enter a room. Returns True when the connection started.

    The station is "connecting" until the server accepts the login (see
    mark_link_up). With quiet=True problems are only logged, which is what
    automatic reconnections use.
    """
    global connection_generation, active_room, session_active, user_wants_connection, link_up, connection_closed
    global _rx_thread, _vox_thread
    if session_active or app_closing:
        return session_active

    def problem(message):
        log.warning("Connection not started: %s", message)
        if not quiet:
            emit_event("error", title=tr("app.title"), message=message)
        return False

    if not station_is_configured():
        # Nothing to log in with yet (fresh settings): point the user to
        # the Settings tab instead of reporting a wrong access code.
        log.warning("Connection not started: the callsign or the access code is not set")
        if not quiet:
            emit_event("setup_required", title=tr("app.title"), message=tr("login.setup_required"))
        return False
    if utils.access_code_for(my_call) != str(access_code):
        return problem(tr("login.wrong_code"))
    room = str(room or selected_room or "").strip()
    if not room:
        return problem(tr("main.choose_room"))
    try:
        sock = open_udp_socket()
    except OSError as exc:
        return problem(tr("login.server_unreachable").format(master_host, exc))

    with state_lock:
        connection_generation += 1
        generation = connection_generation
        active_room = room
        link_up = False
        connection_closed = False
        session_active = True
        user_wants_connection = True
    _reconnect_cancel.clear()

    log.info("Connecting to %s (%s:%s), room %s", master_host, server_addr[0], server_addr[1], room)
    emit_event("connecting")
    if room != selected_room:
        emit_event("scan_room", room=room)
    apply_link_state(0)
    start_watchdog()
    _rx_thread = start_worker(receive_loop, sock, generation, name="rx-audio")
    start_worker(online_monitor_loop, generation, name="online-monitor")
    _vox_thread = None
    if rx_mode != "Manual":
        _vox_thread = start_worker(vox_transmit_loop, generation, name="vox-input")
    return True


def mark_link_up():
    """The server accepted the login (ACK or first PING): the station is on the air."""
    global link_up
    with state_lock:
        if link_up or not session_active:
            return
        link_up = True
    note_server_alive()
    log.info("Connected to %s", master_host)
    emit_event("connection_changed", connected=True)
    apply_link_state(0)
    pong()
    start_worker(refresh_online_list, name="online-list")
    # Rooms created while we were away appear on every (re)connection.
    start_worker(load_room_list, name="load-rooms")


def _join_worker(thread, timeout=2.0):
    """Wait a little for a worker thread to end (never for the calling thread itself)."""
    if thread is not None and thread.is_alive() and thread is not threading.current_thread():
        thread.join(timeout)


def disconnect_from_server(user_request=True):
    """Leave the server: end any transmission, log out, close the socket and stop the workers.

    user_request=False is used for a lost connection, which keeps the wish to
    be connected so the automatic reconnection can restore it.
    """
    global connection_closed, ptt_allowed, session_active, link_up, user_wants_connection
    if user_request:
        user_wants_connection = False
        _reconnect_cancel.set()
    was_connected = session_active
    if scanner_running:
        scanner_stop("disconnect", restore_room=False)
    # The end frame is sent while the socket is still open.
    stop_transmit(wait=True)
    with state_lock:
        session_active = False
        link_up = False
        ptt_allowed = False
        connection_closed = True
    stop_watchdog()
    if was_connected:
        logout()
    close_udp_socket()
    _join_worker(_rx_thread)
    _join_worker(_vox_thread)
    if was_connected:
        log.info("Disconnected from %s", master_host)
        emit_event("connection_changed", connected=False)
        apply_link_state(0)


def toggle_connection():
    """The Connect / Disconnect button."""
    global _user_chose_connection, user_wants_connection
    _user_chose_connection = True
    _autostart_cancel.set()
    if session_active:
        disconnect_from_server()
    elif _reconnect_pending:
        # Pressing the button while a reconnection is pending cancels it.
        user_wants_connection = False
        _reconnect_cancel.set()
        emit_event("connection_changed", connected=False)
    else:
        connect_to_server()


def auto_start_worker():
    """Connect to the auto-start room shortly after startup, unless the user already acted."""
    if _autostart_cancel.wait(AUTOSTART_DELAY):
        return
    if app_closing or session_active or _user_chose_connection:
        return
    room = auto_room or selected_room
    if room:
        set_selected_room(room)
    connect_to_server(room=room)


# ---------------------------------------------------------------------------
# Server watchdog and automatic reconnection
# ---------------------------------------------------------------------------

# Every start_watchdog() starts a new watchdog thread; older ones see that the
# generation changed and end on their own.
_watchdog_generation = 0


def start_watchdog():
    """Start watching the server's PINGs for the new connection."""
    global watchdog_active, last_ping_ms, _watchdog_generation
    last_ping_ms = monotonic_ms()
    watchdog_active = True
    _watchdog_generation += 1
    start_worker(_server_watchdog, _watchdog_generation, name="server-watchdog")


def stop_watchdog():
    """Stop watching the server."""
    global watchdog_active
    watchdog_active = False


def _server_watchdog(generation):
    """Check every 5 seconds that the server still sends PING frames."""
    while not app_closing:
        sleep(5)
        if not watchdog_active or not session_active or generation != _watchdog_generation:
            return
        if monotonic_ms() - last_ping_ms > SERVER_SILENCE_MS:
            server_timed_out()
            return


def server_timed_out():
    """The server stopped answering: drop the connection and reconnect in a moment."""
    log.warning("The server stopped answering; reconnecting in %s seconds.", RECONNECT_DELAY)
    disconnect_from_server(user_request=False)
    emit_event("reconnecting")
    schedule_reconnect()


def schedule_reconnect():
    """Reconnect after RECONNECT_DELAY, unless the user disconnects or the program closes first."""
    global _reconnect_pending
    with state_lock:
        if _reconnect_pending or app_closing:
            return
        _reconnect_pending = True
    _reconnect_cancel.clear()
    start_worker(_reconnect_worker, name="reconnect")


def _reconnect_worker():
    global _reconnect_pending
    try:
        if _reconnect_cancel.wait(RECONNECT_DELAY):
            return
        if not user_wants_connection or session_active or app_closing:
            return
        if connect_to_server(quiet=True, room=active_room):
            return
    finally:
        with state_lock:
            _reconnect_pending = False
    # The server is still unreachable: try again later.
    if user_wants_connection and not app_closing:
        schedule_reconnect()


# ---------------------------------------------------------------------------
# Transmission log
# ---------------------------------------------------------------------------

def log_end_of_transmission(call, room, started_at, duration_seconds):
    """Publish a finished transmission for the "Last heard" list."""
    emit_event(
        "transmission_logged",
        time=strftime("%H:%M:%S", localtime(started_at)),
        callsign=str(call),
        name=radioid_first_name(call),
        duration=format_duration(duration_seconds),
    )


def tx_timeout_seconds():
    """Longest transmission allowed, from the tx_control timeout setting (TOT_MIN to TOT_MAX seconds)."""
    try:
        return max(TOT_MIN, min(TOT_MAX, int(tx_timeout_setting)))
    except (TypeError, ValueError):
        return 180


# ---------------------------------------------------------------------------
# Active transmissions (Monitor) and stations online
# ---------------------------------------------------------------------------

# True while the active transmission poller thread is running.
_qso_monitor_running = False


def active_monitor_loop():
    """Poll the transmissions active on the server once per second."""
    global active_transmissions
    request_failed = False
    while not active_monitor_stopped and not app_closing:
        try:
            resp = http_get_with_fallback(master_host + "/api/active.json")
            if resp.status_code == 200:
                data = resp.json()
                active_transmissions = data if isinstance(data, list) else []
        except (requests.exceptions.RequestException, ValueError) as e_req:
            # A transient network error only skips this poll. It is reported
            # once per outage and the loop keeps trying.
            if not request_failed:
                log.warning("Failed to load active.json: %s", e_req)
            request_failed = True
        else:
            request_failed = False
        sleep(1)
    active_transmissions = []


def _run_qso_monitor():
    """Run the active transmission poller and remember when it ends."""
    global _qso_monitor_running
    try:
        active_monitor_loop()
    finally:
        _qso_monitor_running = False


def start_active_qso_monitor():
    """Start polling the transmissions active on the server (once per second)."""
    global active_monitor_stopped, _qso_monitor_running
    active_monitor_stopped = False
    if not _qso_monitor_running:
        _qso_monitor_running = True
        start_worker(_run_qso_monitor, name="active-monitor")


def stop_active_qso_monitor():
    """Stop polling the active transmissions; the poller ends within a second."""
    global active_monitor_stopped
    active_monitor_stopped = True


def _visible_stations(whois_list):
    """whois.json entries of every connected station, whatever device it uses.

    Stations linked through hotspots, gateways or other clients are listed
    and watched by the alarms exactly like desktop and Android stations.
    """
    for item in whois_list if isinstance(whois_list, list) else []:
        if isinstance(item, dict) and item.get("Call"):
            yield item


def _callsigns_in_current_room(whois_list):
    """Callsigns of whois.json in the room we are in (the selected room when offline)."""
    room = active_room if session_active else selected_room
    return [item["Call"] for item in _visible_stations(whois_list) if item.get("room") == room]


def _fetch_whois():
    """whois.json of the current server, or None when it cannot be read."""
    try:
        resp = http_get_with_fallback(master_host + "/api/whois.json")
        return resp.json() if resp.status_code == 200 else None
    except (requests.exceptions.RequestException, ValueError) as e_req:
        log.warning("Failed to load whois.json: %s", e_req)
        return None


def refresh_online_list():
    """Refresh the list of stations in the current room once."""
    whois_list = _fetch_whois()
    if whois_list is not None:
        emit_event("online_stations", callsigns=_callsigns_in_current_room(whois_list))


def _connection_wait(generation, seconds):
    """Wait up to `seconds`; returns False as soon as the connection ends."""
    deadline = monotonic() + seconds
    while monotonic() < deadline:
        if not connection_is_current(generation):
            return False
        sleep(0.5)
    return connection_is_current(generation)


def online_monitor_loop(generation):
    """Refresh the online list and check the watched callsigns (alarms) while connected.

    The first check runs a few seconds after connecting and only records
    which watched stations are already online, so connecting never sounds an
    alarm for them; from then on every change raises an alarm. Later checks
    follow every ONLINE_CHECK_SECONDS.
    """
    baseline = True
    wait_seconds = FIRST_ONLINE_CHECK_SECONDS
    while _connection_wait(generation, wait_seconds):
        wait_seconds = ONLINE_CHECK_SECONDS
        whois_list = _fetch_whois()
        if whois_list is None:
            continue
        try:
            emit_event("online_stations", callsigns=_callsigns_in_current_room(whois_list))
            online = {item["Call"]: str(item.get("room", "")) for item in _visible_stations(whois_list)}
            _update_alarms(online, baseline=baseline)
            baseline = False
        except Exception:
            log.exception("Online station check failed")


_alarm_ids = itertools.count(1)


def _update_alarms(online, baseline=False):
    """Compare the watched callsigns with the stations online and log every change.

    With baseline=True the states are only brought up to date, without an
    alarm: it is used for the first check after connecting.
    """
    changed = False
    now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    with state_lock:
        for call, state in watched_calls.items():
            is_online = call in online
            if (state["state"] == "on") == is_online:
                continue
            state["state"] = "on" if is_online else "off"
            state["time"] = now_text
            state["room"] = online.get(call, "")
            if baseline:
                continue
            alarm_history[next(_alarm_ids)] = {
                "callsign": call,
                "state": state["state"],
                "room": state["room"],
                "time": now_text,
            }
            changed = True
        while len(alarm_history) > ALARM_LOG_LIMIT:
            del alarm_history[next(iter(alarm_history))]
        lines = alarm_log_lines() if changed else None
    if changed:
        start_worker(play_wave, resource_path(os.path.join("data", "alarm.wav")), name="alarm-sound")
        emit_event("alarms_updated", lines=lines)


def alarm_log_lines():
    """Alarm history as tab separated "call, state, time, room" rows, newest first."""
    with state_lock:
        entries = list(alarm_history.values())
    return [
        "{}\t{}\t{}\t{}".format(entry["callsign"], entry["state"], entry["time"], entry["room"])
        for entry in reversed(entries)
    ]


def clear_alarm_log():
    """Forget the alarm history."""
    with state_lock:
        alarm_history.clear()


# ---------------------------------------------------------------------------
# RadioID user list
# ---------------------------------------------------------------------------

def lookup_radioid(_callsign):
    """Find a callsign in the RadioID list, remember it and publish its identity."""
    row = None
    try:
        row = radioid_find(_callsign)
    except (OSError,) + UNREADABLE_DATA_ERRORS as exc:
        log.warning("RadioID lookup failed: %s", exc)
    if row:
        location = " ".join(part for part in (row.get("city"), row.get("state"), row.get("country")) if part)[:70]
        full_name = " ".join(part for part in (row.get("first"), row.get("last")) if part)[:40]
        entry = {
            "id": str(row.get("id", "")),
            "full_name": full_name,
            "location": location,
            "name": str(row.get("first", "")).strip(),
        }
    else:
        entry = {"id": tr("station.unknown"), "full_name": tr("station.unknown"), "location": "", "name": tr("station.unknown")}
    radioid_cache[_callsign] = entry
    emit_event("station_identity", identity=entry["id"], name=entry["full_name"], location=entry["location"])


def update_user_ids():
    """Download a fresh RadioID user list in the background (the user asked for it)."""
    start_worker(refresh_radioid_list, True, name="radioid-download")


# Held while the RadioID list is downloaded and stored, so a second request
# (the "Update IDs file" button during the first-start download) never runs
# at the same time.
_radioid_download_lock = threading.Lock()


def refresh_radioid_list(report_errors=True):
    """Download the RadioID user list, check it and store it in the TinyDB files.

    The list arrives as a CSV file, which is only kept until its content is
    stored; the list in use is replaced only when the new one is complete.
    report_errors=False (the automatic download on the first start) only
    logs a failure; the user can retry with the "Update IDs file" button.
    A request made while a download is already running is ignored: the
    running one publishes "user_ids_updated" when it ends.
    """
    if not _radioid_download_lock.acquire(blocking=False):
        log.info("A RadioID download is already running; this request is ignored.")
        return
    try:
        _download_radioid_list(report_errors)
    finally:
        _radioid_download_lock.release()


def _download_radioid_list(report_errors):
    """The download itself (the caller holds _radioid_download_lock)."""
    ensure_dir(database_dir())
    # Partial files left behind by a download that was cut off (program
    # closed, power lost) are of no use any more.
    for leftover in os.listdir(database_dir()):
        if leftover.startswith("user") and leftover.endswith(".csv.part"):
            _remove_quietly(os.path.join(database_dir(), leftover))
    handle, partial = tempfile.mkstemp(prefix="user-", suffix=".csv.part", dir=database_dir())
    os.close(handle)
    try:
        with http_session.get(RADIOID_USERS_URL, stream=True, headers=http_headers(), timeout=(10, 60)) as resp:
            resp.raise_for_status()
            with open(partial, "wb") as out_file:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    out_file.write(chunk)
        with open(partial, encoding="utf-8", errors="replace") as check_file:
            header = check_file.readline()
        if not header.upper().startswith("RADIO_ID,CALLSIGN") or os.path.getsize(partial) < 100_000:
            raise ValueError(tr("radioid.invalid_file"))
        build_radioid_index(lambda: _radioid_csv_rows(partial), "radioid.net")
    except Exception as exc:
        log.warning("RadioID download failed: %s", exc)
        if report_errors:
            emit_event("error", title="Error", message=tr("radioid.download_failed").format(exc))
        emit_event("user_ids_updated", ok=False)
        return
    finally:
        try:
            os.remove(partial)
        except OSError:
            pass
    radioid_cache.clear()
    emit_event("user_ids_updated", ok=True)
