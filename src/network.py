# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Peanut server communication: the UDP voice protocol and the HTTP services.

Every message of the Peanut UDP protocol is built and parsed here. The layout
of each message is described in README.md ("Peanut protocol overview").

One connection uses one UDP socket. The socket is "connected" to the server
address, so the operating system only delivers datagrams that really come
from the server, and the server name is looked up once per connection
instead of once per packet.
"""

# Sizes and codes of the Peanut voice frames.
DPCM_HEADER_SIZE = 30
DPCM_AUDIO_SIZE = 320
FRAME_TYPE_AUDIO = 1
FRAME_TYPE_END = 16

# Audio format of the Peanut network: 8 kHz, 16 bit, mono, 160 samples per frame.
SAMPLE_RATE = 8000
FRAME_SAMPLES = 160

# Receive buffer. Larger than any Peanut datagram, so an unexpected big
# packet is read (and ignored) instead of raising an error on Windows.
RX_BUFFER_SIZE = 2048

# How long a receive call waits before checking whether the connection ended.
UDP_RX_TIMEOUT = 0.5

# Playout buffer of the received audio. Frames arrive from the network at
# uneven moments; a separate playback thread plays them, so a late packet
# or a slow sound card never holds up the reception of the next packets.
# After a pause, playback waits for PLAYOUT_PREFILL_FRAMES frames (or
# PLAYOUT_PREFILL_SECONDS) so short delays in the network are absorbed.
# At most PLAYOUT_MAX_FRAMES wait in the buffer; when the sound card falls
# behind, the oldest frame is dropped so the delay never grows.
PLAYOUT_MAX_FRAMES = 25
PLAYOUT_PREFILL_FRAMES = 3
PLAYOUT_PREFILL_SECONDS = 0.06
PLAYOUT_IDLE_SECONDS = 0.1

# The login is repeated every few seconds until the server answers.
LOGIN_RETRY_SECONDS = 2.0
LOGIN_MAX_ATTEMPTS = 5

# The UDP socket of the current connection and the server address it talks to.
udp = None
server_addr = None

# Number of the current connection. Each connection gets a new number, and a
# worker thread that belongs to an older connection ends on its own.
connection_generation = 0

# Remembers whether the last UDP send failed, so a long outage is reported
# once instead of once for every audio frame.
udp_send_failed = False


def _debug_packet(direction, packet, address=None):
    """Write complete Peanut UDP packet details to the log when --debug is enabled."""
    if not debug_mode:
        return
    peer = " peer={}:{}".format(*address) if address else ""
    log.debug(
        "%s%s length=%d ascii=%r hex=%s",
        direction, peer, len(packet), packet.decode("ascii", errors="backslashreplace"), packet.hex(" "),
    )


def connection_is_current(generation):
    """True while the connection numbered `generation` is the live one."""
    return not connection_closed and not app_closing and generation == connection_generation


# ---------------------------------------------------------------------------
# Socket
# ---------------------------------------------------------------------------

def open_udp_socket():
    """Open the UDP socket of a new connection and return it.

    The server name is resolved here, once. Raises OSError (for example
    socket.gaierror when the name cannot be resolved).
    """
    global udp, server_addr
    address = (socket.gethostbyname(master_host), PEANUT_UDP_PORT)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(UDP_RX_TIMEOUT)
        sock.connect(address)
    except OSError:
        sock.close()
        raise
    server_addr = address
    udp = sock
    return sock


def close_udp_socket():
    """Close the UDP socket of the current connection (safe to call more than once)."""
    global udp
    sock, udp = udp, None
    if sock is not None:
        try:
            sock.close()
        except OSError:
            pass


def send_datagram(datagram):
    """Send one datagram to the Peanut server.

    Returns True when the datagram was handed to the network stack and False
    when sending failed (no connection, closed socket, unreachable network...).
    """
    global udp_send_failed
    sock = udp
    _debug_packet("TX UDP", datagram, server_addr)
    if sock is None:
        return False
    try:
        sock.send(datagram)
    except OSError as e_send:
        # Report only the first failure of a streak.
        if not udp_send_failed:
            log.warning("UDP send failed: %s", e_send)
        udp_send_failed = True
        return False
    if udp_send_failed:
        log.info("UDP send works again")
    udp_send_failed = False
    return True


# ---------------------------------------------------------------------------
# Control messages
# ---------------------------------------------------------------------------

def login():
    """Ask the server to accept this station: LOGIN + callsign + access code."""
    send_datagram(("LOGIN" + ascii_field(callsign, 8) + ascii_field(access_code, 8)).encode("ascii"))


def logout():
    """Tell the server that this station leaves."""
    send_datagram(b"LOGOUT")


def room_field():
    """The active room as an 8-character field (blank when no room is set)."""
    return ascii_field(active_room or "", 8)


def pong():
    """Answer a PING and announce the room this station is in."""
    send_datagram(("PONG" + ascii_field(callsign, 8) + room_field()).encode("ascii"))


def info():
    """Describe this client to the server (sent after the login is accepted)."""
    send_datagram(("INFO" + ascii_field(callsign, 8) + ascii_field(DEVICE_NAME, 20) + ascii_field(PROTOCOL_VERSION, 5)).encode("ascii"))


def send_room_message():
    """Send the short text message shown next to our callsign while we transmit."""
    send_datagram(("PMSG" + room_field() + ascii_field(tx_message[:20], 20)).encode("ascii"))


def note_server_alive():
    """Remember when the server last proved it is alive."""
    global last_ping_ms
    last_ping_ms = monotonic_ms()


def handle_refusal(refusal_packet):
    """The server refused this station (REFU): disconnect and tell the user why.

    The program stays open, so a wrong callsign or access code can be
    corrected in Settings. No automatic reconnection follows: the server
    would only refuse again.
    """
    # The refusal reason lives in byte 4, right after the "REFU" prefix.
    # A datagram that is only "REFU" has no reason byte: it counts as unknown.
    reason_code = refusal_packet[4] if len(refusal_packet) > 4 else 0
    if reason_code == 1:
        msg = tr("login.reason_incorrect")
    elif reason_code == 2:
        msg = tr("login.reason_user_code")
    elif reason_code == 3:
        msg = tr("login.reason_upgrade")
    else:
        msg = tr("login.reason_unknown")
    log.error("The server refused the login (reason %s)", reason_code)
    disconnect_from_server()
    emit_event("login_refused", title="Error", message=tr("login.refused").format(msg), reason=reason_code)


# ---------------------------------------------------------------------------
# Voice frames
# ---------------------------------------------------------------------------

def _dpcm_header(frame_type):
    """First 30 bytes of a DPCM frame: callsign, room, DMR id, sequence, RSSI, type, session."""
    frame = bytearray(("DPCM" + ascii_field(callsign, 8) + room_field()).encode("ascii"))
    frame += bytes(
        (
            0,
            0,
            (dmr_id >> 16) & 255,
            (dmr_id >> 8) & 255,
            dmr_id & 255,
            tx_sequence & 255,
            (tx_sequence >> 8) & 255,
            RSSI_BYTE_VALUE & 255,
            frame_type,
            session_id & 255,
        )
    )
    return frame


def send_audio_frame(pcm):
    """Send one 20 ms frame of our audio to the server."""
    global tx_sequence
    with state_lock:
        if tx_sequence < 2:
            send_room_message()
        send_datagram(bytes(_dpcm_header(FRAME_TYPE_AUDIO)) + pcm)
        tx_sequence += 1


def send_end_of_transmission():
    """Tell the server our transmission ended (a DPCM frame of type 16 with silent audio)."""
    global tx_sequence, session_id
    with state_lock:
        send_datagram(bytes(_dpcm_header(FRAME_TYPE_END)) + bytes(DPCM_AUDIO_SIZE))
        session_id = (session_id + 1) % 256
        tx_sequence = 0


def build_end_beep():
    """The short "roger beep" played when another station stops talking.

    600 Hz for 120 ms, 16-bit mono at the Peanut sample rate, at a gentle volume.
    """
    frequency = 600
    duration = 0.12
    amplitude = 0.1 * 32767
    samples = int(SAMPLE_RATE * duration)
    return b"".join(
        struct.pack("<h", int(amplitude * math.sin(2 * math.pi * frequency * n / SAMPLE_RATE)))
        for n in range(samples)
    )


# ---------------------------------------------------------------------------
# Receive loop
# ---------------------------------------------------------------------------

def _queue_for_playout(playout, pcm):
    """Hand audio to the playback thread, dropping the oldest frame when the buffer is full."""
    while True:
        try:
            playout.put_nowait(pcm)
            return
        except queue.Full:
            try:
                playout.get_nowait()
            except queue.Empty:
                pass


def _playout_loop(stream, playout, failures):
    """Play the received audio handed over by the receive loop (playback thread).

    None in the queue ends the loop. When the speaker stops working, the
    error is added to `failures` and the loop ends; the receive loop then
    tells the user and closes the connection.
    """
    # Playback starts idle, so the very first audio also gathers a few frames.
    idle_since = monotonic() - PLAYOUT_IDLE_SECONDS
    while True:
        try:
            pcm = playout.get(timeout=PLAYOUT_IDLE_SECONDS)
        except queue.Empty:
            idle_since = idle_since or monotonic()
            continue
        if pcm is None:
            return
        if idle_since and monotonic() - idle_since >= PLAYOUT_IDLE_SECONDS:
            # Audio starts again after a pause: let a few frames gather first.
            deadline = monotonic() + PLAYOUT_PREFILL_SECONDS
            while playout.qsize() < PLAYOUT_PREFILL_FRAMES - 1 and monotonic() < deadline:
                sleep(0.005)
        idle_since = 0.0
        try:
            stream.write(pcm)
        except OSError as exc:
            failures.append(exc)
            return
        if playout.empty():
            idle_since = monotonic()


def receive_loop(sock, generation):
    """Receive and play the voice of the room until the connection numbered `generation` ends.

    The loop also logs in (repeating the LOGIN until the server answers),
    answers PINGs and reacts to the control messages. Whatever happens, the
    audio stream and this connection's socket are closed when it ends.
    """
    global heard_call, start_time
    try:
        stream = open_audio_stream(want_input=False, frames_per_buffer=FRAME_SAMPLES * 2)
    except Exception as exc:
        report_audio_failure(exc, generation)
        return

    beep_data = build_end_beep()
    playout = queue.Queue(maxsize=PLAYOUT_MAX_FRAMES)
    playback_failures = []
    player = threading.Thread(
        target=_playout_loop, args=(stream, playout, playback_failures), name="rx-playback", daemon=True
    )
    player.start()
    last_call = None
    last_session = None
    rx_started = monotonic()
    login_attempts = 0
    last_login = 0.0

    try:
        while connection_is_current(generation):
            if playback_failures:
                # The speaker stopped working while playing (device unplugged,
                # sound server gone): the user is told and the connection is closed.
                report_audio_failure(playback_failures[0], generation)
                break
            if not link_up and login_attempts < LOGIN_MAX_ATTEMPTS and monotonic() - last_login >= LOGIN_RETRY_SECONDS:
                login()
                login_attempts += 1
                last_login = monotonic()

            try:
                (packet_in, addr) = sock.recvfrom(RX_BUFFER_SIZE)
            except socket.timeout:
                continue
            except ConnectionResetError:
                # Windows reports an earlier unreachable send this way: not fatal.
                continue
            except OSError as exc:
                if not connection_is_current(generation):
                    break
                log.warning("UDP receive failed: %s", exc)
                sleep(0.2)
                continue

            if not connection_is_current(generation):
                break
            _debug_packet("RX UDP", packet_in, addr)
            if not packet_in:
                continue

            if packet_in.startswith(b"DPCM"):
                # While we are transmitting we ignore incoming audio, and a
                # frame shorter than the fixed header is not a valid frame.
                if tx_active or len(packet_in) < DPCM_HEADER_SIZE:
                    continue

                # Bytes 4-11 hold the callsign of the station that is talking,
                # byte 28 the frame type and byte 29 the session number.
                talker = clean_callsign(packet_in[4:12].decode("ascii", errors="replace"))
                frame_type = packet_in[28]
                session = packet_in[29]
                audio = packet_in[DPCM_HEADER_SIZE:]
                same_transmission = last_call is not None and talker == last_call and session == last_session

                if frame_type == FRAME_TYPE_END:
                    # Only the end of the transmission being heard counts. An
                    # end frame of a transmission we never heard (a repeated
                    # end frame, or one that arrives just after joining a
                    # room) changes nothing: no log entry, no beep.
                    if same_transmission:
                        log_end_of_transmission(talker, active_room, start_time, monotonic() - rx_started)
                        last_call = None
                        last_session = None
                        if int(roger_beep or 0) == 1 and not speaker_muted:
                            _queue_for_playout(playout, beep_data)
                    continue

                # A normal audio frame carries exactly 320 bytes (160 samples);
                # anything else is not audio we can play.
                if len(audio) != DPCM_AUDIO_SIZE:
                    continue

                if not same_transmission:
                    # Another station took over without sending its end
                    # frame: its transmission is logged before the new one.
                    if last_call is not None:
                        log_end_of_transmission(last_call, active_room, start_time, monotonic() - rx_started)
                    heard_call = talker
                    start_time = time()
                    rx_started = monotonic()
                    last_call = talker
                    last_session = session
                    lookup_queue.put((talker, ""))

                # The link state ("receiving") is set by the status monitor
                # from the time of the latest audio frame, so it always goes
                # back to idle once the audio stops.
                note_rx_frame()
                if link_state == 1 and not same_transmission:
                    # Still receiving, but from another station: show its call.
                    apply_link_state(1)
                pause_scanner()
                if not speaker_muted:
                    _queue_for_playout(playout, audio)
                record_frame(audio)
                emit_event("audio_level", level=int(pcm_rms(audio) / 100))

            elif packet_in.startswith(b"PING"):
                # The server is alive: feed the watchdog and answer with a PONG.
                note_server_alive()
                pong()
                if not link_up:
                    mark_link_up()
            elif packet_in.startswith(b"REFU"):
                handle_refusal(packet_in)
                break
            elif packet_in.startswith(b"ACK"):
                info()
                if not link_up:
                    mark_link_up()
            # PMSG, PGPS and any other prefix need no handling.
    finally:
        # The playback thread finishes the audio it holds and ends; only then
        # is the stream closed, so it is never closed while being written.
        _queue_for_playout(playout, None)
        player.join(timeout=2.0)
        if not player.is_alive():
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        else:
            log.warning("The speaker is not answering; its stream is left to the system.")
        try:
            sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Transmit loops
# ---------------------------------------------------------------------------

def vox_transmit_loop(generation):
    """Watch the microphone (VOX) or the serial squelch line and transmit while it is active.

    Runs for the whole connection when RX control is VOX or one of the serial
    modes. The audio is sent while a transmission is on, whatever started it.
    """
    try:
        stream = open_audio_stream(want_input=True, frames_per_buffer=FRAME_SAMPLES * 7)
    except Exception as exc:
        log.error("The input audio device cannot be opened: %s", exc)
        emit_event("error", title=tr("audio.title"), message=tr("audio.input_failed").format(exc))
        return

    try:
        # voice_heard: VOX hears voice (it stays on for vox_delay frames of
        # silence, so short pauses do not end the transmission).
        voice_heard = False
        decay = int(vox_delay_setting)
        # auto_started: the transmission in progress was started by VOX or by
        # the squelch line, so this loop also ends it when the input goes quiet.
        auto_started = False
        # wait_for_release: the transmission was ended by something else (the
        # transmit time-out, a disconnection, the PTT button), so a new one
        # only starts after the input has gone quiet once.
        wait_for_release = False
        serial_failed = False
        while connection_is_current(generation):
            try:
                audio = stream.read(FRAME_SAMPLES, exception_on_overflow=False)
            except OSError as exc:
                # The microphone stopped working (device unplugged, sound
                # server gone): the user is told and the connection is closed.
                log.error("The input audio device stopped working: %s", exc)
                emit_event("error", title=tr("audio.title"), message=tr("audio.input_failed").format(exc))
                if generation == connection_generation and session_active:
                    disconnect_from_server()
                return
            rms = pcm_rms(audio)

            # 1. Is the input active right now?
            input_active = False
            if rx_mode == "VOX":
                if rms > int(vox_threshold_setting):
                    decay = int(vox_delay_setting)
                    voice_heard = True
                elif voice_heard:
                    decay -= 1
                    if decay <= 0:
                        voice_heard = False
                input_active = voice_heard
            elif rx_mode.startswith("Serial") and not serial_failed:
                try:
                    input_active = read_squelch_line()
                except (OSError, serial.SerialException) as exc:
                    # The serial adapter disappeared: receive keeps working,
                    # but the squelch line can no longer start transmissions.
                    serial_failed = True
                    log.error("The squelch serial port stopped working: %s", exc)
                    emit_event("error", title="Error", message=tr("serial.port_unavailable").format(rx_serial_port) + "\n" + str(exc))

            # While the radio hears a station, the scanner stays in the
            # current room, so the reply goes to the room that was heard.
            if input_active and scanner_running:
                pause_scanner()

            # 2. Start or end the transmission to follow the input. The start
            # is tried on every frame, so voice that begins while the room is
            # still heard (or during the return hold) is sent as soon as
            # transmitting is allowed.
            if auto_started and not ptt_pressed:
                auto_started = False
                wait_for_release = True
            if input_active:
                if not ptt_pressed and not wait_for_release and session_active:
                    auto_started = auto_ptt_start()
            else:
                wait_for_release = False
                if auto_started and ptt_pressed:
                    stop_transmit()
                auto_started = False

            with state_lock:
                transmitting = tx_active
                if transmitting:
                    send_audio_frame(audio)
            if transmitting:
                note_tx_frame()
                record_frame(audio)
                emit_event("audio_level", level=int(rms / 100))
    finally:
        try:
            if stream.is_active():
                stream.stop_stream()
            stream.close()
        except Exception:
            pass


def manual_transmit_loop(generation, tx_number):
    """Send the microphone audio of transmission `tx_number`, then send its end frame.

    The loop belongs to one transmission only: it ends as soon as that
    transmission ends, even when a new one has already started, so two
    microphone loops never send audio at the same time. Whatever ends the
    loop (the PTT, the time-out or a microphone failure), its last step is
    sending the end frame, so the server always learns that the
    transmission is over.
    """
    global start_time
    try:
        stream = open_audio_stream(want_input=True, frames_per_buffer=FRAME_SAMPLES * 7)
    except Exception as exc:
        log.error("The input audio device cannot be opened: %s", exc)
        emit_event("error", title=tr("audio.title"), message=tr("audio.input_failed").format(exc))
        stop_transmit(send_end_frame=False, log_it=False)
        return

    try:
        start_time = time()
        while transmission_is_current(tx_number) and connection_is_current(generation):
            try:
                audio = stream.read(FRAME_SAMPLES, exception_on_overflow=False)
            except OSError as exc:
                log.error("The input audio device stopped working: %s", exc)
                emit_event("error", title=tr("audio.title"), message=tr("audio.input_failed").format(exc))
                # The end frame is sent below, when the loop finishes.
                stop_transmit()
                break
            with state_lock:
                if not transmission_is_current(tx_number):
                    break
                send_audio_frame(audio)
            note_tx_frame()
            record_frame(audio)
            emit_event("audio_level", level=int(pcm_rms(audio) / 100))
    finally:
        try:
            if stream.is_active():
                stream.stop_stream()
            stream.close()
        except Exception:
            pass
        if session_active and udp is not None:
            send_end_of_transmission()


# ---------------------------------------------------------------------------
# Station lookups
# ---------------------------------------------------------------------------

def station_lookup_loop():
    """Look up the picture and identity of every callsign put in lookup_queue, one at a time."""
    while not lookups_stopped:
        try:
            (_callsign, name) = lookup_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            lookup_station(_callsign, name)
        except Exception:
            log.exception("Station lookup failed for %s", _callsign)


# ---------------------------------------------------------------------------
# HTTP services
# ---------------------------------------------------------------------------

def post_eqsl_adif(user, password, adif_text):
    """Upload ADIF text to eQSL.cc as a file (multipart POST) and return the page text.

    The text keeps one line per line of the page, because eQSL writes one
    warning line for every record it did not add. Raises
    requests.exceptions.RequestException on network errors.
    """
    response = http_session.post(
        "https://www.eQSL.cc/qslcard/ImportADIF.cfm",
        data={"EQSL_USER": user, "EQSL_PSWD": password},
        files={"Filename": ("logbook.adi", adif_text.encode("ascii", "replace"), "text/plain")},
        headers=http_headers(),
        timeout=(10, 120),
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser").get_text("\n", strip=True)


def qrz_api_call(post_data):
    """Call the QRZ.com Logbook API and return its answer as a dictionary.

    A server answer is parsed into its fields (RESULT, REASON, LOGID, ...).
    Network failures are returned as {"RESULT": "ERROR", "REASON": text}.
    """
    api_url = "https://logbook.qrz.com/api"
    try:
        resp = http_session.post(
            api_url,
            headers=http_headers({"Content-Type": "application/x-www-form-urlencoded"}),
            data=post_data,
            timeout=HTTP_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        return {"RESULT": "ERROR", "REASON": "The QRZ.com server did not answer in time."}
    except requests.exceptions.ConnectionError:
        return {"RESULT": "ERROR", "REASON": "Unable to connect to logbook.qrz.com."}
    except requests.exceptions.RequestException as exc:
        return {"RESULT": "ERROR", "REASON": str(exc)}
    if resp.status_code != 200:
        return {"RESULT": "ERROR", "REASON": "QRZ.com returned HTTP %s." % resp.status_code}
    return parse_qrz_response(resp.text)


def parse_qrz_response(text):
    """Turn a QRZ.com API answer such as "RESULT=OK&LOGIDS=12&COUNT=1" into a dictionary."""
    fields = {key.upper(): values[0] for key, values in urllib.parse.parse_qs(str(text).strip(), keep_blank_values=True).items()}
    if not fields.get("RESULT"):
        fields["RESULT"] = "ERROR"
        fields.setdefault("REASON", "The QRZ.com server returned an empty answer.")
    if "LOGID" not in fields and "LOGIDS" in fields:
        fields["LOGID"] = fields["LOGIDS"]
    return fields


def master_of_server(server):
    """Master address of the server called `server` in masters.json, or "" when unknown."""
    for item in server_list or []:
        if isinstance(item, dict) and item.get("name") == server:
            return str(item.get("master", ""))
    return ""
