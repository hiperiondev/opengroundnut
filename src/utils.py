# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Small helpers with no shared state: access code, audio devices and serial ports."""

import pyaudio
import serial
import serial.tools.list_ports


def access_code_for(callsign):
    """Peanut access code of a callsign, as a decimal text.

    The code is the CRC-16/CCITT-FALSE checksum (polynomial 0x1021, start
    value 0xFFFF) of the text "FELINE" followed by the callsign. The code
    depends on the exact text, so callsigns must be compared in upper case.
    """
    crc = 0xFFFF
    for byte in ("FELINE" + callsign).encode("latin-1", "replace"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return str(crc)


def audio_devices(portaudio=None):
    """Every audio device of the first host API as a list of dictionaries.

    Each dictionary holds "index" (the PyAudio device index used to open a
    stream), "name", "inputs" and "outputs" (channel counts).

    portaudio is the PyAudio instance the program already uses. Without one,
    a temporary instance is created for the query and released afterwards.
    """
    devices = []
    p = portaudio if portaudio is not None else pyaudio.PyAudio()
    try:
        info = p.get_host_api_info_by_index(0)
        for host_index in range(info.get("deviceCount", 0)):
            device = p.get_device_info_by_host_api_device_index(0, host_index)
            devices.append(
                {
                    "index": int(device.get("index", host_index)),
                    "name": str(device.get("name", "")),
                    "inputs": int(device.get("maxInputChannels", 0)),
                    "outputs": int(device.get("maxOutputChannels", 0)),
                }
            )
    finally:
        if portaudio is None:
            p.terminate()
    return devices


def list_audio_devices(want_input, portaudio=None):
    """Devices usable for capture (want_input=True) or playback, as "index:name" texts.

    portaudio is the PyAudio instance the program already uses, if any (see
    audio_devices).
    """
    key = "inputs" if want_input else "outputs"
    return ["{}:{}".format(device["index"], device["name"]) for device in audio_devices(portaudio) if device[key] > 0]


def serial_ports():
    """Names of the serial ports present on this computer, sorted.

    The operating system is asked for its list of ports; no port is opened,
    so no control line (RTS/DTR) is ever touched while listing them.
    """
    return sorted(port.device for port in serial.tools.list_ports.comports())


def open_serial_quiet(port_name):
    """Open a serial port with RTS and DTR low from the very first moment.

    A plain serial.Serial(port) raises RTS and DTR while opening, which keys
    any transmitter whose PTT is wired to one of those lines. Here the line
    states are set before the port is opened, so the radio stays unkeyed.
    """
    port = serial.Serial()
    port.port = port_name
    port.rtscts = False
    port.dsrdtr = False
    port.rts = False
    port.dtr = False
    port.open()
    return port
