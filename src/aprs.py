# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""APRS position beacon sent to APRS-IS when the station transmits (at most every 30 minutes)."""

# Shortest time between two position beacons, in seconds.
APRS_BEACON_INTERVAL = 1800.0

# SSID added to the callsign in the beacon (the station's own SSID is replaced).
# In the APRS SSID recommendations -10 marks stations linked through the
# Internet (IRLP, EchoLink, Winlink and similar), which is what a Peanut
# station is.
APRS_SSID = "-10"

# Destination field of the packets. APRS asks every program to use its own
# "tocall"; APZ... is the block reserved for experimental software.
APRS_TOCALL = "APZPNT"

# Text added after the position.
APRS_COMMENT = "via " + APP_NAME

# Prevents two beacons from being sent at the same time by quick PTT presses.
_aprs_lock = threading.Lock()


def _aprs_settings():
    """(host, port, latitude, longitude) from the saved configuration, or None when unusable."""
    try:
        host = config.get("aprs", "host", fallback="").strip()
        port_number = config.getint("aprs", "port", fallback=14580)
        latitude = config.getfloat("aprs", "latitude", fallback=None)
        longitude = config.getfloat("aprs", "longitude", fallback=None)
    except (AttributeError, TypeError, ValueError) as exc:
        log.warning("APRS settings are not valid: %s", exc)
        return None
    if len(host) < 4 or not 1 <= port_number <= 65535:
        log.warning("APRS host or port is not valid; no beacon is sent.")
        return None
    if latitude is None or longitude is None or not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
        log.warning("APRS position is not valid; no beacon is sent.")
        return None
    return (host, port_number, latitude, longitude)


def aprs_send_thread():
    """Send our position to APRS-IS when the last beacon is old enough."""
    global last_aprs_beacon
    if not _aprs_lock.acquire(blocking=False):
        return
    try:
        if monotonic() - last_aprs_beacon < APRS_BEACON_INTERVAL and last_aprs_beacon:
            return
        settings = _aprs_settings()
        if settings is None:
            return
        host, port_number, latitude, longitude = settings
        packet = aprs_string(my_call, latitude, longitude, APRS_SSID)
        if packet and send_aprs(packet, host, my_call, port_number):
            last_aprs_beacon = monotonic()
    finally:
        _aprs_lock.release()


def aprs_string(call, latitude, longitude, ssid):
    """APRS position packet with a timestamp, or "" when the callsign or position is not usable."""
    base_call = clean_callsign(str(call).split("-")[0])
    if len(base_call) < 3:
        return ""
    if not (-90.0 <= float(latitude) <= 90.0 and -180.0 <= float(longitude) <= 180.0):
        return ""
    timestamp = datetime.now(timezone.utc).strftime("%d%H%M")
    lat = aprslib.util.latitude_to_ddm(float(latitude))
    lon = aprslib.util.longitude_to_ddm(float(longitude))
    symbol_table = "/"
    symbol = "-"
    return "{}{}>{},TCPIP*:@{}z{}{}{}{}{}".format(
        base_call, ssid, APRS_TOCALL, timestamp, lat, symbol_table, lon, symbol, APRS_COMMENT
    )


def send_aprs(aprs_packet, aprs_server, aprs_user, aprs_port):
    """Log in to an APRS-IS server, send one packet and log out. Returns True on success."""
    login_call = clean_callsign(str(aprs_user).split("-")[0])
    passcode = str(aprslib.passcode(login_call))
    connection = aprslib.IS(login_call, host=aprs_server, passwd=passcode, port=aprs_port)
    try:
        connection.connect()
        connection.sendall(aprs_packet)
        log.info("APRS position sent to %s:%s", aprs_server, aprs_port)
        return True
    except Exception as exc:
        log.warning("APRS beacon failed: %s", exc)
        return False
    finally:
        try:
            connection.close()
        except Exception:
            pass
