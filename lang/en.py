# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""English interface texts.

This is the reference translation: it defines every key, and any key missing
from another language falls back to the text written here. Keys are grouped
by the part of the program that uses them; "{}" marks a value filled in by
the program and must be kept in every translation.
"""

LANGUAGE_NAME = "English"

TEXTS = {
    # Program
    "app.title": "OpenGroundnut client",
    "update.available": "Version {} is available.\nPlease update the program.",

    # Buttons and words shared by many windows
    "common.ok": "OK",
    "common.cancel": "Cancel",
    "common.yes": "Yes",
    "common.no": "No",
    "common.add": "Add",
    "common.edit": "Edit",
    "common.remove": "Remove",
    "common.remove_all": "Remove all",
    "common.save": "Save",
    "common.clear": "Clear",
    "common.show": "Show",
    "common.hide": "Hide",
    "common.continue_question": "Do you want to continue?",

    # Field names
    "field.callsign": "Callsign",
    "field.name": "Name",
    "field.date": "Date",
    "field.time": "Time",
    "field.band": "Band",
    "field.frequency": "Frequency",
    "field.comment": "Comment",
    "field.room": "Room",
    "field.message": "Message",
    "field.duration": "Duration",

    # Tabs
    "tab.main": "Main",
    "tab.monitor": "Monitor",
    "tab.settings": "Settings",

    # Header
    "clock.local": "Local",
    "status.offline": "Offline",
    "status.connecting": "Connecting",
    "status.online": "Online",
    "status.receiving": "Receiving",
    "status.transmitting": "Transmitting",
    "status.scanning": "Scanning",
    "status.reconnecting": "Reconnecting ...",

    # Main tab
    "main.station_heard": "Station",
    "main.my_station": "My station",
    "main.last_heard": "Last heard",
    "main.stations_in_room": "Stations in the room",
    "main.connect": "Connect",
    "main.disconnect": "Disconnect",
    "main.cancel_reconnect": "Reconnecting ... (click to cancel)",
    "main.choose_room": "Choose a room first.",
    "main.mute_tip": "Mute or unmute the speaker",
    "station.unknown": "Unknown",

    # Rooms and bookmarks
    "rooms.group": "Group",
    "rooms.bookmarks": "BOOKMARKS",
    "rooms.bookmark_add": "Add to bookmarks",
    "rooms.bookmark_remove": "Remove from bookmarks",
    "rooms.bookmark_added": "Room {} added to the bookmarks",
    "rooms.bookmark_removed": "Room {} removed from the bookmarks",
    "rooms.selected": "Room {} selected",
    "rooms.busy_transmitting": "Finish your transmission before changing rooms.",
    "rooms.reload_tip": "Load the server and room lists again",
    "rooms.reloading": "Loading the server and room lists ...",

    # Monitor tab
    "monitor.filter": "Filter",
    "monitor.filter_all": "All",
    "monitor.started": "Started",
    "monitor.double_click_hint": "Double-click a row to enter its room",

    # Room scanner
    "scan.manage": "Scan rooms",
    "scan.available": "Available rooms",
    "scan.selected": "Rooms to scan",
    "scan.add_all": "Add all",
    "scan.search_hint": "Type to search for a room",
    "scan.needs_connection": "Connect to a Peanut server before starting the scan.",
    "scan.no_rooms": "There are no rooms to scan. Add some with \"Scan rooms\" first.",

    # Callsign alarms
    "alarms.title": "Alarms",
    "alarms.log_title": "Alarm log",
    "alarms.state": "State",
    "alarms.time_utc": "Time (UTC)",
    "alarms.online": "online",
    "alarms.offline": "offline",
    "alarms.toast": "Alarm: {} is {}",

    # Recording
    "rec.save_on_exit": "Save the recording before closing?",

    # Logbook
    "logbook.title": "Logbook",
    "logbook.add_title": "Add to the logbook",
    "logbook.edit_title": "Edit contact",
    "logbook.added": "Contact added",
    "logbook.updated": "Contact updated",
    "logbook.deleted": "Contact deleted",
    "logbook.all_deleted": "Every contact was deleted",
    "logbook.clear": "Clear logbook",
    "logbook.empty": "The logbook is empty.",
    "logbook.select_first": "Select a contact first.",
    "logbook.confirm_save": "Save this contact?",
    "logbook.confirm_delete": "Delete this contact?",
    "logbook.confirm_delete_all": "Delete every contact in the logbook?",
    "logbook.duplicate": "{} is already in the logbook:",
    "logbook.date_invalid": "The date is not valid.",
    "logbook.time_invalid": "The time is not valid.",
    "logbook.band_invalid": "Enter a valid band.",
    "logbook.frequency_invalid": "Enter the frequency in MHz.",
    "logbook.adif_saved": "ADIF file saved: {}",
    "logbook.nothing_to_upload": "Every contact in the logbook has already been uploaded.",
    "logbook.confirm_eqsl": "Upload the pending contacts to eQSL?",
    "logbook.confirm_qrz": "Upload the pending contacts to QRZ.com?",
    "logbook.eqsl_not_configured": "Enter your eQSL user name and password in Settings first.",
    "logbook.qrz_not_configured": "Enter your QRZ.com Logbook API key in Settings first.",
    "logbook.eqsl_uploading": "Uploading the contacts to eQSL ...",
    "logbook.qrz_uploading": "Uploading the contacts to QRZ.com ...",
    "logbook.eqsl_answer": "eQSL answer",
    "logbook.qrz_answer": "QRZ.com answer",
    "logbook.eqsl_unreachable": "eQSL cannot be reached.",
    "logbook.qrz_record_ok": "{}: uploaded (log id {})",
    "logbook.qrz_record_failed": "{}: not uploaded - {}",
    "logbook.qrz_summary": "{} of {} contacts uploaded to QRZ.com.",

    # Settings
    "settings.general": "General",
    "settings.platforms": "Online logbooks",
    "settings.rx_control": "RX control",
    "settings.tx_control": "TX control",
    "settings.auto": "Startup",
    "settings.access_code": "Access code",
    "settings.server": "Server",
    "settings.language": "Language",
    "settings.scale": "Scale",
    "settings.audio": "Audio",
    "settings.always_on_top": "Always on top",
    "settings.roger_beep": "Roger beep",
    "settings.dmr_id": "DMR ID",
    "settings.dmr_lookup": "Look up",
    "settings.dmr_lookup_failed": "radioid.net did not answer. You can type the DMR ID yourself.",
    "settings.dmr_not_found": "No DMR ID is registered for this callsign.",
    "settings.update_radioid": "Update the RadioID list",
    "settings.message_hint": "Only the first 20 characters are sent, without accents",
    "settings.restart_hint": "Language and scale changes take effect after a restart.",
    "settings.restart_needed": "Restart the program to apply the changes.",
    "settings.vox_threshold": "VOX threshold",
    "settings.vox_hang_time": "VOX hang time",
    "settings.return_hold": "Return hold",
    "settings.serial_port": "Serial port",
    "settings.tx_timeout": "TX time-out",
    "settings.ctrl_key_ptt": "Ctrl key as PTT",
    "settings.connect_at_start": "Connect at startup",

    # Online logbook accounts
    "platforms.eqsl": "eQSL account",
    "platforms.qrz": "QRZ.com account (XML subscription)",
    "platforms.user": "User name",
    "platforms.password": "Password",
    "platforms.qth_nickname": "QTH nickname",
    "platforms.qrz_api_key": "Logbook API key",

    # APRS
    "aprs.enable": "Send my APRS position",
    "aprs.host": "Server",
    "aprs.port": "Port",
    "aprs.latitude": "Latitude",
    "aprs.longitude": "Longitude",

    # Settings form checks
    "form.callsign_missing": "Enter your callsign.",
    "form.callsign_invalid": "A callsign may only hold letters, digits and \"/\", up to 8 characters.",
    "form.dmr_id_invalid": "The DMR ID must be a number from 0 to 16777215.",
    "form.scale_invalid": "The scale must be a whole number from 1 to 3.",
    "form.rx_mode_invalid": "Choose a valid RX control mode.",
    "form.tx_mode_invalid": "Choose a valid TX control mode.",
    "form.rx_port_missing": "Choose the serial port for RX control.",
    "form.tx_port_missing": "Choose the serial port for TX control.",
    "form.vox_invalid": "A VOX value is out of range.",
    "form.tx_timeout_invalid": "The TX time-out must be between 30 and 300 seconds.",
    "form.auto_room_missing": "Choose the room to connect to at startup.",
    "form.aprs_host_invalid": "Enter the APRS-IS server.",
    "form.aprs_port_invalid": "The APRS port must be a number from 1 to 65535.",
    "form.aprs_latitude_invalid": "The latitude must be a decimal number from -90 to 90.",
    "form.aprs_longitude_invalid": "The longitude must be a decimal number from -180 to 180.",

    # Logging in to the Peanut network
    "login.setup_required": (
        "Enter your callsign and its Peanut access code in Settings, then press Save.\n"
        "Access codes are issued at www.pa7lim.nl/peanut"
    ),
    "login.wrong_code": "The access code does not match the callsign. Access codes are issued at www.pa7lim.nl/peanut",
    "login.server_unreachable": "The server {} cannot be reached:\n{}",
    "login.refused": "The Peanut network refused the login.\nReason: {}",
    "login.reason_incorrect": "callsign or code not accepted",
    "login.reason_user_code": "wrong access code",
    "login.reason_upgrade": "this program version is no longer accepted",
    "login.reason_unknown": "unknown",

    # Serial ports
    "serial.port_unavailable": "The port {0} does not exist or is in use by another program.",
    "serial.rescan_tip": "Look for serial ports again",

    # Audio
    "audio.title": "Audio",
    "audio.input": "Input",
    "audio.output": "Output",
    "audio.rescan_tip": "Look for audio devices again",
    "audio.input_failed": "The input audio device cannot be used:\n{}",
    "audio.output_failed": "The output audio device cannot be used, so the connection was closed:\n{}\n\nChoose another device in Settings.",
    "audio.device_fallback": "The audio device {} is not available; the system default device is used.",
    "audio.unavailable": "The sound system cannot be started, so the station cannot connect.\nCheck the audio devices and restart the program.",

    # RadioID user list
    "radioid.updated": "The RadioID list was updated",
    "radioid.invalid_file": "The downloaded file is not a RadioID user list.",
    "radioid.download_failed": "The RadioID user list could not be downloaded:\n{}",

    # Stored files
    "storage.value_invalid": "[{}] {} = {} is not valid; the default value is used.",
    "storage.settings_unreadable": "The settings file could not be read, so the default settings are used. A copy was kept as {}.",
    "storage.file_unreadable": "{} could not be read, so an empty one is used. A copy was kept as {}.",
}
