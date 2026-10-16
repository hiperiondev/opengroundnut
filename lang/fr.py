# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""French interface texts (see en.py for the meaning of the keys)."""

LANGUAGE_NAME = "Français"

TEXTS = {
    # Program
    "app.title": "Client OpenGroundnut",
    "update.available": "La version {} est disponible.\nVeuillez mettre le programme à jour.",

    # Buttons and words shared by many windows
    "common.ok": "OK",
    "common.cancel": "Annuler",
    "common.yes": "Oui",
    "common.no": "Non",
    "common.add": "Ajouter",
    "common.edit": "Modifier",
    "common.remove": "Retirer",
    "common.remove_all": "Tout retirer",
    "common.save": "Enregistrer",
    "common.clear": "Effacer",
    "common.show": "Afficher",
    "common.hide": "Masquer",
    "common.continue_question": "Continuer quand même ?",

    # Field names
    "field.callsign": "Indicatif",
    "field.name": "Nom",
    "field.date": "Date",
    "field.time": "Heure",
    "field.band": "Bande",
    "field.frequency": "Fréquence",
    "field.comment": "Commentaire",
    "field.room": "Salon",
    "field.message": "Message",
    "field.duration": "Durée",

    # Tabs
    "tab.main": "Accueil",
    "tab.monitor": "Moniteur",
    "tab.settings": "Réglages",

    # Header
    "clock.local": "Locale",
    "status.offline": "Hors ligne",
    "status.connecting": "Connexion",
    "status.online": "En ligne",
    "status.receiving": "Réception",
    "status.transmitting": "Émission",
    "status.scanning": "Balayage",
    "status.reconnecting": "Reconnexion ...",

    # Main tab
    "main.station_heard": "Station",
    "main.my_station": "Ma station",
    "main.last_heard": "Dernières entendues",
    "main.stations_in_room": "Stations du salon",
    "main.connect": "Connecter",
    "main.disconnect": "Déconnecter",
    "main.cancel_reconnect": "Reconnexion ... (cliquer pour annuler)",
    "main.choose_room": "Choisissez d'abord un salon.",
    "main.mute_tip": "Couper ou rétablir le haut-parleur",
    "station.unknown": "Inconnu",

    # Rooms and bookmarks
    "rooms.group": "Groupe",
    "rooms.bookmarks": "FAVORIS",
    "rooms.bookmark_add": "Ajouter aux favoris",
    "rooms.bookmark_remove": "Retirer des favoris",
    "rooms.bookmark_added": "Salon {} ajouté aux favoris",
    "rooms.bookmark_removed": "Salon {} retiré des favoris",
    "rooms.selected": "Salon {} choisi",
    "rooms.busy_transmitting": "Terminez l'émission avant de changer de salon.",
    "rooms.reload_tip": "Recharger les listes de serveurs et de salons",
    "rooms.reloading": "Chargement des listes de serveurs et de salons ...",

    # Monitor tab
    "monitor.filter": "Filtre",
    "monitor.filter_all": "Tout",
    "monitor.started": "Début",
    "monitor.double_click_hint": "Double-cliquez sur une ligne pour entrer dans son salon",

    # Room scanner
    "scan.manage": "Salons à balayer",
    "scan.available": "Salons disponibles",
    "scan.selected": "Salons à balayer",
    "scan.add_all": "Tout ajouter",
    "scan.search_hint": "Tapez pour chercher un salon",
    "scan.needs_connection": "Connectez-vous à un serveur Peanut avant de lancer le balayage.",
    "scan.no_rooms": "Aucun salon à balayer. Choisissez-en d'abord dans « Salons à balayer ».",

    # Callsign alarms
    "alarms.title": "Alarmes",
    "alarms.log_title": "Journal des alarmes",
    "alarms.state": "État",
    "alarms.time_utc": "Heure (UTC)",
    "alarms.online": "en ligne",
    "alarms.offline": "hors ligne",
    "alarms.toast": "Alarme : {} est {}",

    # Recording
    "rec.save_on_exit": "Enregistrer l'enregistrement avant de fermer ?",

    # Logbook
    "logbook.title": "Carnet de trafic",
    "logbook.add_title": "Ajouter au carnet",
    "logbook.edit_title": "Modifier le contact",
    "logbook.added": "Contact ajouté",
    "logbook.updated": "Contact modifié",
    "logbook.deleted": "Contact supprimé",
    "logbook.all_deleted": "Tous les contacts ont été supprimés",
    "logbook.clear": "Vider le carnet",
    "logbook.empty": "Le carnet de trafic est vide.",
    "logbook.select_first": "Choisissez d'abord un contact.",
    "logbook.confirm_save": "Enregistrer ce contact ?",
    "logbook.confirm_delete": "Supprimer ce contact ?",
    "logbook.confirm_delete_all": "Supprimer tous les contacts du carnet ?",
    "logbook.duplicate": "{} figure déjà dans le carnet :",
    "logbook.date_invalid": "La date n'est pas valide.",
    "logbook.time_invalid": "L'heure n'est pas valide.",
    "logbook.band_invalid": "Indiquez une bande valide.",
    "logbook.frequency_invalid": "Indiquez la fréquence en MHz.",
    "logbook.adif_saved": "Fichier ADIF enregistré : {}",
    "logbook.nothing_to_upload": "Tous les contacts du carnet ont déjà été envoyés.",
    "logbook.confirm_eqsl": "Envoyer à eQSL les contacts en attente ?",
    "logbook.confirm_qrz": "Envoyer à QRZ.com les contacts en attente ?",
    "logbook.eqsl_not_configured": "Indiquez d'abord votre nom d'utilisateur et votre mot de passe eQSL dans les Réglages.",
    "logbook.qrz_not_configured": "Indiquez d'abord votre clé API QRZ.com Logbook dans les Réglages.",
    "logbook.eqsl_uploading": "Envoi des contacts à eQSL ...",
    "logbook.qrz_uploading": "Envoi des contacts à QRZ.com ...",
    "logbook.eqsl_answer": "Réponse d'eQSL",
    "logbook.qrz_answer": "Réponse de QRZ.com",
    "logbook.eqsl_unreachable": "eQSL est injoignable.",
    "logbook.qrz_record_ok": "{} : envoyé (id {})",
    "logbook.qrz_record_failed": "{} : non envoyé - {}",
    "logbook.qrz_summary": "{} contacts sur {} envoyés à QRZ.com.",

    # Settings
    "settings.general": "Général",
    "settings.platforms": "Carnets en ligne",
    "settings.rx_control": "Contrôle RX",
    "settings.tx_control": "Contrôle TX",
    "settings.auto": "Démarrage",
    "settings.access_code": "Code d'accès",
    "settings.server": "Serveur",
    "settings.language": "Langue",
    "settings.scale": "Échelle",
    "settings.audio": "Audio",
    "settings.always_on_top": "Toujours au premier plan",
    "settings.roger_beep": "Bip de fin",
    "settings.dmr_id": "ID DMR",
    "settings.dmr_lookup": "Chercher",
    "settings.dmr_lookup_failed": "radioid.net ne répond pas. Vous pouvez saisir l'ID DMR vous-même.",
    "settings.dmr_not_found": "Aucun ID DMR n'est enregistré pour cet indicatif.",
    "settings.update_radioid": "Mettre à jour la liste RadioID",
    "settings.message_hint": "Seuls les 20 premiers caractères sont envoyés, sans accents",
    "settings.restart_hint": "Les changements de langue et d'échelle s'appliquent au redémarrage.",
    "settings.restart_needed": "Redémarrez le programme pour appliquer les changements.",
    "settings.vox_threshold": "Seuil VOX",
    "settings.vox_hang_time": "Maintien VOX",
    "settings.return_hold": "Pause de retour",
    "settings.serial_port": "Port série",
    "settings.tx_timeout": "Durée max. d'émission",
    "settings.ctrl_key_ptt": "Touche Ctrl comme PTT",
    "settings.connect_at_start": "Se connecter au démarrage",

    # Online logbook accounts
    "platforms.eqsl": "Compte eQSL",
    "platforms.qrz": "Compte QRZ.com (abonnement XML)",
    "platforms.user": "Utilisateur",
    "platforms.password": "Mot de passe",
    "platforms.qth_nickname": "Nom du QTH",
    "platforms.qrz_api_key": "Clé API du carnet",

    # APRS
    "aprs.enable": "Envoyer ma position APRS",
    "aprs.host": "Serveur",
    "aprs.port": "Port",
    "aprs.latitude": "Latitude",
    "aprs.longitude": "Longitude",

    # Settings form checks
    "form.callsign_missing": "Indiquez votre indicatif.",
    "form.callsign_invalid": "Un indicatif ne peut contenir que des lettres, des chiffres et « / », 8 caractères au plus.",
    "form.dmr_id_invalid": "L'ID DMR doit être un nombre de 0 à 16777215.",
    "form.scale_invalid": "L'échelle doit être un nombre entier de 1 à 3.",
    "form.rx_mode_invalid": "Choisissez un mode de contrôle RX valide.",
    "form.tx_mode_invalid": "Choisissez un mode de contrôle TX valide.",
    "form.rx_port_missing": "Choisissez le port série du contrôle RX.",
    "form.tx_port_missing": "Choisissez le port série du contrôle TX.",
    "form.vox_invalid": "Une valeur du VOX est hors limites.",
    "form.tx_timeout_invalid": "La durée max. d'émission doit être comprise entre 30 et 300 secondes.",
    "form.auto_room_missing": "Choisissez le salon à rejoindre au démarrage.",
    "form.aprs_host_invalid": "Indiquez le serveur APRS-IS.",
    "form.aprs_port_invalid": "Le port APRS doit être un nombre de 1 à 65535.",
    "form.aprs_latitude_invalid": "La latitude doit être un nombre décimal de -90 à 90.",
    "form.aprs_longitude_invalid": "La longitude doit être un nombre décimal de -180 à 180.",

    # Logging in to the Peanut network
    "login.setup_required": (
        "Indiquez votre indicatif et son code d'accès Peanut dans les Réglages, puis cliquez sur Enregistrer.\n"
        "Les codes d'accès sont délivrés sur www.pa7lim.nl/peanut"
    ),
    "login.wrong_code": "Le code d'accès ne correspond pas à l'indicatif. Les codes sont délivrés sur www.pa7lim.nl/peanut",
    "login.server_unreachable": "Le serveur {} est injoignable :\n{}",
    "login.refused": "Le réseau Peanut a refusé la connexion.\nMotif : {}",
    "login.reason_incorrect": "indicatif ou code refusé",
    "login.reason_user_code": "code d'accès erroné",
    "login.reason_upgrade": "cette version du programme n'est plus acceptée",
    "login.reason_unknown": "inconnu",

    # Serial ports
    "serial.port_unavailable": "Le port {0} n'existe pas ou est utilisé par un autre programme.",
    "serial.rescan_tip": "Rechercher à nouveau les ports série",

    # Audio
    "audio.title": "Audio",
    "audio.input": "Entrée",
    "audio.output": "Sortie",
    "audio.rescan_tip": "Rechercher à nouveau les périphériques audio",
    "audio.input_failed": "Le périphérique audio d'entrée est inutilisable :\n{}",
    "audio.output_failed": "Le périphérique audio de sortie est inutilisable, la connexion a donc été fermée :\n{}\n\nChoisissez un autre périphérique dans les Réglages.",
    "audio.device_fallback": "Le périphérique audio {} n'est pas disponible ; celui du système est utilisé.",
    "audio.unavailable": "Le système audio ne peut pas démarrer, la station ne peut donc pas se connecter.\nVérifiez les périphériques audio et redémarrez le programme.",

    # RadioID user list
    "radioid.updated": "La liste RadioID a été mise à jour",
    "radioid.invalid_file": "Le fichier téléchargé n'est pas une liste d'utilisateurs RadioID.",
    "radioid.download_failed": "Impossible de télécharger la liste d'utilisateurs RadioID :\n{}",

    # Stored files
    "storage.value_invalid": "[{}] {} = {} n'est pas valide ; la valeur par défaut est utilisée.",
    "storage.settings_unreadable": "Le fichier de réglages est illisible, les réglages par défaut sont utilisés. Une copie a été conservée sous {}.",
    "storage.file_unreadable": "{} est illisible, un fichier vide est utilisé. Une copie a été conservée sous {}.",
}
