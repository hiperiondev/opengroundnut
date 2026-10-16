# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Audio devices, transmission control (PTT), link state and recording."""

# Keep the loaded libasound and libjack (and the JACK message handler) alive
# for the whole run. They stay None until the silencer has been installed.
alsa_lib = None
jack_lib = None
_jack_message_handler = None

# The PortAudio instance used for every stream; created by start_application().
# It stays None when the sound system cannot be started.
p = None

# Worker thread that sends the microphone audio in Manual mode.
_tx_thread = None

# Number of the current (or last) transmission. Each transmission gets a new
# number, so a microphone loop knows when its own transmission has ended.
_tx_number = 0

# Clock reading (monotonic seconds) when the current transmission started.
_tx_started = 0.0

# Until this monotonic time, VOX and serial squelch do not start a transmission.
# It gives the radio time to return to receive after the network audio ended.
_ptt_hold_until = 0.0


def silence_audio_library_messages():
    """Mute the C-level messages of ALSA and JACK for the whole life of the program.

    ALSA prints lines such as "Unknown PCM cards.pcm.rear", and JACK lines
    such as "jack server is not running", every time PortAudio probes or
    opens a device. That happens again for every stream and every device
    list, so the handlers stay installed for the whole run. The messages
    are only noise for users: real audio problems are reported by PortAudio
    itself.

    It is safe to call more than once, and it does nothing for a library
    that cannot be found (Windows, macOS, Linux without JACK).
    """
    global alsa_lib, jack_lib, _jack_message_handler
    from ctypes.util import find_library

    if alsa_lib is None:
        try:
            library_name = find_library("asound")
            if library_name:
                lib = cdll.LoadLibrary(library_name)
                lib.snd_lib_error_set_handler(c_error_handler)
                alsa_lib = lib
        except (OSError, AttributeError):
            # Muting the messages is only cosmetic, so never stop the app for it.
            pass

    if jack_lib is None:
        try:
            library_name = find_library("jack")
            if library_name:
                lib = cdll.LoadLibrary(library_name)
                handler = CFUNCTYPE(None, c_char_p)(lambda _message: None)
                lib.jack_set_error_function(handler)
                lib.jack_set_info_function(handler)
                _jack_message_handler = handler
                jack_lib = lib
        except (OSError, AttributeError):
            pass


# ---------------------------------------------------------------------------
# Audio devices
# ---------------------------------------------------------------------------

def _split_device_setting(saved):
    """Split a saved device text "index:name" into (index or None, name)."""
    text = str(saved or "").strip()
    if not text:
        return (None, "")
    head, separator, name = text.partition(":")
    if separator and head.strip().isdigit():
        return (int(head), name.strip())
    return (None, text)


# PyAudio device index found for each (saved setting, input?) pair. Looking a
# device up means asking PortAudio for every device, which can take a long
# time, so it is done once and not on every PTT press. forget_audio_devices()
# empties it when the settings change or a device stops working.
_audio_device_cache = {}


def forget_audio_devices():
    """Look the audio devices up again the next time a stream is opened."""
    _audio_device_cache.clear()


def resolve_audio_device(saved, want_input):
    """PyAudio device index for a saved "index:name" setting, or None for the system default.

    Device numbers change between computers and when devices are plugged in
    or out, so the device is looked up by name first, then by number. When
    neither matches a device that can record (or play), the system default
    device is used. The answer is remembered (see _audio_device_cache).
    """
    cache_key = (str(saved or ""), bool(want_input))
    if cache_key in _audio_device_cache:
        return _audio_device_cache[cache_key]
    index, name = _split_device_setting(saved)
    if index is None and not name:
        return None
    key = "inputs" if want_input else "outputs"
    try:
        devices = [device for device in utils.audio_devices(p) if device[key] > 0]
    except Exception as exc:
        log.warning("The audio device list is not available: %s", exc)
        return index
    found = None
    for device in devices:
        if name and device["name"] == name:
            found = device["index"]
            break
    else:
        for device in devices:
            if index is not None and device["index"] == index:
                found = device["index"]
                break
    if found is None:
        log.warning("Audio device %r is not available; the system default device is used.", saved)
    _audio_device_cache[cache_key] = found
    return found


