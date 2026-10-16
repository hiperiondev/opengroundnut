# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Tests of the application core (no window, no sound card, no network)."""

from conftest import load_core


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

def test_access_code_depends_on_upper_case_callsign(core):
    code = core["utils"].access_code_for("W1AW")
    assert code == "49966"
    assert core["utils"].access_code_for("w1aw") != code


def test_text_fields_are_ascii_and_right_aligned(core):
    assert core["ascii_field"]("Café", 8) == "    Cafe"
    assert core["ascii_field"]("ABCDEFGHIJ", 8) == "ABCDEFGH"


def test_voice_frame_header_layout(core):
    core["callsign"] = "DL9ABC"
    core["active_room"] = "TEST"
    core["dmr_id"] = 0x123456
    core["tx_sequence"] = 0x0102
    core["session_id"] = 7
    header = bytes(core["_dpcm_header"](core["FRAME_TYPE_AUDIO"]))
    assert len(header) == core["DPCM_HEADER_SIZE"] == 30
    assert header[:4] == b"DPCM"
    assert header[4:12] == b"  DL9ABC"
    assert header[12:20] == b"    TEST"
    assert header[22:25] == bytes((0x12, 0x34, 0x56))
    assert header[25:27] == bytes((0x02, 0x01))
    assert header[28] == 1 and header[29] == 7


def test_audio_level_of_silence_and_full_scale(core):
    assert core["pcm_rms"](bytes(320)) == 0
    assert core["pcm_rms"](b"\xff\x7f" * 160) == 32767


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def test_fresh_settings_use_the_defaults(core):
    assert core["my_call"] == "NOCALL"
    assert core["rx_mode"] == "Manual"
    assert core["tx_timeout_setting"] == "180"
    assert core["config_warnings"] == []


def test_invalid_stored_value_falls_back_and_warns(core):
    core["config"].set("tx_control", "timeout", "abc")
    core["config"].save()
    core["load_settings"]()
    assert core["tx_timeout_setting"] == "180"
    assert ("storage.value_invalid", ("tx_control", "timeout", "abc")) in core["config_warnings"]


def _valid_form():
    return {
        "form_callsign": "DL9ABC", "form_scale_value": 1, "form_rx_mode": "Manual", "form_tx_mode": "Manual",
        "vox_threshold": 200, "vox_delay": 50, "vox_return": 5, "form_tx_timeout": 180, "form_dmr_id": "",
    }


def test_unknown_settings_are_dropped(core):
    merged = core["_merge_settings"]({"general": {"unused": 1, "callsign": "DL9ABC"}, "extra": {"a": 1}})
    assert "unused" not in merged["general"]
    assert "extra" not in merged
    assert merged["general"]["callsign"] == "DL9ABC"
    assert merged["general"]["language"] == "en"


def test_settings_form_validation(core):
    assert core["validate_setup"](_valid_form()) is None
    bad_mode = dict(_valid_form(), form_rx_mode="Bad")
    assert core["validate_setup"](bad_mode) == (core["tr"]("form.rx_mode_invalid"), "form_rx_mode")
    serial_without_port = dict(_valid_form(), form_tx_mode="Serial RTS")
    assert core["validate_setup"](serial_without_port) == (core["tr"]("form.tx_port_missing"), "form_tx_port")
    shortest_tot = dict(_valid_form(), form_tx_timeout=30)
    assert core["validate_setup"](shortest_tot) is None
    assert "30" in core["TOT_VALUES"]


# ---------------------------------------------------------------------------
# Logbook, ADIF and uploads
# ---------------------------------------------------------------------------

def test_logbook_record_round_trip_and_adif(core):
    core["callsign"] = "DL9ABC"
    core["logbook_save_record"]({
        "callsign": "OH2ABC", "name": "Zoë", "date": "2024-03-15", "time": "14:20",
        "band": "2m", "frequency": "144.8", "comment": "Grüße",
    })
    rows = core["logbook_rows"]()
    assert rows[0][:5] == ("OH2ABC", "Zoë", "2024-03-15", "14:20", "2m")
    assert core["count_pending_uploads"]("qrz") == 1
    adif = core["export_adif_text"]()
    assert "<CALL:6>OH2ABC" in adif
    assert "<NAME:3>Zoe" in adif
    assert "<QSO_DATE:8>20240315" in adif
    assert "<MODE:12>DIGITALVOICE" in adif
    assert adif.rstrip().endswith("<EOR>")


