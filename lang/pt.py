# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Portuguese interface texts (see en.py for the meaning of the keys)."""

LANGUAGE_NAME = "Português"

TEXTS = {
    # Program
    "app.title": "Cliente OpenGroundnut",
    "update.available": "A versão {} já está disponível.\nAtualize o programa.",

    # Buttons and words shared by many windows
    "common.ok": "OK",
    "common.cancel": "Cancelar",
    "common.yes": "Sim",
    "common.no": "Não",
    "common.add": "Adicionar",
    "common.edit": "Editar",
    "common.remove": "Remover",
    "common.remove_all": "Remover tudo",
    "common.save": "Salvar",
    "common.clear": "Limpar",
    "common.show": "Mostrar",
    "common.hide": "Ocultar",
    "common.continue_question": "Deseja continuar mesmo assim?",

    # Field names
    "field.callsign": "Indicativo",
    "field.name": "Nome",
    "field.date": "Data",
    "field.time": "Hora",
    "field.band": "Banda",
    "field.frequency": "Frequência",
    "field.comment": "Comentário",
    "field.room": "Sala",
    "field.message": "Mensagem",
    "field.duration": "Duração",

    # Tabs
    "tab.main": "Início",
    "tab.monitor": "Monitor",
    "tab.settings": "Configurações",

    # Header
    "clock.local": "Local",
    "status.offline": "Desconectado",
    "status.connecting": "Conectando",
    "status.online": "Conectado",
    "status.receiving": "Recebendo",
    "status.transmitting": "Transmitindo",
    "status.scanning": "Varrendo",
    "status.reconnecting": "Reconectando ...",

    # Main tab
    "main.station_heard": "Estação",
    "main.my_station": "Minha estação",
    "main.last_heard": "Últimas ouvidas",
    "main.stations_in_room": "Estações na sala",
    "main.connect": "Conectar",
    "main.disconnect": "Desconectar",
    "main.cancel_reconnect": "Reconectando ... (clique para cancelar)",
    "main.choose_room": "Escolha uma sala primeiro.",
    "main.mute_tip": "Silenciar ou reativar o alto-falante",
    "station.unknown": "Desconhecido",

    # Rooms and bookmarks
    "rooms.group": "Grupo",
    "rooms.bookmarks": "FAVORITOS",
    "rooms.bookmark_add": "Adicionar aos favoritos",
    "rooms.bookmark_remove": "Remover dos favoritos",
    "rooms.bookmark_added": "Sala {} adicionada aos favoritos",
    "rooms.bookmark_removed": "Sala {} removida dos favoritos",
    "rooms.selected": "Sala {} escolhida",
    "rooms.busy_transmitting": "Termine a transmissão antes de trocar de sala.",
    "rooms.reload_tip": "Carregar novamente as listas de servidores e salas",
    "rooms.reloading": "Carregando as listas de servidores e salas ...",

    # Monitor tab
    "monitor.filter": "Filtro",
    "monitor.filter_all": "Tudo",
    "monitor.started": "Início",
    "monitor.double_click_hint": "Clique duas vezes em uma linha para entrar na sala",

    # Room scanner
    "scan.manage": "Salas da varredura",
    "scan.available": "Salas disponíveis",
    "scan.selected": "Salas da varredura",
    "scan.add_all": "Adicionar todas",
    "scan.search_hint": "Digite para procurar uma sala",
    "scan.needs_connection": "Conecte-se a um servidor Peanut antes de iniciar a varredura.",
    "scan.no_rooms": "Não há salas para a varredura. Escolha-as antes em \"Salas da varredura\".",

    # Callsign alarms
    "alarms.title": "Alarmes",
    "alarms.log_title": "Histórico de alarmes",
    "alarms.state": "Estado",
    "alarms.time_utc": "Hora (UTC)",
    "alarms.online": "conectado",
    "alarms.offline": "desconectado",
    "alarms.toast": "Alarme: {} está {}",

    # Recording
    "rec.save_on_exit": "Salvar a gravação antes de fechar?",

    # Logbook
    "logbook.title": "Logbook",
    "logbook.add_title": "Adicionar ao logbook",
    "logbook.edit_title": "Editar contato",
    "logbook.added": "Contato adicionado",
    "logbook.updated": "Contato atualizado",
    "logbook.deleted": "Contato excluído",
    "logbook.all_deleted": "Todos os contatos foram excluídos",
    "logbook.clear": "Esvaziar logbook",
    "logbook.empty": "O logbook está vazio.",
    "logbook.select_first": "Selecione um contato primeiro.",
    "logbook.confirm_save": "Salvar este contato?",
    "logbook.confirm_delete": "Excluir este contato?",
    "logbook.confirm_delete_all": "Excluir todos os contatos do logbook?",
    "logbook.duplicate": "{} já está no logbook:",
    "logbook.date_invalid": "A data não é válida.",
    "logbook.time_invalid": "A hora não é válida.",
    "logbook.band_invalid": "Digite uma banda válida.",
    "logbook.frequency_invalid": "Digite a frequência em MHz.",
    "logbook.adif_saved": "Arquivo ADIF salvo: {}",
    "logbook.nothing_to_upload": "Todos os contatos do logbook já foram enviados.",
    "logbook.confirm_eqsl": "Enviar ao eQSL os contatos pendentes?",
    "logbook.confirm_qrz": "Enviar ao QRZ.com os contatos pendentes?",
    "logbook.eqsl_not_configured": "Informe antes seu usuário e senha do eQSL nas Configurações.",
    "logbook.qrz_not_configured": "Informe antes sua chave de API do QRZ.com Logbook nas Configurações.",
    "logbook.eqsl_uploading": "Enviando os contatos ao eQSL ...",
    "logbook.qrz_uploading": "Enviando os contatos ao QRZ.com ...",
    "logbook.eqsl_answer": "Resposta do eQSL",
    "logbook.qrz_answer": "Resposta do QRZ.com",
    "logbook.eqsl_unreachable": "Não foi possível acessar o eQSL.",
    "logbook.qrz_record_ok": "{}: enviado (id {})",
    "logbook.qrz_record_failed": "{}: não enviado - {}",
    "logbook.qrz_summary": "{} de {} contatos enviados ao QRZ.com.",

    # Settings
    "settings.general": "Geral",
    "settings.platforms": "Logbooks on-line",
    "settings.rx_control": "Controle de RX",
    "settings.tx_control": "Controle de TX",
    "settings.auto": "Inicialização",
    "settings.access_code": "Código de acesso",
    "settings.server": "Servidor",
    "settings.language": "Idioma",
    "settings.scale": "Escala",
    "settings.audio": "Áudio",
    "settings.always_on_top": "Sempre visível",
    "settings.roger_beep": "Bipe de fim",
    "settings.dmr_id": "ID DMR",
    "settings.dmr_lookup": "Pesquisar",
    "settings.dmr_lookup_failed": "O radioid.net não respondeu. Você pode digitar o ID DMR manualmente.",
    "settings.dmr_not_found": "Nenhum ID DMR está registrado para este indicativo.",
    "settings.update_radioid": "Atualizar a lista RadioID",
    "settings.message_hint": "Só os primeiros 20 caracteres são enviados, sem acentos",
    "settings.restart_hint": "As mudanças de idioma e escala valem após reiniciar.",
    "settings.restart_needed": "Reinicie o programa para aplicar as mudanças.",
    "settings.vox_threshold": "Limiar do VOX",
    "settings.vox_hang_time": "Retenção do VOX",
    "settings.return_hold": "Pausa de retorno",
    "settings.serial_port": "Porta serial",
    "settings.tx_timeout": "Tempo máximo de TX",
    "settings.ctrl_key_ptt": "Tecla Ctrl como PTT",
    "settings.connect_at_start": "Conectar ao iniciar",

    # Online logbook accounts
    "platforms.eqsl": "Conta do eQSL",
    "platforms.qrz": "Conta do QRZ.com (assinatura XML)",
    "platforms.user": "Usuário",
    "platforms.password": "Senha",
    "platforms.qth_nickname": "Apelido do QTH",
    "platforms.qrz_api_key": "Chave de API do logbook",

    # APRS
    "aprs.enable": "Enviar minha posição APRS",
    "aprs.host": "Servidor",
    "aprs.port": "Porta",
    "aprs.latitude": "Latitude",
    "aprs.longitude": "Longitude",

    # Settings form checks
    "form.callsign_missing": "Digite seu indicativo.",
    "form.callsign_invalid": "O indicativo só pode ter letras, algarismos e \"/\", até 8 caracteres.",
    "form.dmr_id_invalid": "O ID DMR deve ser um número de 0 a 16777215.",
    "form.scale_invalid": "A escala deve ser um número inteiro de 1 a 3.",
    "form.rx_mode_invalid": "Escolha um modo de controle de RX válido.",
    "form.tx_mode_invalid": "Escolha um modo de controle de TX válido.",
    "form.rx_port_missing": "Escolha a porta serial do controle de RX.",
    "form.tx_port_missing": "Escolha a porta serial do controle de TX.",
    "form.vox_invalid": "Um valor do VOX está fora da faixa.",
    "form.tx_timeout_invalid": "O tempo máximo de TX deve ficar entre 30 e 300 segundos.",
    "form.auto_room_missing": "Escolha a sala para conectar ao iniciar.",
    "form.aprs_host_invalid": "Digite o servidor APRS-IS.",
    "form.aprs_port_invalid": "A porta APRS deve ser um número de 1 a 65535.",
    "form.aprs_latitude_invalid": "A latitude deve ser um número decimal de -90 a 90.",
    "form.aprs_longitude_invalid": "A longitude deve ser um número decimal de -180 a 180.",

    # Logging in to the Peanut network
    "login.setup_required": (
        "Informe seu indicativo e o código de acesso Peanut nas Configurações e clique em Salvar.\n"
        "Os códigos de acesso são emitidos em www.pa7lim.nl/peanut"
    ),
    "login.wrong_code": "O código de acesso não corresponde ao indicativo. Os códigos são emitidos em www.pa7lim.nl/peanut",
    "login.server_unreachable": "Não foi possível acessar o servidor {}:\n{}",
    "login.refused": "A rede Peanut recusou o acesso.\nMotivo: {}",
    "login.reason_incorrect": "indicativo ou código não aceito",
    "login.reason_user_code": "código de acesso incorreto",
    "login.reason_upgrade": "esta versão do programa não é mais aceita",
    "login.reason_unknown": "desconhecido",

    # Serial ports
    "serial.port_unavailable": "A porta {0} não existe ou está sendo usada por outro programa.",
    "serial.rescan_tip": "Procurar portas seriais novamente",

    # Audio
    "audio.title": "Áudio",
    "audio.input": "Entrada",
    "audio.output": "Saída",
    "audio.rescan_tip": "Procurar dispositivos de áudio novamente",
    "audio.input_failed": "Não é possível usar o dispositivo de áudio de entrada:\n{}",
    "audio.output_failed": "Não é possível usar o dispositivo de áudio de saída, por isso a conexão foi fechada:\n{}\n\nEscolha outro dispositivo nas Configurações.",
    "audio.device_fallback": "O dispositivo de áudio {} não está disponível; o dispositivo padrão do sistema é usado.",
    "audio.unavailable": "Não é possível iniciar o sistema de som, então a estação não pode se conectar.\nVerifique os dispositivos de áudio e reinicie o programa.",

    # RadioID user list
    "radioid.updated": "A lista RadioID foi atualizada",
    "radioid.invalid_file": "O arquivo baixado não é uma lista de usuários do RadioID.",
    "radioid.download_failed": "Não foi possível baixar a lista de usuários do RadioID:\n{}",

    # Stored files
    "storage.value_invalid": "[{}] {} = {} não é válido; o valor padrão é usado.",
    "storage.settings_unreadable": "Não foi possível ler o arquivo de configurações, então as configurações padrão são usadas. Uma cópia foi guardada como {}.",
    "storage.file_unreadable": "Não foi possível ler {}, então um arquivo vazio é usado. Uma cópia foi guardada como {}.",
}
