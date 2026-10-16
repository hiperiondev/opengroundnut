# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""German interface texts (see en.py for the meaning of the keys)."""

LANGUAGE_NAME = "Deutsch"

TEXTS = {
    # Program
    "app.title": "OpenGroundnut-Client",
    "update.available": "Version {} ist verfügbar.\nBitte das Programm aktualisieren.",

    # Buttons and words shared by many windows
    "common.ok": "OK",
    "common.cancel": "Abbrechen",
    "common.yes": "Ja",
    "common.no": "Nein",
    "common.add": "Hinzufügen",
    "common.edit": "Bearbeiten",
    "common.remove": "Entfernen",
    "common.remove_all": "Alle entfernen",
    "common.save": "Speichern",
    "common.clear": "Leeren",
    "common.show": "Anzeigen",
    "common.hide": "Verbergen",
    "common.continue_question": "Trotzdem fortfahren?",

    # Field names
    "field.callsign": "Rufzeichen",
    "field.name": "Name",
    "field.date": "Datum",
    "field.time": "Uhrzeit",
    "field.band": "Band",
    "field.frequency": "Frequenz",
    "field.comment": "Kommentar",
    "field.room": "Raum",
    "field.message": "Nachricht",
    "field.duration": "Dauer",

    # Tabs
    "tab.main": "Start",
    "tab.monitor": "Monitor",
    "tab.settings": "Einstellungen",

    # Header
    "clock.local": "Lokal",
    "status.offline": "Offline",
    "status.connecting": "Verbinde",
    "status.online": "Online",
    "status.receiving": "Empfang",
    "status.transmitting": "Senden",
    "status.scanning": "Suchlauf",
    "status.reconnecting": "Verbinde neu ...",

    # Main tab
    "main.station_heard": "Station",
    "main.my_station": "Meine Station",
    "main.last_heard": "Zuletzt gehört",
    "main.stations_in_room": "Stationen im Raum",
    "main.connect": "Verbinden",
    "main.disconnect": "Trennen",
    "main.cancel_reconnect": "Verbinde neu ... (klicken zum Abbrechen)",
    "main.choose_room": "Bitte zuerst einen Raum wählen.",
    "main.mute_tip": "Lautsprecher stumm schalten oder wieder einschalten",
    "station.unknown": "Unbekannt",

    # Rooms and bookmarks
    "rooms.group": "Gruppe",
    "rooms.bookmarks": "FAVORITEN",
    "rooms.bookmark_add": "Zu Favoriten hinzufügen",
    "rooms.bookmark_remove": "Aus Favoriten entfernen",
    "rooms.bookmark_added": "Raum {} zu den Favoriten hinzugefügt",
    "rooms.bookmark_removed": "Raum {} aus den Favoriten entfernt",
    "rooms.selected": "Raum {} gewählt",
    "rooms.busy_transmitting": "Bitte erst die Sendung beenden, dann den Raum wechseln.",
    "rooms.reload_tip": "Server- und Raumlisten neu laden",
    "rooms.reloading": "Server- und Raumlisten werden geladen ...",

    # Monitor tab
    "monitor.filter": "Filter",
    "monitor.filter_all": "Alle",
    "monitor.started": "Beginn",
    "monitor.double_click_hint": "Doppelklick auf eine Zeile betritt ihren Raum",

    # Room scanner
    "scan.manage": "Suchlauf-Räume",
    "scan.available": "Verfügbare Räume",
    "scan.selected": "Räume im Suchlauf",
    "scan.add_all": "Alle hinzufügen",
    "scan.search_hint": "Tippen, um einen Raum zu suchen",
    "scan.needs_connection": "Vor dem Suchlauf mit einem Peanut-Server verbinden.",
    "scan.no_rooms": "Keine Räume für den Suchlauf. Zuerst unter \"Suchlauf-Räume\" wählen.",

    # Callsign alarms
    "alarms.title": "Alarme",
    "alarms.log_title": "Alarmprotokoll",
    "alarms.state": "Status",
    "alarms.time_utc": "Zeit (UTC)",
    "alarms.online": "online",
    "alarms.offline": "offline",
    "alarms.toast": "Alarm: {} ist {}",

    # Recording
    "rec.save_on_exit": "Aufnahme vor dem Beenden speichern?",

    # Logbook
    "logbook.title": "Logbuch",
    "logbook.add_title": "Ins Logbuch eintragen",
    "logbook.edit_title": "Verbindung bearbeiten",
    "logbook.added": "Verbindung eingetragen",
    "logbook.updated": "Verbindung geändert",
    "logbook.deleted": "Verbindung gelöscht",
    "logbook.all_deleted": "Alle Verbindungen wurden gelöscht",
    "logbook.clear": "Logbuch leeren",
    "logbook.empty": "Das Logbuch ist leer.",
    "logbook.select_first": "Bitte zuerst eine Verbindung auswählen.",
    "logbook.confirm_save": "Diese Verbindung speichern?",
    "logbook.confirm_delete": "Diese Verbindung löschen?",
    "logbook.confirm_delete_all": "Alle Verbindungen im Logbuch löschen?",
    "logbook.duplicate": "{} steht bereits im Logbuch:",
    "logbook.date_invalid": "Das Datum ist ungültig.",
    "logbook.time_invalid": "Die Uhrzeit ist ungültig.",
    "logbook.band_invalid": "Bitte ein gültiges Band angeben.",
    "logbook.frequency_invalid": "Bitte die Frequenz in MHz angeben.",
    "logbook.adif_saved": "ADIF-Datei gespeichert: {}",
    "logbook.nothing_to_upload": "Alle Verbindungen im Logbuch wurden bereits hochgeladen.",
    "logbook.confirm_eqsl": "Offene Verbindungen zu eQSL hochladen?",
    "logbook.confirm_qrz": "Offene Verbindungen zu QRZ.com hochladen?",
    "logbook.eqsl_not_configured": "Bitte zuerst eQSL-Benutzername und -Passwort in den Einstellungen eintragen.",
    "logbook.qrz_not_configured": "Bitte zuerst den QRZ.com-Logbook-API-Schlüssel in den Einstellungen eintragen.",
    "logbook.eqsl_uploading": "Verbindungen werden zu eQSL hochgeladen ...",
    "logbook.qrz_uploading": "Verbindungen werden zu QRZ.com hochgeladen ...",
    "logbook.eqsl_answer": "Antwort von eQSL",
    "logbook.qrz_answer": "Antwort von QRZ.com",
    "logbook.eqsl_unreachable": "eQSL ist nicht erreichbar.",
    "logbook.qrz_record_ok": "{}: hochgeladen (Log-ID {})",
    "logbook.qrz_record_failed": "{}: nicht hochgeladen - {}",
    "logbook.qrz_summary": "{} von {} Verbindungen zu QRZ.com hochgeladen.",

    # Settings
    "settings.general": "Allgemein",
    "settings.platforms": "Online-Logbücher",
    "settings.rx_control": "RX-Steuerung",
    "settings.tx_control": "TX-Steuerung",
    "settings.auto": "Programmstart",
    "settings.access_code": "Zugangscode",
    "settings.server": "Server",
    "settings.language": "Sprache",
    "settings.scale": "Skalierung",
    "settings.audio": "Audio",
    "settings.always_on_top": "Immer im Vordergrund",
    "settings.roger_beep": "Roger-Piep",
    "settings.dmr_id": "DMR-ID",
    "settings.dmr_lookup": "Suchen",
    "settings.dmr_lookup_failed": "radioid.net antwortet nicht. Die DMR-ID kann auch von Hand eingegeben werden.",
    "settings.dmr_not_found": "Für dieses Rufzeichen ist keine DMR-ID registriert.",
    "settings.update_radioid": "RadioID-Liste aktualisieren",
    "settings.message_hint": "Nur die ersten 20 Zeichen werden gesendet, ohne Akzente",
    "settings.restart_hint": "Sprache und Skalierung gelten nach einem Neustart.",
    "settings.restart_needed": "Bitte das Programm neu starten, um die Änderungen zu übernehmen.",
    "settings.vox_threshold": "VOX-Schwelle",
    "settings.vox_hang_time": "VOX-Haltezeit",
    "settings.return_hold": "Rückschaltpause",
    "settings.serial_port": "Serielle Schnittstelle",
    "settings.tx_timeout": "Max. Sendezeit",
    "settings.ctrl_key_ptt": "Strg-Taste als PTT",
    "settings.connect_at_start": "Beim Start verbinden",

    # Online logbook accounts
    "platforms.eqsl": "eQSL-Konto",
    "platforms.qrz": "QRZ.com-Konto (XML-Abonnement)",
    "platforms.user": "Benutzername",
    "platforms.password": "Passwort",
    "platforms.qth_nickname": "QTH-Kurzname",
    "platforms.qrz_api_key": "Logbook-API-Schlüssel",

    # APRS
    "aprs.enable": "Meine APRS-Position senden",
    "aprs.host": "Server",
    "aprs.port": "Port",
    "aprs.latitude": "Breite",
    "aprs.longitude": "Länge",

    # Settings form checks
    "form.callsign_missing": "Bitte das Rufzeichen eingeben.",
    "form.callsign_invalid": "Ein Rufzeichen darf nur Buchstaben, Ziffern und \"/\" enthalten, höchstens 8 Zeichen.",
    "form.dmr_id_invalid": "Die DMR-ID muss eine Zahl von 0 bis 16777215 sein.",
    "form.scale_invalid": "Die Skalierung muss eine ganze Zahl von 1 bis 3 sein.",
    "form.rx_mode_invalid": "Bitte eine gültige RX-Steuerung wählen.",
    "form.tx_mode_invalid": "Bitte eine gültige TX-Steuerung wählen.",
    "form.rx_port_missing": "Bitte die serielle Schnittstelle der RX-Steuerung wählen.",
    "form.tx_port_missing": "Bitte die serielle Schnittstelle der TX-Steuerung wählen.",
    "form.vox_invalid": "Ein VOX-Wert liegt außerhalb des gültigen Bereichs.",
    "form.tx_timeout_invalid": "Die max. Sendezeit muss zwischen 30 und 300 Sekunden liegen.",
    "form.auto_room_missing": "Bitte den Raum für die Verbindung beim Start wählen.",
    "form.aprs_host_invalid": "Bitte den APRS-IS-Server eingeben.",
    "form.aprs_port_invalid": "Der APRS-Port muss eine Zahl von 1 bis 65535 sein.",
    "form.aprs_latitude_invalid": "Die Breite muss eine Dezimalzahl von -90 bis 90 sein.",
    "form.aprs_longitude_invalid": "Die Länge muss eine Dezimalzahl von -180 bis 180 sein.",

    # Logging in to the Peanut network
    "login.setup_required": (
        "Bitte Rufzeichen und Peanut-Zugangscode in den Einstellungen eintragen und Speichern drücken.\n"
        "Zugangscodes gibt es unter www.pa7lim.nl/peanut"
    ),
    "login.wrong_code": "Der Zugangscode passt nicht zum Rufzeichen. Zugangscodes gibt es unter www.pa7lim.nl/peanut",
    "login.server_unreachable": "Der Server {} ist nicht erreichbar:\n{}",
    "login.refused": "Das Peanut-Netz hat die Anmeldung abgelehnt.\nGrund: {}",
    "login.reason_incorrect": "Rufzeichen oder Code nicht akzeptiert",
    "login.reason_user_code": "falscher Zugangscode",
    "login.reason_upgrade": "diese Programmversion wird nicht mehr akzeptiert",
    "login.reason_unknown": "unbekannt",

    # Serial ports
    "serial.port_unavailable": "Die Schnittstelle {0} existiert nicht oder wird von einem anderen Programm benutzt.",
    "serial.rescan_tip": "Serielle Schnittstellen erneut suchen",

    # Audio
    "audio.title": "Audio",
    "audio.input": "Eingang",
    "audio.output": "Ausgang",
    "audio.rescan_tip": "Audiogeräte erneut suchen",
    "audio.input_failed": "Das Audio-Eingabegerät ist nicht nutzbar:\n{}",
    "audio.output_failed": "Das Audio-Ausgabegerät ist nicht nutzbar, daher wurde die Verbindung getrennt:\n{}\n\nBitte in den Einstellungen ein anderes Gerät wählen.",
    "audio.device_fallback": "Das Audiogerät {} ist nicht verfügbar; das Standardgerät des Systems wird verwendet.",
    "audio.unavailable": "Das Audiosystem lässt sich nicht starten, daher kann die Station nicht verbinden.\nBitte die Audiogeräte prüfen und das Programm neu starten.",

    # RadioID user list
    "radioid.updated": "Die RadioID-Liste wurde aktualisiert",
    "radioid.invalid_file": "Die heruntergeladene Datei ist keine RadioID-Benutzerliste.",
    "radioid.download_failed": "Die RadioID-Benutzerliste konnte nicht heruntergeladen werden:\n{}",

    # Stored files
    "storage.value_invalid": "[{}] {} = {} ist ungültig; der Standardwert wird verwendet.",
    "storage.settings_unreadable": "Die Einstellungsdatei ist nicht lesbar, daher gelten die Standardeinstellungen. Eine Kopie liegt unter {}.",
    "storage.file_unreadable": "{} ist nicht lesbar, daher wird eine leere Datei verwendet. Eine Kopie liegt unter {}.",
}