def rescan_audio_devices():
    """List the audio devices again, including ones plugged in after the program started.

    PortAudio only looks for devices when it starts, so it is restarted
    here. That is only safe while no audio stream is open, so nothing is
    restarted while connected or while an audio thread still runs; the
    devices known so far are listed instead. Returns (inputs, outputs) as
    lists of "index:name" texts.
    """
    global p
    streams_in_use = session_active or any(
        thread is not None and thread.is_alive()
        for thread in (globals().get("_rx_thread"), globals().get("_vox_thread"), _tx_thread)
    )
    if not streams_in_use:
        if p is not None:
            try:
                p.terminate()
            except Exception:
                pass
        try:
            p = pyaudio.PyAudio()
        except Exception as exc:
            p = None
            log.error("The sound system cannot be started again: %s", exc)
            emit_event("error", title=tr("audio.title"), message=tr("audio.unavailable") + "\n" + str(exc))
            return ([], [])
    forget_audio_devices()
    try:
        return (utils.list_audio_devices(True, p), utils.list_audio_devices(False, p))
    except Exception as exc:
        log.warning("Unable to list audio devices: %s", exc)
        return ([], [])


def open_audio_stream(want_input, frames_per_buffer):
    """Open an 8 kHz, 16-bit mono stream on the configured input or output device.

    When the configured device cannot be opened, the system default device
    is tried before giving up. Raises the PortAudio error when no device
    works, and OSError when the sound system could not be started at all.
    """
    if p is None:
        raise OSError(tr("audio.unavailable"))
    saved = input_device if want_input else output_device
    device = resolve_audio_device(saved, want_input)
    options = {
        "format": pyaudio.paInt16,
        "channels": 1,
        "rate": SAMPLE_RATE,
        "frames_per_buffer": frames_per_buffer,
    }
    if want_input:
        options.update(input=True, input_device_index=device)
    else:
        options.update(output=True, output_device_index=device)
    try:
        return p.open(**options)
    except Exception as first_error:
        if device is None:
            raise
        log.warning("Audio device %r failed (%s); trying the system default device.", saved, first_error)
        # The device may come back later (plugged in again), so it is looked up afresh next time.
        forget_audio_devices()
        options["input_device_index" if want_input else "output_device_index"] = None
        stream = p.open(**options)
        emit_event("warning", title=tr("audio.title"), message=tr("audio.device_fallback").format(saved))
        return stream


def report_audio_failure(exc, generation):
    """The speaker of a connection could not be opened or stopped working: tell the user and disconnect."""
    log.error("The output audio device cannot be opened: %s", exc)
    emit_event("error", title=tr("audio.title"), message=tr("audio.output_failed").format(exc))
    if generation == connection_generation and session_active:
        disconnect_from_server()


def play_wave(wav_path):
    """Play a WAV file on the configured output device; problems are only logged."""
    if p is None:
        return
    try:
        with wave.open(wav_path, "rb") as f:
            device = resolve_audio_device(output_device, want_input=False)
            stream = p.open(
                format=p.get_format_from_width(f.getsampwidth()),
                channels=f.getnchannels(),
                rate=f.getframerate(),
                output=True,
                output_device_index=device,
            )
            try:
                data = f.readframes(1024)
                while data:
                    stream.write(data)
                    data = f.readframes(1024)
            finally:
                stream.stop_stream()
                stream.close()
    except Exception as exc:
        log.warning("Unable to play %s: %s", wav_path, exc)


# ---------------------------------------------------------------------------
# Transmission (PTT)
# ---------------------------------------------------------------------------

def transmission_is_current(tx_number):
    """True while transmission number `tx_number` is the one in progress."""
    return tx_active and tx_number == _tx_number


def start_transmit():
    """Start transmitting. Returns True when a transmission started.

    Only possible while the server has accepted us and no transmission is on.
    In Manual mode the microphone loop of the previous transmission must
    have finished first (it sends that transmission's end frame); a press
    that comes before that is ignored.
    """
    global tx_active, session_id, start_time_ptt, ptt_pressed, tx_sequence, _tx_started, _tx_thread, _tx_number
    previous = _tx_thread
    if previous is not None and previous.is_alive() and previous is not threading.current_thread():
        previous.join(timeout=0.5)
        if previous.is_alive():
            log.warning("The previous transmission is still closing; the PTT press is ignored.")
            return False

    with state_lock:
        if ptt_pressed or not (session_active and link_up):
            return False
        ptt_pressed = True
        tx_active = True
        session_id = random.randrange(1, 254)
        tx_sequence = 0
        start_time_ptt = time()
        _tx_started = monotonic()
        _tx_number += 1
        tx_number = _tx_number

    # Show our own station card while we talk.
    lookup_queue.put((my_call, ""))

    # Read the persisted APRS enable flag from the saved configuration,
    # which is safe from the VOX and audio worker threads.
    try:
        aprs_enabled = config.getint("aprs", "enabled", fallback=0)
    except (AttributeError, ValueError):
        aprs_enabled = 0
    if aprs_enabled == 1:
        start_worker(aprs_send_thread, name="aprs-beacon")

    if rx_mode == "Manual":
        _tx_thread = start_worker(manual_transmit_loop, connection_generation, tx_number, name="tx-audio")
    return True


