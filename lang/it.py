# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Italian interface texts (see en.py for the meaning of the keys)."""

LANGUAGE_NAME = "Italiano"

TEXTS = {
    # Program
    "app.title": "Client OpenGroundnut",
    "update.available": "È disponibile la versione {}.\nAggiorna il programma.",

    # Buttons and words shared by many windows
    "common.ok": "OK",
    "common.cancel": "Annulla",
    "common.yes": "Sì",
    "common.no": "No",
    "common.add": "Aggiungi",
    "common.edit": "Modifica",
    "common.remove": "Rimuovi",
    "common.remove_all": "Rimuovi tutto",
    "common.save": "Salva",
    "common.clear": "Svuota",
    "common.show": "Mostra",
    "common.hide": "Nascondi",
    "common.continue_question": "Vuoi continuare comunque?",

    # Field names
    "field.callsign": "Nominativo",
    "field.name": "Nome",
    "field.date": "Data",
    "field.time": "Ora",
    "field.band": "Banda",
    "field.frequency": "Frequenza",
    "field.comment": "Commento",
    "field.room": "Stanza",
    "field.message": "Messaggio",
    "field.duration": "Durata",

    # Tabs
    "tab.main": "Principale",
    "tab.monitor": "Monitor",
    "tab.settings": "Impostazioni",

    # Header
    "clock.local": "Locale",
    "status.offline": "Non connesso",
    "status.connecting": "Connessione",
    "status.online": "Connesso",
    "status.receiving": "In ricezione",
    "status.transmitting": "In trasmissione",
    "status.scanning": "Scansione",
    "status.reconnecting": "Riconnessione ...",

    # Main tab
    "main.station_heard": "Stazione",
    "main.my_station": "La mia stazione",
    "main.last_heard": "Ultime ascoltate",
    "main.stations_in_room": "Stazioni nella stanza",
    "main.connect": "Connetti",
    "main.disconnect": "Disconnetti",
    "main.cancel_reconnect": "Riconnessione ... (clic per annullare)",
    "main.choose_room": "Scegli prima una stanza.",
    "main.mute_tip": "Silenzia o riattiva l'altoparlante",
    "station.unknown": "Sconosciuto",

    # Rooms and bookmarks
    "rooms.group": "Gruppo",
    "rooms.bookmarks": "PREFERITI",
    "rooms.bookmark_add": "Aggiungi ai preferiti",
    "rooms.bookmark_remove": "Rimuovi dai preferiti",
    "rooms.bookmark_added": "Stanza {} aggiunta ai preferiti",
    "rooms.bookmark_removed": "Stanza {} rimossa dai preferiti",
    "rooms.selected": "Stanza {} scelta",
    "rooms.busy_transmitting": "Termina la trasmissione prima di cambiare stanza.",
    "rooms.reload_tip": "Ricarica gli elenchi di server e stanze",
    "rooms.reloading": "Caricamento degli elenchi di server e stanze ...",

    # Monitor tab
    "monitor.filter": "Filtro",
    "monitor.filter_all": "Tutto",
    "monitor.started": "Inizio",
    "monitor.double_click_hint": "Doppio clic su una riga per entrare nella sua stanza",

    # Room scanner
    "scan.manage": "Stanze da scansionare",
    "scan.available": "Stanze disponibili",
    "scan.selected": "Stanze da scansionare",
    "scan.add_all": "Aggiungi tutte",
    "scan.search_hint": "Scrivi per cercare una stanza",
    "scan.needs_connection": "Connettiti a un server Peanut prima di avviare la scansione.",
    "scan.no_rooms": "Non ci sono stanze da scansionare. Sceglile prima in \"Stanze da scansionare\".",

    # Callsign alarms
    "alarms.title": "Allarmi",
    "alarms.log_title": "Registro allarmi",
    "alarms.state": "Stato",
    "alarms.time_utc": "Ora (UTC)",
    "alarms.online": "connessa",
    "alarms.offline": "non connessa",
    "alarms.toast": "Allarme: {} è {}",

    # Recording
    "rec.save_on_exit": "Salvare la registrazione prima di chiudere?",

    # Logbook
    "logbook.title": "Logbook",
    "logbook.add_title": "Aggiungi al logbook",
    "logbook.edit_title": "Modifica collegamento",
    "logbook.added": "Collegamento aggiunto",
    "logbook.updated": "Collegamento aggiornato",
    "logbook.deleted": "Collegamento eliminato",
    "logbook.all_deleted": "Tutti i collegamenti sono stati eliminati",
    "logbook.clear": "Svuota logbook",
    "logbook.empty": "Il logbook è vuoto.",
    "logbook.select_first": "Seleziona prima un collegamento.",
    "logbook.confirm_save": "Salvare questo collegamento?",
    "logbook.confirm_delete": "Eliminare questo collegamento?",
    "logbook.confirm_delete_all": "Eliminare tutti i collegamenti del logbook?",
    "logbook.duplicate": "{} è già nel logbook:",
    "logbook.date_invalid": "La data non è valida.",
    "logbook.time_invalid": "L'ora non è valida.",
    "logbook.band_invalid": "Inserisci una banda valida.",
    "logbook.frequency_invalid": "Inserisci la frequenza in MHz.",
    "logbook.adif_saved": "File ADIF salvato: {}",
    "logbook.nothing_to_upload": "Tutti i collegamenti del logbook sono già stati caricati.",
    "logbook.confirm_eqsl": "Caricare su eQSL i collegamenti in sospeso?",
    "logbook.confirm_qrz": "Caricare su QRZ.com i collegamenti in sospeso?",
    "logbook.eqsl_not_configured": "Inserisci prima utente e password di eQSL nelle Impostazioni.",
    "logbook.qrz_not_configured": "Inserisci prima la chiave API di QRZ.com Logbook nelle Impostazioni.",
    "logbook.eqsl_uploading": "Caricamento dei collegamenti su eQSL ...",
    "logbook.qrz_uploading": "Caricamento dei collegamenti su QRZ.com ...",
    "logbook.eqsl_answer": "Risposta di eQSL",
    "logbook.qrz_answer": "Risposta di QRZ.com",
    "logbook.eqsl_unreachable": "eQSL non è raggiungibile.",
    "logbook.qrz_record_ok": "{}: caricato (id {})",
    "logbook.qrz_record_failed": "{}: non caricato - {}",
    "logbook.qrz_summary": "{} di {} collegamenti caricati su QRZ.com.",

    # Settings
    "settings.general": "Generale",
    "settings.platforms": "Logbook online",
    "settings.rx_control": "Controllo RX",
    "settings.tx_control": "Controllo TX",
    "settings.auto": "Avvio",
    "settings.access_code": "Codice di accesso",
    "settings.server": "Server",
    "settings.language": "Lingua",
    "settings.scale": "Scala",
    "settings.audio": "Audio",
    "settings.always_on_top": "Sempre in primo piano",
    "settings.roger_beep": "Beep di fine",
    "settings.dmr_id": "ID DMR",
    "settings.dmr_lookup": "Cerca",
    "settings.dmr_lookup_failed": "radioid.net non ha risposto. Puoi scrivere l'ID DMR a mano.",
    "settings.dmr_not_found": "Nessun ID DMR registrato per questo nominativo.",
    "settings.update_radioid": "Aggiorna l'elenco RadioID",
    "settings.message_hint": "Vengono inviati solo i primi 20 caratteri, senza accenti",
    "settings.restart_hint": "Le modifiche di lingua e scala valgono dopo il riavvio.",
    "settings.restart_needed": "Riavvia il programma per applicare le modifiche.",
    "settings.vox_threshold": "Soglia VOX",
    "settings.vox_hang_time": "Ritardo VOX",
    "settings.return_hold": "Pausa di rientro",
    "settings.serial_port": "Porta seriale",
    "settings.tx_timeout": "Tempo massimo TX",
    "settings.ctrl_key_ptt": "Tasto Ctrl come PTT",
    "settings.connect_at_start": "Connetti all'avvio",

    # Online logbook accounts
    "platforms.eqsl": "Account eQSL",
    "platforms.qrz": "Account QRZ.com (abbonamento XML)",
    "platforms.user": "Utente",
    "platforms.password": "Password",
    "platforms.qth_nickname": "Nome del QTH",
    "platforms.qrz_api_key": "Chiave API del logbook",

    # APRS
    "aprs.enable": "Invia la mia posizione APRS",
    "aprs.host": "Server",
    "aprs.port": "Porta",
    "aprs.latitude": "Latitudine",
    "aprs.longitude": "Longitudine",

    # Settings form checks
    "form.callsign_missing": "Inserisci il tuo nominativo.",
    "form.callsign_invalid": "Il nominativo può contenere solo lettere, cifre e \"/\", fino a 8 caratteri.",
    "form.dmr_id_invalid": "L'ID DMR deve essere un numero da 0 a 16777215.",
    "form.scale_invalid": "La scala deve essere un numero intero da 1 a 3.",
    "form.rx_mode_invalid": "Scegli una modalità di controllo RX valida.",
    "form.tx_mode_invalid": "Scegli una modalità di controllo TX valida.",
    "form.rx_port_missing": "Scegli la porta seriale del controllo RX.",
    "form.tx_port_missing": "Scegli la porta seriale del controllo TX.",
    "form.vox_invalid": "Un valore del VOX è fuori intervallo.",
    "form.tx_timeout_invalid": "Il tempo massimo TX deve essere tra 30 e 300 secondi.",
    "form.auto_room_missing": "Scegli la stanza a cui connettersi all'avvio.",
    "form.aprs_host_invalid": "Inserisci il server APRS-IS.",
    "form.aprs_port_invalid": "La porta APRS deve essere un numero da 1 a 65535.",
    "form.aprs_latitude_invalid": "La latitudine deve essere un numero decimale da -90 a 90.",
    "form.aprs_longitude_invalid": "La longitudine deve essere un numero decimale da -180 a 180.",

    # Logging in to the Peanut network
    "login.setup_required": (
        "Inserisci il tuo nominativo e il codice di accesso Peanut nelle Impostazioni, poi premi Salva.\n"
        "I codici di accesso si ottengono su www.pa7lim.nl/peanut"
    ),
    "login.wrong_code": "Il codice di accesso non corrisponde al nominativo. I codici si ottengono su www.pa7lim.nl/peanut",
    "login.server_unreachable": "Il server {} non è raggiungibile:\n{}",
    "login.refused": "La rete Peanut ha rifiutato l'accesso.\nMotivo: {}",
    "login.reason_incorrect": "nominativo o codice non accettato",
    "login.reason_user_code": "codice di accesso errato",
    "login.reason_upgrade": "questa versione del programma non è più accettata",
    "login.reason_unknown": "sconosciuto",

    # Serial ports
    "serial.port_unavailable": "La porta {0} non esiste o è usata da un altro programma.",
    "serial.rescan_tip": "Cerca di nuovo le porte seriali",

    # Audio
    "audio.title": "Audio",
    "audio.input": "Ingresso",
    "audio.output": "Uscita",
    "audio.rescan_tip": "Cerca di nuovo i dispositivi audio",
    "audio.input_failed": "Il dispositivo audio di ingresso non è utilizzabile:\n{}",
    "audio.output_failed": "Il dispositivo audio di uscita non è utilizzabile, quindi la connessione è stata chiusa:\n{}\n\nScegli un altro dispositivo nelle Impostazioni.",
    "audio.device_fallback": "Il dispositivo audio {} non è disponibile; si usa quello predefinito del sistema.",
    "audio.unavailable": "Impossibile avviare il sistema audio, quindi la stazione non può connettersi.\nControlla i dispositivi audio e riavvia il programma.",

    # RadioID user list
    "radioid.updated": "L'elenco RadioID è stato aggiornato",
    "radioid.invalid_file": "Il file scaricato non è un elenco utenti RadioID.",
    "radioid.download_failed": "Impossibile scaricare l'elenco utenti RadioID:\n{}",

    # Stored files
    "storage.value_invalid": "[{}] {} = {} non è valido; si usa il valore predefinito.",
    "storage.settings_unreadable": "Impossibile leggere il file delle impostazioni, quindi si usano quelle predefinite. Una copia è stata salvata come {}.",
    "storage.file_unreadable": "Impossibile leggere {}, quindi se ne usa uno vuoto. Una copia è stata salvata come {}.",
}