def test_eqsl_answer_counts_only_duplicate_warnings(core):
    complete = core["eqsl_upload_complete"]
    assert complete("Result: 2 out of 2 records added", 2)
    assert complete("Result: 1 out of 2 records added\nWarning: Y=2024 OH2ABC Bad record: Duplicate", 2)
    assert not complete("Result: 1 out of 2 records added\nNote: duplicates are ignored\nError: bad band", 2)
    assert not complete("Result: 1 out of 1 records added", 2)


def test_qrz_answer_parsing(core):
    fields = core["parse_qrz_response"]("RESULT=OK&LOGIDS=12&COUNT=1")
    assert fields["RESULT"] == "OK" and fields["LOGID"] == "12"
    assert core["parse_qrz_response"]("")["RESULT"] == "ERROR"


# ---------------------------------------------------------------------------
# Callsigns, APRS, rooms and alarms
# ---------------------------------------------------------------------------

def test_prefix_table_finds_the_longest_prefix(core):
    expected = {
        "DL9ABC": "de", "OH2ABC": "fi", "JA1ABC": "jp", "VK2ABC": "au", "4A1ABC": "mx", "4F1ABC": "ph",
        "AT2ABC": "in", "HF0POL": "pl", "YM1ABC": "tr", "7Z1AB": "sa", "XM1ABC": "ca",
        "TM1ABC": "fr", "B1ABC": "cn", "KH6AB": "us", "W1AW": "us", "M0ABC": "gb-eng", "GW4ABC": "gb-wls",
    }
    for call, flag in expected.items():
        entry = core["prefix_info"](call)
        assert entry.get("flag") == flag, call
        assert core["flag_picture_path"](flag) is not None, flag


def test_aprs_packet(core):
    packet = core["aprs_string"]("DL9ABC-9", -12.5, -45.25, core["APRS_SSID"])
    assert packet.startswith("DL9ABC-10>APZPNT,TCPIP*:@")
    assert "1230.00S/04515.00W-" in packet


def test_room_does_not_change_during_own_transmission(core):
    events = []
    core["set_event_listener"](lambda name, **data: events.append(name))
    core["ptt_pressed"] = True
    assert core["enter_room"]("OTHER") is False
    assert events[-1] == "warning"
    core["ptt_pressed"] = False
    assert core["enter_room"]("OTHER") is True
    assert core["active_room"] == "OTHER"


def test_every_device_type_is_listed(core):
    whois = [
        {"Call": "OH2ABC", "room": "R1", "device": "WINDOWS"},
        {"Call": "W1AW", "room": "R1", "device": "HOTSPOT"},
        {"room": "R1", "device": "ANDROID"},
    ]
    assert [item["Call"] for item in core["_visible_stations"](whois)] == ["OH2ABC", "W1AW"]


def test_first_online_check_is_a_silent_baseline(core):
    core["set_event_listener"](lambda name, **data: None)
    core["_merge_alarm_calls"](["OH2ABC", "W1AW"])
    core["_update_alarms"]({"OH2ABC": "R1"}, baseline=True)
    assert core["alarm_history"] == {}
    core["_update_alarms"]({"W1AW": "R2"})
    changes = sorted((entry["callsign"], entry["state"]) for entry in core["alarm_history"].values())
    assert changes == [("OH2ABC", "off"), ("W1AW", "on")]


def test_plain_http_is_not_used_after_a_proxy_refusal(core):
    requests = core["requests"]
    refused = requests.exceptions.ConnectionError(ConnectionRefusedError(111, "refused"))
    proxy = requests.exceptions.ProxyError(ConnectionRefusedError(111, "refused"))
    timeout = requests.exceptions.ConnectTimeout("timed out")
    assert core["_https_port_refused"](refused)
    assert not core["_https_port_refused"](proxy)
    assert not core["_https_port_refused"](timeout)