def stop_transmit(send_end_frame=True, wait=False, log_it=True):
    """End the transmission in progress. Returns True when one was ended.

    In Manual mode the microphone thread sends the end frame itself when it
    stops; with wait=True this call waits (briefly) until it has done so.
    In the other modes the end frame is sent here. log_it=False leaves the
    transmission out of the "Last heard" list (used when it never really
    started, for example because the microphone could not be opened).
    """
    global tx_active, ptt_pressed
    with state_lock:
        if not ptt_pressed:
            return False
        ptt_pressed = False
        tx_active = False

    apply_link_state(0)
    tx_thread = _tx_thread
    if rx_mode == "Manual" and tx_thread is not None and tx_thread.is_alive():
        if wait and tx_thread is not threading.current_thread():
            tx_thread.join(timeout=1.5)
    elif send_end_frame and session_active:
        send_end_of_transmission()
    if log_it:
        log_end_of_transmission(callsign, active_room, start_time_ptt, monotonic() - _tx_started)
    return True


def toggle_transmit():
    """The PTT action: start transmitting, or end the transmission in progress."""
    if ptt_pressed:
        stop_transmit()
    else:
        start_transmit()


def _ptt_on_hold():
    """True while the radio is still returning to receive after network audio."""
    return monotonic() < _ptt_hold_until


def auto_ptt_start():
    """VOX or the squelch line asks to transmit. Returns True when a transmission started.

    Refused while the room is being heard and during the return hold that
    lets the radio go back to receive; the caller simply asks again on the
    next audio frame.
    """
    if ptt_pressed or not ptt_allowed or _ptt_on_hold():
        return False
    return start_transmit()


def read_squelch_line():
    """State of the serial squelch line chosen in RX control (True = a station is heard).

    Returns False when no serial port is open. Raises OSError or
    serial.SerialException when the port stops working.
    """
    port_rx = serial_rx
    if port_rx is None or not port_rx.is_open:
        return False
    if rx_mode == "Serial CD":
        return bool(port_rx.getCD())
    if rx_mode == "Serial CTS":
        return bool(port_rx.getCTS())
    if rx_mode == "Serial DSR":
        return bool(port_rx.getDSR())
    return False


def check_tx_timeout():
    """End the transmission in progress once it reaches the transmit time-out."""
    if ptt_pressed and monotonic() - _tx_started >= tx_timeout_seconds():
        log.info("Transmit time-out reached; the transmission ends.")
        stop_transmit()


# ---------------------------------------------------------------------------
# Link state (idle / receiving / transmitting)
# ---------------------------------------------------------------------------

def _set_serial_tx_line(active):
    """Key (True) or release (False) the radio through the configured serial TX line."""
    port_tx = serial_tx
    if not tx_mode.startswith("Serial") or port_tx is None or not port_tx.is_open:
        return False
    try:
        if tx_mode == "Serial RTS":
            port_tx.rts = bool(active)
        elif tx_mode == "Serial DTR":
            port_tx.dtr = bool(active)
        else:
            return False
    except (OSError, serial.SerialException) as exc:
        log.warning("Unable to change the serial PTT line: %s", exc)
        return False
    return True


def apply_link_state(status):
    """Apply a new link state: 0 idle, 1 receiving, 2 transmitting.

    Updates the PTT permission and the serial PTT line, and publishes the
    new state (with the text that describes it) as a "ptt_state" event.
    While the room is heard the radio is keyed through the serial TX line,
    so a radio link repeats the network audio on the air. With the speaker
    muted the line stays released: the radio would only send a silent carrier.
    """
    global ptt_allowed, link_state, _ptt_hold_until
    link_state = status
    if status == 1:
        ptt_allowed = False
        caption = heard_call + " → " + str(active_room or "")
        emit_event("ptt_state", status=1, caption=caption, enabled=False)
        _set_serial_tx_line(not speaker_muted)
    elif status == 2:
        ptt_allowed = True
        caption = callsign + " → " + str(active_room or "")
        emit_event("ptt_state", status=2, caption=caption, enabled=True)
    else:
        ptt_allowed = bool(session_active and link_up)
        emit_event("ptt_state", status=0, caption=str(my_call), enabled=ptt_allowed)
        emit_event("audio_level", level=0)
        if _set_serial_tx_line(False):
            # vox_return is in tenths of a second.
            _ptt_hold_until = monotonic() + max(0, int(vox_return_setting)) / 10.0


