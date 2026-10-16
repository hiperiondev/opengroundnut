# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Event channel between the application core and any user interface.

The core modules (network, audio, database, callsign, settings and core)
never talk to a window, a widget or a dialog. When something happens that a
user may want to see, they publish a named event with plain Python data:

    emit_event("audio_level", level=42)
    emit_event("error", title="Error", message="The port is busy")

A user interface subscribes once with set_event_listener() and decides on its
own how (and whether) to show each event. Without a listener the program still
runs: errors and notices are written to the log and the rest is ignored.

Events can be published from any thread. The listener is called on the thread
that published the event, so a listener that drives a toolkit with a single
UI thread must hand the work over to that thread itself.

Events published by the core
----------------------------
servers_loaded       names (list of str), current (master address in use)
rooms_loaded         countries (sorted list of str), initial (bool)
connecting           (no data) the login was sent and the server has not answered yet
connection_changed   connected (bool): True once the server accepted the login,
                     False when the connection ends
reconnecting         (no data) the server stopped answering, a reconnect is pending
ptt_state            status (0 idle, 1 receiving, 2 transmitting), caption (str), enabled (bool)
audio_level          level (int, 0-327) RMS level of the audio being sent or received
transmission_logged  time (HH:MM:SS), callsign, name, duration (MM:SS or H:MM:SS)
station_photo        callsign, picture (path of the picture file, or None), name
station_identity     identity (DMR id), name, location
online_stations      callsigns (list of str) connected to the active room
alarms_updated       lines (list of tab separated "call, state, time, room" rows, newest first)
scan_state           active (bool)
scan_room            room (str) the scanner has just entered (or returned to)
dmr_ids              ids (list of str, empty when none was found, or None when no callsign
                     was given); not published when radioid.net did not answer (a
                     "warning" is published instead)
user_ids_updated     ok (bool) the RadioID user file download finished
eqsl_reply           text (str) answer returned by eQSL.cc
qrz_reply            text (str) summary of a QRZ.com logbook upload
info                 title, message
warning              title, message
error                title, message
setup_required       title, message: the callsign or the access code is not set yet,
                     so the station cannot connect until they are entered in Settings
login_refused        title, message, reason (int: 1 incorrect, 2 wrong access code,
                     3 client must be upgraded, 0 or other unknown): the server refused
                     the login and the station was disconnected
fatal_error          title, message: the application cannot go on and is shutting down
"""

import logging

_event_listener = None

_event_log = logging.getLogger("peanut")

# Events that must never be lost silently when no interface is listening.
_CONSOLE_EVENTS = ("info", "warning", "error", "setup_required", "login_refused", "fatal_error")


def set_event_listener(listener):
    """Register the function that receives every event, or None to remove it.

    The listener is called as listener(event_name, **data). Some events carry
    a "name" field, so the listener must take the event name positionally,
    for example: def listener(event_name, /, **data).
    """
    global _event_listener
    _event_listener = listener


def emit_event(event_name, /, **data):
    """Publish an event to the registered listener.

    A failing listener is written to the log but never breaks the core code
    that published the event.
    """
    listener = _event_listener
    if listener is None:
        if event_name in _CONSOLE_EVENTS:
            level = logging.INFO if event_name == "info" else logging.WARNING
            if event_name in ("error", "login_refused", "fatal_error"):
                level = logging.ERROR
            _event_log.log(level, "%s: %s", data.get("title", ""), data.get("message", ""))
        return None
    try:
        return listener(event_name, **data)
    except Exception:
        _event_log.exception("Event listener failed on %r", event_name)
        return None
