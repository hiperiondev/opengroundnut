# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Spanish interface texts (see en.py for the meaning of the keys)."""

LANGUAGE_NAME = "Español"

TEXTS = {
    # Program
    "app.title": "Cliente OpenGroundnut",
    "update.available": "La versión {} ya está disponible.\nActualice el programa.",

    # Buttons and words shared by many windows
    "common.ok": "Aceptar",
    "common.cancel": "Cancelar",
    "common.yes": "Sí",
    "common.no": "No",
    "common.add": "Añadir",
    "common.edit": "Modificar",
    "common.remove": "Quitar",
    "common.remove_all": "Quitar todo",
    "common.save": "Guardar",
    "common.clear": "Vaciar",
    "common.show": "Ver",
    "common.hide": "Ocultar",
    "common.continue_question": "¿Continuar de todos modos?",

    # Field names
    "field.callsign": "Indicativo",
    "field.name": "Nombre",
    "field.date": "Fecha",
    "field.time": "Hora",
    "field.band": "Banda",
    "field.frequency": "Frecuencia",
    "field.comment": "Comentario",
    "field.room": "Sala",
    "field.message": "Mensaje",
    "field.duration": "Duración",

    # Tabs
    "tab.main": "Inicio",
    "tab.monitor": "Monitor",
    "tab.settings": "Ajustes",

    # Header
    "clock.local": "Local",
    "status.offline": "Sin conexión",
    "status.connecting": "Conectando",
    "status.online": "En línea",
    "status.receiving": "Recibiendo",
    "status.transmitting": "Transmitiendo",
    "status.scanning": "Explorando",
    "status.reconnecting": "Reconectando ...",

    # Main tab
    "main.station_heard": "Estación",
    "main.my_station": "Mi estación",
    "main.last_heard": "Últimas escuchadas",
    "main.stations_in_room": "Estaciones en la sala",
    "main.connect": "Conectar",
    "main.disconnect": "Desconectar",
    "main.cancel_reconnect": "Reconectando ... (pulse para cancelar)",
    "main.choose_room": "Elija primero una sala.",
    "main.mute_tip": "Silenciar o activar el altavoz",
    "station.unknown": "Desconocido",

    # Rooms and bookmarks
    "rooms.group": "Grupo",
    "rooms.bookmarks": "MARCADORES",
    "rooms.bookmark_add": "Añadir a marcadores",
    "rooms.bookmark_remove": "Quitar de marcadores",
    "rooms.bookmark_added": "Sala {} añadida a los marcadores",
    "rooms.bookmark_removed": "Sala {} quitada de los marcadores",
    "rooms.selected": "Sala {} elegida",
    "rooms.busy_transmitting": "Termine la transmisión antes de cambiar de sala.",
    "rooms.reload_tip": "Volver a cargar las listas de servidores y salas",
    "rooms.reloading": "Cargando las listas de servidores y salas ...",

    # Monitor tab
    "monitor.filter": "Filtro",
    "monitor.filter_all": "Todo",
    "monitor.started": "Inicio",
    "monitor.double_click_hint": "Doble clic en una fila para entrar en su sala",

    # Room scanner
    "scan.manage": "Salas a explorar",
    "scan.available": "Salas disponibles",
    "scan.selected": "Salas a explorar",
    "scan.add_all": "Añadir todas",
    "scan.search_hint": "Escriba para buscar una sala",
    "scan.needs_connection": "Conéctese a un servidor Peanut antes de iniciar la exploración.",
    "scan.no_rooms": "No hay salas para explorar. Elíjalas antes en \"Salas a explorar\".",

    # Callsign alarms
    "alarms.title": "Alarmas",
    "alarms.log_title": "Historial de alarmas",
    "alarms.state": "Estado",
    "alarms.time_utc": "Hora (UTC)",
    "alarms.online": "en línea",
    "alarms.offline": "sin conexión",
    "alarms.toast": "Alarma: {} está {}",

    # Recording
    "rec.save_on_exit": "¿Guardar la grabación antes de cerrar?",

    # Logbook
    "logbook.title": "Libro de guardia",
    "logbook.add_title": "Añadir al libro de guardia",
    "logbook.edit_title": "Modificar contacto",
    "logbook.added": "Contacto añadido",
    "logbook.updated": "Contacto modificado",
    "logbook.deleted": "Contacto borrado",
    "logbook.all_deleted": "Se borraron todos los contactos",
    "logbook.clear": "Vaciar libro",
    "logbook.empty": "El libro de guardia está vacío.",
    "logbook.select_first": "Elija primero un contacto.",
    "logbook.confirm_save": "¿Guardar este contacto?",
    "logbook.confirm_delete": "¿Borrar este contacto?",
    "logbook.confirm_delete_all": "¿Borrar todos los contactos del libro?",
    "logbook.duplicate": "{} ya figura en el libro de guardia:",
    "logbook.date_invalid": "La fecha no es válida.",
    "logbook.time_invalid": "La hora no es válida.",
    "logbook.band_invalid": "Escriba una banda válida.",
    "logbook.frequency_invalid": "Escriba la frecuencia en MHz.",
    "logbook.adif_saved": "Archivo ADIF guardado: {}",
    "logbook.nothing_to_upload": "Todos los contactos del libro ya se enviaron.",
    "logbook.confirm_eqsl": "¿Enviar a eQSL los contactos pendientes?",
    "logbook.confirm_qrz": "¿Enviar a QRZ.com los contactos pendientes?",
    "logbook.eqsl_not_configured": "Escriba antes su usuario y contraseña de eQSL en Ajustes.",
    "logbook.qrz_not_configured": "Escriba antes su clave de API de QRZ.com Logbook en Ajustes.",
    "logbook.eqsl_uploading": "Enviando los contactos a eQSL ...",
    "logbook.qrz_uploading": "Enviando los contactos a QRZ.com ...",
    "logbook.eqsl_answer": "Respuesta de eQSL",
    "logbook.qrz_answer": "Respuesta de QRZ.com",
    "logbook.eqsl_unreachable": "No es posible comunicarse con eQSL.",
    "logbook.qrz_record_ok": "{}: enviado (id {})",
    "logbook.qrz_record_failed": "{}: no enviado - {}",
    "logbook.qrz_summary": "{} de {} contactos enviados a QRZ.com.",

    # Settings
    "settings.general": "General",
    "settings.platforms": "Libros en línea",
    "settings.rx_control": "Control de RX",
    "settings.tx_control": "Control de TX",
    "settings.auto": "Arranque",
    "settings.access_code": "Código de acceso",
    "settings.server": "Servidor",
    "settings.language": "Idioma",
    "settings.scale": "Escala",
    "settings.audio": "Audio",
    "settings.always_on_top": "Siempre visible",
    "settings.roger_beep": "Tono de fin",
    "settings.dmr_id": "ID DMR",
    "settings.dmr_lookup": "Buscar",
    "settings.dmr_lookup_failed": "radioid.net no responde. Puede escribir el ID DMR a mano.",
    "settings.dmr_not_found": "Este indicativo no tiene ningún ID DMR registrado.",
    "settings.update_radioid": "Actualizar la lista RadioID",
    "settings.message_hint": "Solo se envían los primeros 20 caracteres, sin tildes",
    "settings.restart_hint": "Los cambios de idioma y escala se aplican al reiniciar.",
    "settings.restart_needed": "Reinicie el programa para aplicar los cambios.",
    "settings.vox_threshold": "Umbral VOX",
    "settings.vox_hang_time": "Retardo VOX",
    "settings.return_hold": "Pausa de retorno",
    "settings.serial_port": "Puerto serie",
    "settings.tx_timeout": "Límite de TX",
    "settings.ctrl_key_ptt": "Tecla Ctrl como PTT",
    "settings.connect_at_start": "Conectar al arrancar",

    # Online logbook accounts
    "platforms.eqsl": "Cuenta de eQSL",
    "platforms.qrz": "Cuenta de QRZ.com (suscripción XML)",
    "platforms.user": "Usuario",
    "platforms.password": "Contraseña",
    "platforms.qth_nickname": "Alias del QTH",
    "platforms.qrz_api_key": "Clave de API del libro",

    # APRS
    "aprs.enable": "Enviar mi posición APRS",
    "aprs.host": "Servidor",
    "aprs.port": "Puerto",
    "aprs.latitude": "Latitud",
    "aprs.longitude": "Longitud",

    # Settings form checks
    "form.callsign_missing": "Escriba su indicativo.",
    "form.callsign_invalid": "El indicativo solo admite letras, cifras y \"/\", hasta 8 caracteres.",
    "form.dmr_id_invalid": "El ID DMR debe ser un número entre 0 y 16777215.",
    "form.scale_invalid": "La escala debe ser un número entero entre 1 y 3.",
    "form.rx_mode_invalid": "Elija un modo de control de RX válido.",
    "form.tx_mode_invalid": "Elija un modo de control de TX válido.",
    "form.rx_port_missing": "Elija el puerto serie del control de RX.",
    "form.tx_port_missing": "Elija el puerto serie del control de TX.",
    "form.vox_invalid": "Hay un valor de VOX fuera de rango.",
    "form.tx_timeout_invalid": "El límite de TX debe estar entre 30 y 300 segundos.",
    "form.auto_room_missing": "Elija la sala a la que conectar al arrancar.",
    "form.aprs_host_invalid": "Escriba el servidor APRS-IS.",
    "form.aprs_port_invalid": "El puerto APRS debe ser un número entre 1 y 65535.",
    "form.aprs_latitude_invalid": "La latitud debe ser un número decimal entre -90 y 90.",
    "form.aprs_longitude_invalid": "La longitud debe ser un número decimal entre -180 y 180.",

    # Logging in to the Peanut network
    "login.setup_required": (
        "Escriba su indicativo y su código de acceso Peanut en Ajustes y pulse Guardar.\n"
        "Los códigos de acceso se obtienen en www.pa7lim.nl/peanut"
    ),
    "login.wrong_code": "El código de acceso no corresponde al indicativo. Los códigos se obtienen en www.pa7lim.nl/peanut",
    "login.server_unreachable": "No es posible comunicarse con el servidor {}:\n{}",
    "login.refused": "La red Peanut rechazó el acceso.\nMotivo: {}",
    "login.reason_incorrect": "indicativo o código no aceptado",
    "login.reason_user_code": "código de acceso erróneo",
    "login.reason_upgrade": "esta versión del programa ya no se acepta",
    "login.reason_unknown": "desconocido",

    # Serial ports
    "serial.port_unavailable": "El puerto {0} no existe o lo está usando otro programa.",
    "serial.rescan_tip": "Volver a buscar puertos serie",

    # Audio
    "audio.title": "Audio",
    "audio.input": "Entrada",
    "audio.output": "Salida",
    "audio.rescan_tip": "Volver a buscar dispositivos de audio",
    "audio.input_failed": "No se puede usar el dispositivo de audio de entrada:\n{}",
    "audio.output_failed": "No se puede usar el dispositivo de audio de salida y la conexión se cerró:\n{}\n\nElija otro dispositivo en Ajustes.",
    "audio.device_fallback": "El dispositivo de audio {} no está disponible; se usa el dispositivo predeterminado del sistema.",
    "audio.unavailable": "No se puede iniciar el sistema de sonido y la estación no puede conectarse.\nRevise los dispositivos de audio y reinicie el programa.",

    # RadioID user list
    "radioid.updated": "La lista RadioID se actualizó",
    "radioid.invalid_file": "El archivo descargado no es una lista de usuarios de RadioID.",
    "radioid.download_failed": "No se pudo descargar la lista de usuarios de RadioID:\n{}",

    # Stored files
    "storage.value_invalid": "[{}] {} = {} no es válido; se usa el valor predeterminado.",
    "storage.settings_unreadable": "No se pudo leer el archivo de ajustes y se usan los ajustes predeterminados. Se guardó una copia como {}.",
    "storage.file_unreadable": "No se pudo leer {} y se usa uno vacío. Se guardó una copia como {}.",
}