def note_tx_frame():
    """Note that one of our audio frames was just sent."""
    global last_tx_ms
    last_tx_ms = monotonic_ms()


def note_rx_frame():
    """Note that an audio frame from the room was just received."""
    global last_rx_ms
    last_rx_ms = monotonic_ms()


def update_link_state():
    """Work out the link state from the latest RX and TX frames and apply it when it changes."""
    global link_status, previous_link_status, last_rx_ms, last_tx_ms
    now = monotonic_ms()
    if now - last_rx_ms < 600:
        link_status = 1
        last_tx_ms = 0
    elif now - last_tx_ms < 600:
        link_status = 2
        last_rx_ms = 0
    else:
        link_status = 0
        last_rx_ms = 0
        last_tx_ms = 0
    if link_status != previous_link_status:
        previous_link_status = link_status
        apply_link_state(link_status)


def _status_monitor():
    """Background loop: link state every 10 ms and the transmit time-out."""
    while not app_closing:
        try:
            update_link_state()
            check_tx_timeout()
        except Exception:
            log.exception("Status monitor error")
        sleep(0.01)


def start_status_monitor():
    """Start the link state and transmit time-out monitor thread."""
    threading.Thread(target=_status_monitor, name="status-monitor", daemon=True).start()


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

# Open WAV file receiving the recording, its temporary path and its length.
_recording_file = None
_recording_path = None
_recorded_frames = 0
_recording_lock = threading.Lock()


def start_recording():
    """Start recording every audio frame sent or received into a temporary WAV file."""
    global recording_enabled, recording_active, _recording_file, _recording_path, _recorded_frames
    with _recording_lock:
        _discard_recording_locked()
        handle, temp_path = tempfile.mkstemp(prefix="peanut-rec-", suffix=".wav")
        os.close(handle)
        recording = wave.open(temp_path, "wb")
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(SAMPLE_RATE)
        _recording_file = recording
        _recording_path = temp_path
        _recorded_frames = 0
        recording_active = True
        recording_enabled = True


def record_frame(pcm):
    """Append one audio frame to the recording, when a recording is on."""
    global _recorded_frames
    if not recording_enabled:
        return
    with _recording_lock:
        if _recording_file is None or _recorded_frames >= RECORDING_MAX_SECONDS * SAMPLE_RATE:
            return
        try:
            _recording_file.writeframes(pcm)
            _recorded_frames += len(pcm) // 2
        except (OSError, wave.Error) as exc:
            log.warning("Recording stopped: %s", exc)
            _discard_recording_locked()


def _discard_recording_locked():
    """Close and delete the temporary recording (the caller holds _recording_lock)."""
    global recording_enabled, recording_active, _recording_file, _recording_path, _recorded_frames
    recording_enabled = False
    recording_active = False
    if _recording_file is not None:
        try:
            _recording_file.close()
        except (OSError, wave.Error):
            pass
    if _recording_path and os.path.exists(_recording_path):
        try:
            os.remove(_recording_path)
        except OSError:
            pass
    _recording_file = None
    _recording_path = None
    _recorded_frames = 0


def stop_recording():
    """Stop recording and drop the audio recorded so far."""
    with _recording_lock:
        _discard_recording_locked()


def has_recorded_audio():
    """True when the recording holds at least one audio frame."""
    return _recorded_frames > 0


def save_recording(file_name):
    """Stop recording and store the recording as a WAV file (8 kHz, 16 bit, mono).

    Raises OSError (or wave.Error) when the file cannot be written; the
    recording is dropped either way.
    """
    global recording_enabled, recording_active, _recording_file
    with _recording_lock:
        recording_enabled = False
        recording_active = False
        try:
            if _recording_file is not None:
                _recording_file.close()
                _recording_file = None
            shutil.copyfile(_recording_path, file_name)
        finally:
            _discard_recording_locked()
