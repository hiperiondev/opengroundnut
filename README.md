# OpenGroundnut

**OpenGroundnut** is a desktop client for the **Peanut** amateur-radio voice network, written in Python with a
CustomTkinter interface. It runs on **Linux** (including Raspberry Pi OS), **Windows** and **macOS**.

With OpenGroundnut a licensed radio amateur can:

- talk in Peanut rooms straight from the computer (microphone and speaker);
- link a real radio to a Peanut room, with transmission started by **VOX** or by a **serial squelch line**, and the
  radio keyed through a **serial RTS/DTR PTT line**;
- watch the whole network live (who is talking, in which room, with which message);
- scan a list of rooms automatically;
- be alerted when chosen callsigns join or leave the network;
- record the audio of a session to a WAV file;
- keep a logbook, export it as **ADIF**, and upload it to **eQSL.cc** and the **QRZ.com Logbook**;
- see the picture, flag, name, location and DMR ID of every station that talks;
- send the station position to **APRS-IS** while transmitting.

Program version: **1.0** · Peanut protocol version reported to the server: **0.11**

---

## Table of contents

1. [What Peanut is](#what-peanut-is)
2. [Features in detail](#features-in-detail)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [First start](#first-start)
6. [Running the program](#running-the-program)
7. [The window, tab by tab](#the-window-tab-by-tab)
8. [Linking a radio (RX control / TX control)](#linking-a-radio-rx-control--tx-control)
9. [Room scanner](#room-scanner)
10. [Callsign alarms](#callsign-alarms)
11. [Recording](#recording)
12. [Logbook, ADIF, eQSL and QRZ.com](#logbook-adif-eqsl-and-qrzcom)
13. [Station information (pictures, flags, RadioID)](#station-information-pictures-flags-radioid)
14. [APRS position beacon](#aprs-position-beacon)
15. [Settings reference (`settings.json`)](#settings-reference-settingsjson)
16. [Where your data is kept](#where-your-data-is-kept)
17. [Network services used](#network-services-used)
18. [Peanut protocol overview](#peanut-protocol-overview)
19. [Architecture](#architecture)
20. [Project layout](#project-layout)
21. [Development](#development)
22. [Building a stand-alone program](#building-a-stand-alone-program)
23. [Building a release zip](#building-a-release-zip)
24. [Adding a language](#adding-a-language)
25. [Troubleshooting](#troubleshooting)
26. [Credits and licenses](#credits-and-licenses)

---

## What Peanut is

Peanut is an Internet push-to-talk network for licensed radio amateurs. Stations connect to a **master server**,
enter a **room** and talk to every other station in that room; some rooms are linked to other digital-voice systems.
The list of master servers is published at `www.pa7lim.nl/masters.json`; each master publishes its own room list,
active transmissions and connected stations over HTTP, and carries the voice over UDP.

To log in you need:

- an amateur-radio **callsign**, and
- the **Peanut access code** that belongs to that callsign (registration: `www.pa7lim.nl/peanut`).

A DMR ID is optional and does **not** replace the access code.

---

## Features in detail

| Area | What it does |
| --- | --- |
| Voice | 8 kHz, 16-bit, mono audio in 20 ms frames, sent and received over UDP. A jitter (play-out) buffer absorbs network delays; a short 600 Hz "roger beep" can be played when another station stops talking. |
| Connection | Login retried every 2 s (up to 5 times) until the server answers; a watchdog detects a silent server (no PING for 15 s) and reconnects automatically 10 s later, repeating until it succeeds or the user cancels. |
| Rooms | Rooms grouped by **PEANUT** (every non-local room), **ALL**, **BOOKMARKS** (your favorites on the current server) and by country. Room list refreshed every 10 minutes and on every connection. |
| Monitor | Live table of every transmission in progress on the server, filterable by group, refreshed every second. Double-click a row to jump to that room. |
| Radio link | RX control: Manual, VOX, Serial CD, Serial CTS, Serial DSR. TX control: Manual, Serial RTS, Serial DTR. Configurable VOX threshold, hang time, return hold and transmit time-out (30–300 s). |
| PTT | On-screen PTT button, or optional **Ctrl key PTT** (tap Ctrl alone to start, tap again to stop). |
| Scanner | Rotates through a chosen list of rooms; stops on activity and resumes 5 s after the last voice frame. |
| Alarms | Watches a list of callsigns and logs (with sound and notification) when they come online or go offline. |
| Recording | Records every frame sent and received to a WAV file (up to 4 hours). |
| Logbook | Add / edit / delete QSOs, duplicate warning, ADIF 3.1.4 export, eQSL.cc upload, QRZ.com Logbook API upload, per-service "already uploaded" tracking. |
| Station info | QRZ.com picture (XML service or public page), country flag from the callsign prefix (1,284 prefixes), name/city/country and DMR ID from the RadioID user list. |
| APRS | Position beacon to APRS-IS as `<CALL>-10` at the start of a transmission, at most once every 30 minutes. |
| Interface | Light theme, Orbitron fonts, 6 languages (English, Deutsch, Español, Français, Italiano, Português), UI scale 1–3 (or any fraction via an environment variable), "always on top" option. |
| Robustness | Settings and logbook written atomically (never half-written), unreadable files set aside as `.bak`, every error logged to `peanut.log`, audio devices fall back to the system default when the chosen one is missing. |

---

## Requirements

### Software

- **Python 3.9 or newer**, with **Tk** support (`tkinter`).
  - On **Windows** use **Python 3.9 to 3.13**: PyAudio publishes ready-made Windows packages only for those versions.
- **PortAudio** (the C library behind PyAudio). Bundled in the Windows PyAudio wheels; on Linux and macOS it is a
  system package.

### Hardware

- A sound card: microphone + speaker/headphones, or the audio interface of your radio link.
- Optional: a serial port (USB-serial adapter or built-in) for squelch detection and/or PTT keying.

### Python packages

Installed automatically by the install scripts from `requirements.txt`:

| Package | Version | Used for |
| --- | --- | --- |
| `customtkinter` | `>=5.2,<5.3` | The window and widgets (scaling and options change between major versions, hence the pin). |
| `Pillow` | `>=10.0` | Pictures, flags, icons. |
| `PyAudio` | `>=0.2.14,<0.3` | Audio capture and playback (PortAudio). |
| `pyserial` | `>=3.5,<4` | Serial squelch input and PTT output. |
| `requests` | `>=2.28,<3` | Every HTTP request. |
| `tinydb` | `>=4.8,<5` | Every piece of stored data (settings, logbook, bookmarks, RadioID list). |
| `aprslib` | `>=0.7,<0.8` | APRS-IS login, passcode and position encoding. |
| `beautifulsoup4` | `>=4.11,<5` | Reading eQSL.cc answers and public QRZ.com pages. |
| `xmltodict` | `>=0.13,<1` | QRZ.com XML data service. |

If a package is missing at start-up, the program shows (in the console and in a message window) the exact pip
package name and the command to install the requirements.

---

## Installation

Both installers create a **private Python environment in `.venv` inside the program folder**. Nothing is installed
system-wide, and deleting the folder removes everything. Run the installer once, and again after updating the program.

First get the program, either by cloning the repository or by downloading and unpacking a release zip:

```bash
git clone https://github.com/<your-account>/opengroundnut.git
cd opengroundnut
```

### Linux (Debian, Ubuntu, Raspberry Pi OS)

```bash
sudo apt install python3-venv python3-tk python3-dev portaudio19-dev
./install_linux.sh
```

### Linux (Fedora)

```bash
sudo dnf install python3-tkinter python3-devel portaudio-devel
./install_linux.sh
```

`install_linux.sh` checks that Python 3.9+ and Tk are present, creates `.venv`, upgrades pip, installs
`requirements.txt` and makes `run_linux.sh` executable. If PyAudio fails to build, it tells you to install the
PortAudio development files and run it again.

### macOS

Python from [python.org](https://www.python.org/downloads/) already includes Tk. Install PortAudio with Homebrew, then
use the Linux installer (it works the same on macOS):

```bash
brew install portaudio
./install_linux.sh
```

### Windows

1. Install Python **3.13** (or any 3.9–3.13) from [python.org](https://www.python.org/downloads/), keeping the
   **"py launcher"** option selected (it is by default).
2. Double-click **`install_windows.bat`**.

The script looks for Python 3.13, 3.12, 3.11, 3.10 and 3.9, in that order, through the `py` launcher, and uses the
newest one found. If `.venv` already exists it is reused. If PyAudio cannot be installed (for example because `.venv`
was created with a Python newer than 3.13), delete the `.venv` folder, install Python 3.13 and run the script again.

### Manual installation (any system)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt     # Windows: .venv\Scripts\python.exe -m pip ...
.venv/bin/python opengroundnut.py
```

---

## First start

1. Start the program (see [Running the program](#running-the-program)).
2. A fresh installation starts in **English** with the callsign `NOCALL`. Open the **Settings** tab (the last tab).
3. In **General**:
   - **Callsign**: your callsign (3 to 8 characters: letters, digits and `/`).
   - **Access code**: your Peanut access code (the **Show** button reveals it while typing).
   - **Server**: the Peanut master server (default `peanut.pa7lim.nl`).
   - **Language**: choose your language.
   - **Input / Output**: the audio devices. Leave empty for the system default. The **↻** button next to *Input*
     lists the sound cards again (for example after plugging in a USB interface; only while disconnected).
   - Optionally a **Message** (up to 20 characters, shown next to your callsign while you talk) and your
     **DMR ID** (the **Look up** button finds it on radioid.net).
4. Press **Save**. Language and scale changes need a restart of the program.
5. Go back to **Main**, choose a group and a room, press **Connect**, and use the big callsign button as PTT.

If you try to connect before entering a callsign and a code, the program opens Settings → General and tells you what
is missing. If the code does not match the callsign, the connection is not attempted and an error is shown.

---

## Running the program

```bash
./run_linux.sh            # Linux and macOS
run_windows.bat           # Windows
```

On Windows, `run_windows.bat` without arguments starts the program with `pythonw.exe` (no console window). With any
argument it uses `python.exe`, so a console is available.

### Command-line options

| Option | Effect |
| --- | --- |
| `--debug` | Writes every Peanut UDP packet sent and received (ASCII and hex), and every scanner decision, to the log. Example: `./run_linux.sh --debug` |

### Environment variables

| Variable | Effect |
| --- | --- |
| `PEANUT_UI_SCALE` | Overrides the *Scale* setting for this run. Accepts fractions such as `1.25`; the value is limited to 0.65–3. Example: `PEANUT_UI_SCALE=1.25 ./run_linux.sh` |

When the window would not fit on the screen at the chosen scale, the scale is reduced automatically for that session
so the window (and its close button) always stay visible.

### Keyboard

| Key | Action |
| --- | --- |
| `Ctrl` (tap alone) | Start / stop transmitting, when **Ctrl key as PTT** is enabled. `Ctrl` used together with another key (`Ctrl+C`, `Ctrl+Q`, …) never touches the transmitter. |
| `Ctrl+Q` | Close the program. |
| `Delete` | Delete the selected logbook record (with confirmation); remove the selected entry in the alarm and scan editors. |
| `Enter` | Confirm the logbook form; add the typed callsign in the alarm editor. |

---

## The window, tab by tab

### Header

- Program name and version.
- **Status pill**: *Offline*, *Connecting · ROOM*, *Online · ROOM*, *Receiving · CALL*, *Transmitting · ROOM*,
  *Scanning · ROOM* or *Reconnecting …*.
- **UTC** and **local** clocks.

### Bottom bar (always visible)

- **Audio level meter** for the audio being received or sent.
- **PTT button**, labeled with your callsign. It is disabled until the server accepts the login, and while another
  station is being heard. While receiving it shows `CALL → ROOM`.
- **Timer**: counts up while receiving; while transmitting it counts **down** the transmit time-out and turns red in
  the last 30 seconds. The transmission is ended automatically when it reaches zero.
- **Mute** button for the received audio.

### Main

- **Station** card: picture, flag and country, callsign, DMR ID, name and location of the station being heard
  (your own station when idle).
  - Click the **picture** to open the station's QRZ.com page.
  - Click the **callsign** to add the station to the logbook.
  - The **bell** opens the callsign alarm editor.
- **My station** card:
  - **Group** (PEANUT, ALL, BOOKMARKS or a country) and **Room** selectors. Choosing a group only filters the list;
    the room is entered only when you pick a room.
  - **☆ / ★** adds or removes the selected room from the bookmarks of the current server (also on right-click).
  - **↻** loads the server and room lists again immediately.
  - **Connect / Disconnect**. While a reconnection is pending the button reads *Reconnecting … (click to cancel)*.
  - **REC** starts / stops a recording.
  - **SCAN** starts / stops the room scanner; **⋯** (or right-click on SCAN) opens the scan room editor.
- **Last heard**: time, callsign, name and duration of every transmission heard in this session. Double-click opens
  QRZ.com; right-click offers **QRZ.com**, **aprs.fi**, **Brandmeister**, **HamData** and **Add to the logbook**.
- **Stations in room**: stations connected to the current room (refreshed every 20 s). Double-click opens QRZ.com.

The room never changes in the middle of your own transmission: finish the transmission first.

### Monitor

Every transmission in progress on the server: callsign, message, room and start time (server time). The table is
only polled (once per second) while this tab is visible. The filter button ticks one or more groups; with none ticked,
every room is shown. **Double-click** a row to select that room on the Main tab and enter it.

### Logbook

The contact table (callsign, name, date, time, band, comment) and the buttons **Add**, **Edit**, **Remove**,
**Clear logbook** (deletes every contact), **ADIF**, **eQSL** and **QRZ**. Double-click a row to edit it. See
[Logbook, ADIF, eQSL and QRZ.com](#logbook-adif-eqsl-and-qrzcom).

### Alarm log

History of the watched callsigns going online / offline (callsign, state, UTC time, room), newest first. **Alarms**
opens the editor; **Clear** empties the history. The tab shows a badge when a new alarm arrives.

### Settings

Locked while connected. Sections:

| Section | Fields |
| --- | --- |
| **General** | Callsign, Message, DMR ID (+ Look up), Access code (+ Show/Hide), Server, Language, Scale; Input / Output audio device (+ ↻); Always on top; Roger beep; **Update the RadioID list** (downloads a fresh RadioID list). |
| **Online logbooks** | eQSL account (user name, password, QTH nickname); QRZ.com account (user name, password, Logbook API key). |
| **RX control** | Mode, VOX threshold, VOX hang time, Return hold, Serial port (+ ↻). Only the fields the chosen mode uses are enabled. |
| **TX control** | Mode, Serial port (+ ↻), TX time-out, Ctrl key as PTT. |
| **APRS** | Send my APRS position, Server, Port, Latitude, Longitude. |
| **Startup** | Room, Connect at startup. |

**Save** validates the whole form; the first invalid field is reported and focused. A code that does not match the
callsign is saved anyway, with a warning.

---

## Linking a radio (RX control / TX control)

A *radio link* repeats a Peanut room on the air: what the room says is transmitted by your radio, and what your radio
receives is sent to the room.

```
            network audio ──► sound card OUT ──► radio MIC/DATA IN
 Peanut     PTT while room heard ──► serial RTS or DTR ──► radio PTT
 room
            sound card IN  ◄── radio SPK/DATA OUT
            "radio hears a station"  ◄── VOX level, or serial CD/CTS/DSR ◄── radio squelch
```

### RX control — how the program knows it must transmit to the network

| Mode | Behavior |
| --- | --- |
| **Manual** | Only the PTT button (or the Ctrl key) transmits. |
| **VOX** | A transmission starts when the RMS level of the input exceeds the **VOX threshold**, and ends after **VOX hang time** frames of silence. |
| **Serial CD / CTS / DSR** | A transmission starts while the chosen serial input line is active (the radio's squelch / carrier-detect output), and ends when it drops. |

In every mode the PTT button keeps working. An automatic (VOX/squelch) transmission is never started while the room
is being heard, nor during the **Return hold**, and after a transmission ended by something else (time-out, PTT
button, disconnection) the input must go quiet once before VOX/squelch can start a new one.

While SCAN runs, input activity keeps the scanner in the current room, so a reply goes to the room it belongs to.

### TX control — how the program keys the radio

| Mode | Behavior |
| --- | --- |
| **Manual** | The radio is not keyed by the program. |
| **Serial RTS / Serial DTR** | The chosen output line is raised while the room is heard, so the radio transmits the network audio. |

While the speaker is **muted** the line is never raised, so the radio never sends a silent carrier. Serial ports are
opened with **RTS and DTR held low from the very first moment**, so opening the port never keys the radio. The same
physical port may be used for both RX and TX control. Ports are released (lines low) when the program closes.

### Parameters

| Setting | Range | Default | Meaning |
| --- | --- | --- | --- |
| **VOX threshold** | 1 – 32767 | 200 | VOX level, as the RMS value of the 16-bit samples. Normal speech is usually a few hundred. |
| **VOX hang time** | 1 – 500 | 50 | VOX hang time, in 20 ms frames (50 = 1 second). |
| **Return hold** | 0 – 50 | 5 | Hold, in tenths of a second, after the serial PTT line is released at the end of the room audio; it gives the radio time to return to receive before VOX/squelch can start a transmission. |
| **TX time-out** | 30, 60, 120, 180, 240, 300 s | 180 | Longest transmission; it is ended automatically. |
| **Ctrl key as PTT** | on / off | off | Tap Ctrl alone to start/stop transmitting. |

> **Wine:** when running under Wine, set `"wine": 1` in the `general` section of `settings.json`; serial ports are
> then not listed automatically (the list is unreliable there).

---

## Room scanner

1. Open the scan editor (**⋯** next to SCAN, or right-click SCAN). Pick rooms from *Available rooms* (with a search
   box) into *Rooms to scan* (**Add**, **Add all**, **Remove**, **Remove all**, or double-click), then **OK**.
2. Connect, then press **SCAN** (it turns green).

Behavior:

- The station visits each scan room in turn, staying **1000 ms** in each (editable only in `settings.json`,
  `scan.interval_ms`, 250–60000).
- Incoming audio, your own transmission and VOX/squelch activity pause the rotation; it resumes **5 s** after the last
  voice frame.
- Pressing SCAN again stops the scanner and returns to the room you were in before scanning. Choosing a room by hand,
  disconnecting or losing the connection also stops it (staying in the current room).

---

## Callsign alarms

Open the editor with the **bell** (Main tab) or **Alarms** (Alarm log tab), type callsigns and press **Add**, then
**OK**.

While connected, the program checks the stations online every 20 seconds (the first check 3 seconds after connecting).
The first check only records who is already online, so connecting never raises alarms. From then on, each watched
callsign that comes online or goes offline (in **any** room, whatever client or device it uses) plays
`data/alarm.wav`, shows a notification and is added to the **Alarm log** (up to 1000 entries kept in memory). The
watched list is saved; the history is not.

---

## Recording

Press **REC** (it turns red). Every audio frame you send and receive is recorded into a temporary file (up to 4 hours).
Press **REC** again to choose where to save the recording as a WAV file (8 kHz, 16-bit, mono); canceling the dialog
keeps recording. If nothing was recorded, the recording simply stops. When you close the program with a recording that
holds audio, you are offered to save it first.

---

## Logbook, ADIF, eQSL and QRZ.com

### Records

Each contact holds: **Callsign**, **Name**, **Date** (`yyyy-mm-dd`, UTC), **Time** (`HH:MM` or `HH:MM:SS`,
UTC), **Band**, **Frequency** (MHz) and **Comments**.

- New records are prefilled with the current UTC date and time, and with the band, frequency and comment of the newest
  record.
- The band list offers `2m`, `70cm`, `10m`, `6m`, `23cm` (each fills in a suggested frequency); any band name of the
  ADIF specification can be typed (`2190m` … `1mm`).
- The frequency accepts a comma as decimal separator and an optional trailing `MHz`.
- Adding a callsign that is already in the logbook shows the earlier contact and asks whether to continue.
- **Editing** a record marks it as not uploaded, so the corrected contact is sent again.
- Quick add: click the callsign on the station card, or right-click a *Last heard* row → **Add to the logbook**.

### ADIF export

**ADIF** writes the whole logbook to an `.adi` / `.adif` file: ADIF version 3.1.4 header (`PROGRAMID`,
`PROGRAMVERSION`, `CREATED_TIMESTAMP`), and per record `STATION_CALLSIGN`, `CALL`, `NAME`, `QSO_DATE`, `TIME_ON`,
`BAND`, `FREQ`, `MODE=DIGITALVOICE`, `RST_RCVD=59`, `RST_SENT=59` and `COMMENT`. The file is plain ASCII (accents are
removed).

### eQSL.cc

Requires the eQSL user and password in **Settings → Online logbooks** (the optional *QTH nickname* is sent as
`APP_EQSL_QTH_NICKNAME`). **eQSL** uploads, in the background, only the records not yet uploaded to eQSL, with the
comment as `QSLMSG`. The eQSL answer is shown in a window. Records are marked as uploaded only when eQSL took **every**
one of them (records it already had count as delivered); otherwise all of them are offered again next time.

### QRZ.com Logbook

Requires the QRZ.com **Logbook API key** in **Settings → Online logbooks**. **QRZ** sends each pending record with the Logbook
API (`ACTION=INSERT`); records accepted (or reported as duplicates) are marked as uploaded. The upload stops at the
first authentication or network error. A per-record summary is shown at the end.

---

## Station information (pictures, flags, RadioID)

When a station starts talking (and for your own station when idle), the card shows:

- **Picture**, in this order:
  1. a local picture `images/<CALLSIGN>.png|.jpg|.jpeg|.gif|.webp|.bmp` (a `/` in the callsign becomes `_`) — you can
     drop your own pictures there;
  2. otherwise the generic person icon, replaced by the **QRZ.com** picture when one is found. With a QRZ.com user and
     password configured, the QRZ.com XML data service is used (it needs a QRZ.com subscription that includes XML
     data); otherwise the public QRZ.com page is read. The stock image QRZ.com shows for members without a photo counts
     as no picture. Downloaded pictures are stored in `images/`; a failed lookup is retried after one hour.
- **Flag and country**, from the longest matching callsign prefix (4, 3, 2 then 1 characters) in `data/prefix.json`
  (1,284 prefixes, flags in `flags/`).
- **DMR ID, name and location** from the **RadioID** user list:
  - downloaded automatically on the first start from `database.radioid.net/static/user.csv`;
  - stored in 256 small TinyDB files in `database/radioid/`, so a lookup only reads one small file;
  - refreshed on demand with **Settings → General → Update the RadioID list**. The download is checked (header and size)
    and only replaces the list in use when it is complete.

The **DMR ID** you configure (0 – 16777215) is sent inside every voice frame.

---

## APRS position beacon

With **Settings → APRS → Send my APRS position** enabled, the program sends your position to APRS-IS when you start
transmitting, **at most once every 30 minutes**:

| Item | Value |
| --- | --- |
| Source | `<your callsign without SSID>-10` (`-10` is the SSID for Internet-linked stations) |
| Destination (tocall) | `APZPNT` |
| Path | `TCPIP*` |
| Format | Timestamped position (`@DDHHMMz`), symbol `/-`, comment `via OpenGroundnut` |
| Server | Host and port from the settings (default `rotate.aprs2.net:14580`) |
| Login | Your base callsign with its standard APRS-IS passcode |

Latitude and longitude are entered in **decimal degrees** (−90…90, −180…180), for example `51.4779` and `-0.0015`.

---

## Settings reference (`settings.json`)

All settings are stored in `database/settings.json` (a TinyDB file). Values keep their natural type (text, whole
number, list). The file is written in one atomic step and, on Linux and macOS, is readable by its owner only, because
it holds the access code and passwords. It can be edited by hand **while the program is closed**. Missing or invalid
values fall back to the defaults below and are reported at start-up.

| Section | Key | Default | Meaning |
| --- | --- | --- | --- |
| `general` | `callsign` | `"NOCALL"` | Callsign (A–Z, 0–9, `/`; up to 8 characters). |
| | `dmr_id` | `0` | DMR ID, 0 – 16777215 (0 = none). |
| | `message` | `""` | Text shown next to your callsign while transmitting (first 20 characters, ASCII). |
| | `access_code` | `""` | Peanut access code. |
| | `master` | `"peanut.pa7lim.nl"` | Address of the Peanut master server. |
| | `always_on_top` | `0` | `1` keeps the window above the others. |
| | `roger_beep` | `1` | `1` plays the roger beep when another station stops talking. |
| | `input_device` / `output_device` | `""` | Audio devices as `"number:name"`; empty = system default. Devices are found by name first, then by number. |
| | `eqsl_user` / `eqsl_password` / `eqsl_qth` | `""` | eQSL.cc user, password and QTH nickname. |
| | `qrz_user` / `qrz_password` / `qrz_api_key` | `""` | QRZ.com user, password and Logbook API key. |
| | `language` | `"en"` | Interface language code: `en`, `de`, `es`, `fr`, `it` or `pt`. |
| | `scale` | `1` | Window scale, 1 – 3. |
| | `wine` | `0` | `1` when running under Wine (serial ports are not listed). |
| `rx_control` | `mode` | `"Manual"` | `Manual`, `VOX`, `Serial CD`, `Serial CTS` or `Serial DSR`. |
| | `vox_threshold` | `200` | 1 – 32767. |
| | `vox_delay` | `50` | 1 – 500 frames of 20 ms. |
| | `vox_return` | `5` | 0 – 50 tenths of a second. |
| | `serial_port` | `""` | Serial port of the squelch line (e.g. `/dev/ttyUSB0`, `COM3`). |
| `tx_control` | `mode` | `"Manual"` | `Manual`, `Serial RTS` or `Serial DTR`. |
| | `ctrl_key_ptt` | `0` | `1` enables the Ctrl key PTT. |
| | `serial_port` | `""` | Serial port of the PTT line. |
| | `timeout` | `180` | Transmit time-out, 30 – 300 seconds. |
| `auto` | `connect_at_start` | `0` | `1` connects automatically 10 s after start-up. |
| | `room` | `""` | Room used by the automatic connection. |
| `alarms` | `callsigns` | `[]` | Watched callsigns. |
| `scan` | `rooms` | `[]` | Rooms visited by the scanner. |
| | `interval_ms` | `1000` | Time spent in each room, 250 – 60000 ms (file only). |
| `aprs` | `enabled` | `0` | `1` sends the APRS beacon. |
| | `host` | `"rotate.aprs2.net"` | APRS-IS server. |
| | `port` | `14580` | APRS-IS port. |
| | `latitude` / `longitude` | `""` | Position in decimal degrees. |
| `update` | `version_url` | `""` | Address of a plain-text file holding the newest version number (e.g. `1.1`). When set, a newer version is announced at start-up. Empty = no check. File only. |

Sections and keys the program does not know are dropped the next time the settings are saved.

Example (abridged):

```json
{
  "settings": {
    "1": {
      "general":    { "callsign": "N0CALL", "access_code": "12345", "master": "peanut.pa7lim.nl", "language": "en" },
      "rx_control": { "mode": "VOX", "vox_threshold": 300, "vox_delay": 50, "vox_return": 5, "serial_port": "" },
      "tx_control": { "mode": "Serial RTS", "serial_port": "/dev/ttyUSB0", "timeout": 180, "ctrl_key_ptt": 0 },
      "scan":       { "rooms": ["ROOM1", "ROOM2"], "interval_ms": 1000 },
      "update":     { "version_url": "" }
    }
  },
  "meta": { "1": { "schema_version": 1 } }
}
```

---

## Where your data is kept

Everything the program stores lives **next to the program**, so it travels with the folder:

| Path | Content |
| --- | --- |
| `database/settings.json` | Settings, including the access code and passwords (owner-only on Linux/macOS). |
| `database/logbook.json` | Logbook (`log` table) and room bookmarks per server (`bookmarks` table). |
| `database/radioid/` | RadioID user list (`index.json` + `users-00.json` … `users-ff.json`). |
| `images/` | Station pictures (downloaded or your own). |
| `peanut.log` | Log, including every unexpected error; rotates at 1 MB, three old copies kept. |

When the program folder **cannot be written to** (for example installed under `C:\Program Files`, or a macOS `.app`),
the same files are kept in the user's data folder instead:

| System | Folder |
| --- | --- |
| Windows | `%APPDATA%\OpenGroundnut` |
| macOS | `~/Library/Application Support/OpenGroundnut` |
| Linux | `$XDG_DATA_HOME/opengroundnut`, or `~/.local/share/opengroundnut` |

To move your station to another computer, copy the `database` folder (and `images` if you added pictures).

All files are plain JSON. A file that cannot be read is renamed to `<file>.bak` (so it can be rescued by hand) and the
program continues with a fresh one, telling you so.

---

## Network services used

| Service | Address | When |
| --- | --- | --- |
| Peanut master list | `www.pa7lim.nl/masters.json` | Start-up, retries, ↻ button. |
| Peanut room list | `<master>/api/rooms4.json` | Start-up, every 10 min, every connection, ↻ button. |
| Active transmissions | `<master>/api/active.json` | Every second, only while the Monitor tab is open. |
| Stations online | `<master>/api/whois.json` | After connecting, on room change, every 20 s. |
| Peanut voice/control | `<master>:6667` (UDP) | While connected. |
| RadioID user list | `https://database.radioid.net/static/user.csv` | First start, **Update the RadioID list**. |
| RadioID API | `https://radioid.net/api/dmr/user/` | **Look up** button (DMR ID). |
| QRZ.com | `xmldata.qrz.com`, `www.qrz.com/db/…` | Station picture lookups. |
| QRZ.com Logbook API | `https://logbook.qrz.com/api` | **QRZ** button. |
| eQSL.cc | `https://www.eQSL.cc/qslcard/ImportADIF.cfm` | **eQSL** button. |
| APRS-IS | Configured host:port (TCP) | Start of a transmission, at most every 30 min, when enabled. |
| Version file | `update.version_url` | Start-up, only when set. |

HTTP requests identify themselves as `OpenGroundnut/1.0 (<CALLSIGN>)`. Every HTTP service is tried over **HTTPS**
first. Plain HTTP is used for a Peanut host **only** when its HTTPS port actively refuses the connection; a certificate
error, a time-out, a proxy refusal or an unknown name never falls back to plain HTTP. The scheme that worked is
remembered per host.

When the network is not available yet at start-up (a computer that boots before its network), the server and room
lists are retried after 5, 10, 30 and then every 60 seconds.

---

## Peanut protocol overview

One UDP socket per connection, *connected* to `(<master>, 6667)`. Text fields are ASCII (accents removed), cut to their
width and **right-aligned** (left-padded with spaces).

### Messages sent by the client

| Message | Layout (bytes) | When |
| --- | --- | --- |
| `LOGIN` | `"LOGIN"` + callsign(8) + access code(8) | Every 2 s until the server answers, at most 5 times. |
| `INFO` | `"INFO"` + callsign(8) + device(20) + version(5) | After `ACK`. Device is `WINDOWS` on every system, version `0.11`. |
| `PONG` | `"PONG"` + callsign(8) + room(8) | Answer to every `PING`; also announces a room change. |
| `PMSG` | `"PMSG"` + room(8) + message(20) | With the first frames of each transmission. |
| `DPCM` | 30-byte header + 320 bytes of audio | Every 20 ms while transmitting. |
| `LOGOUT` | `"LOGOUT"` | On disconnection. |

### Messages handled from the server

| Message | Meaning |
| --- | --- |
| `ACK` | Login accepted: the client sends `INFO`. |
| `PING` | Server alive: the client answers `PONG`; it also feeds the 15 s watchdog. The first `ACK` or `PING` marks the link as up. |
| `REFU` + reason byte | Login refused: 1 = incorrect, 2 = wrong access code, 3 = client must be upgraded, other = unknown. The client disconnects and does not retry. |
| `DPCM` | Voice of the station talking in the room. |
| `PMSG`, `PGPS`, others | Ignored. |

### `DPCM` voice frame

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 4 | `"DPCM"` |
| 4 | 8 | Callsign of the station talking |
| 12 | 8 | Room |
| 20 | 2 | `0x00 0x00` |
| 22 | 3 | DMR ID, big-endian |
| 25 | 2 | Sequence counter, little-endian |
| 27 | 1 | RSSI |
| 28 | 1 | Frame type: `1` = audio, `16` = end of transmission |
| 29 | 1 | Session number (random 1–253 per transmission) |
| 30 | 320 | 160 samples, 16-bit signed little-endian, 8 kHz mono (20 ms). An end frame carries 320 bytes of silence. |

Incoming frames are ignored while the client itself is transmitting. A new callsign or session marks a new
transmission; the end frame of the transmission being heard logs it in *Last heard* and plays the roger beep.

---

## Architecture

### Start-up and the shared namespace

`opengroundnut.py` is the only entry point. It works out three folders — `APP_DIR` (the program), `DATA_DIR` (user
files; `APP_DIR` when writable) and `RES_DIR` (read-only resources; PyInstaller's unpack folder in a frozen build) —
and then **executes every module of `src/` inside its own global namespace**, in this order:

```
bootstrap.py → events.py → network.py → audio.py → aprs.py → database.py → callsign.py → settings.py → core.py
   → load_language(<code>)  (texts of lang/<code>.py, read with tr("key"))
   → gui.py
```

Because they share one namespace, the modules use each other's functions and state directly, without imports. Only
`utils.py` is a regular module, imported by name. This is why linting must be done on the joined modules (see
[Development](#development)).

Start-up sequence:

1. `bootstrap.py` loads the libraries and shared state; `setup_logging()` starts the log.
2. The core modules are loaded; the ALSA/JACK console noise is muted.
3. `initialize_application()` opens the settings, lists serial ports, opens the logbook.
4. `load_language()` loads the interface texts of the chosen language; every text is read with `tr("key")`.
5. `gui.py` is loaded; `start_gui()` builds the window and subscribes to the core events.
6. `run_gui(on_ready=start_application)` shows the window and, right after, `start_application()` starts the audio
   system and every background worker, so a slow or missing network never delays the window.

### Core and interface are separated

The **core** (`bootstrap`, `events`, `network`, `audio`, `aprs`, `database`, `callsign`, `settings`, `core`) never
touches a window or widget. It reports everything through **events** (`events.py`):

```python
emit_event("audio_level", level=42)
emit_event("error", title="Error", message="The port is busy")
```

The **interface** (`gui.py`) registers one listener with `set_event_listener()`, and calls plain core functions for
user actions (`toggle_connection()`, `toggle_transmit()`, `enter_room()`, `toggle_scan()`, `save_setup()`, …). Events
are published from worker threads; the GUI hands them to the Tk main thread through a queue drained by a short timer.
Without a listener, errors and notices go to the log, so the core also runs headless (this is how the tests run it).

Events published by the core:

| Event | Data |
| --- | --- |
| `servers_loaded` | `names`, `current` |
| `rooms_loaded` | `countries`, `initial` |
| `connecting` | — |
| `connection_changed` | `connected` |
| `reconnecting` | — |
| `ptt_state` | `status` (0 idle, 1 receiving, 2 transmitting), `caption`, `enabled` |
| `audio_level` | `level` (0–327) |
| `transmission_logged` | `time`, `callsign`, `name`, `duration` |
| `station_photo` | `callsign`, `picture`, `name` |
| `station_identity` | `identity`, `name`, `location` |
| `online_stations` | `callsigns` |
| `alarms_updated` | `lines` |
| `scan_state` | `active` |
| `scan_room` | `room` |
| `dmr_ids` | `ids` |
| `user_ids_updated` | `ok` |
| `eqsl_reply` / `qrz_reply` | `text` |
| `info` / `warning` / `error` | `title`, `message` |
| `setup_required` | `title`, `message` |
| `login_refused` | `title`, `message`, `reason` |
| `fatal_error` | `title`, `message` |

### Threads

All workers are named daemon threads whose exceptions are logged:

| Thread | Job |
| --- | --- |
| `rx-audio` / `rx-playback` | Receives UDP (login, PING/PONG, REFU, DPCM) / plays the jitter buffer (max 25 frames, 3-frame / 60 ms prefill after a pause; oldest frame dropped when full). |
| `tx-audio` | Microphone → DPCM frames for one Manual-mode transmission, then its end frame. |
| `vox-input` | In VOX/serial modes: reads the input, decides start/stop, sends frames. |
| `status-monitor` | Every 10 ms: link state (receiving if a frame arrived in the last 600 ms) and transmit time-out. |
| `server-watchdog` | Every 5 s: no PING for 15 s → reconnect. |
| `server-lists` | Master and room lists, retries and 10-minute refresh. |
| `online-monitor` | `whois.json` every 20 s, alarms. |
| `active-monitor` | `active.json` every second while Monitor is visible. |
| `station-lookup` | Picture, flag and RadioID lookups, one callsign at a time. |
| `room-scanner` | Scanner rotation. |
| others | APRS beacon, uploads, RadioID download, version check, reconnection, auto-start. |

Every connection has a **generation number**; a worker of an older connection ends on its own. Every transmission has
a **number**, so two microphone loops never send at the same time and the server always receives the end frame.

### Storage

`database.py` provides `SafeJSONStorage`, a TinyDB storage that writes to a temporary file, `fsync`s it and replaces
the old file in one `os.replace()`. TinyDB access is serialized with a lock; settings are kept in memory and saved as
one document.

---

## Project layout

```
opengroundnut/
├── opengroundnut.py          Entry point: folders, module loader, start-up
├── opengroundnut.spec        PyInstaller recipe (single folder; .app bundle on macOS)
├── LICENSE.md                License (WTFPL, version 2)
├── Peanut_Protocol_Overview.md  Technical reference of the Peanut protocol
├── requirements.txt          Python packages
├── pyproject.toml            pytest and ruff settings
├── install_linux.sh          Creates .venv and installs the packages (Linux, macOS)
├── install_windows.bat       Same for Windows (Python 3.9–3.13 through the py launcher)
├── run_linux.sh              Starts the program from .venv (passes arguments on)
├── run_windows.bat           Same for Windows (pythonw without arguments)
├── src/
│   ├── bootstrap.py          Imports, identity, endpoints, limits, logging, HTTP helpers, shared state
│   ├── events.py             Event channel between core and interface
│   ├── network.py            Peanut UDP protocol, RX/TX loops, eQSL and QRZ HTTP calls
│   ├── audio.py              Audio devices, PTT, link state, serial PTT line, recording
│   ├── aprs.py               APRS-IS beacon
│   ├── database.py           TinyDB storage, logbook, bookmarks, RadioID index, ADIF, uploads, QRZ pictures
│   ├── callsign.py           Prefix → flag, pictures, RadioID/DMR lookups, version check
│   ├── settings.py           Settings store and defaults, form validation, scanner, alarm list
│   ├── core.py               Start-up/shutdown, connection, reconnection, rooms, monitors, RadioID download
│   ├── gui.py                The whole graphical interface
│   └── utils.py              Access-code check, audio device and serial port listing, quiet serial open
├── lang/                     en.py (reference), de.py, es.py, fr.py, it.py, pt.py
├── data/                     prefix.json, alarm.wav, icons
├── flags/                    Country flags (PNG)
├── fonts/orbitron/           Orbitron font (SIL OFL)
├── tests/                    conftest.py, test_core.py
└── tools/
    ├── lint_shared_namespace.py   Lints the modules joined in load order
    └── make_release.py            Builds the release zip
```

---

## Development

```bash
python -m pip install -r requirements.txt pytest ruff
python -m pytest
python tools/lint_shared_namespace.py
```

- **Tests** (`tests/`) load the application core exactly as `opengroundnut.py` does, into a fresh namespace whose data
  folder is a temporary folder: no window, no sound card and no network are used, and real settings are never touched.
  They cover the protocol fields and frame header, the access-code check, audio level, settings defaults and
  validation, logbook and ADIF, eQSL/QRZ answer parsing, prefixes and flags, the APRS packet,
  room changes during transmission, the online list, alarms and the HTTPS fallback rule. The packages of
  `requirements.txt` (including PyAudio) must be installed, because the core imports them.
- **Linting**: running `ruff` on single files reports false "undefined name" errors, because names come from other
  modules of the shared namespace. `tools/lint_shared_namespace.py` joins the modules and the
  interface in load order into one temporary file and runs `ruff check` on it with the rules of `pyproject.toml`
  (`E9`, `F`, `B`, `PLE`).
- **Debugging**: start with `--debug` and read `peanut.log`.

---

## Building a stand-alone program

```bash
python -m pip install pyinstaller
pyinstaller opengroundnut.spec
```

The result is `dist/opengroundnut/` (and `dist/OpenGroundnut.app` on macOS, with the microphone permission text).
Because the modules run from source, `src/`, `data/`, `flags/`, `lang/` and `fonts/` are bundled as data, and the spec
reads every import of the modules so PyInstaller includes them. User files are created next to the executable on the
first run, or in the user data folder when that is not writable.

---

## Building a release zip

```bash
python tools/make_release.py
```

Writes `release/opengroundnut-<version>.zip` (the version is read from `APP_DISPLAY_VERSION` in `src/bootstrap.py`).
Inside a Git working copy the tracked files are packed; otherwise a fixed list of program files and folders. Your
settings, access code, passwords, logbook, RadioID list, pictures, log, recordings, `.venv`, build output and caches
are **never** packed.

---

## Adding a language

1. Copy `lang/en.py` to `lang/<code>.py`, where `<code>` is the two-letter ISO 639-1 code of the language. Set
   `LANGUAGE_NAME` to the name of the language written in that language, and translate every text of `TEXTS`
   (keep the keys and the `{}` placeholders). A key left out is shown in English.
2. Add the code to `LANGUAGES` in `src/bootstrap.py`.
3. Add the code to the `hiddenimports` list in `opengroundnut.spec` for stand-alone builds.

---

## Troubleshooting

| Problem | Solution |
| --- | --- |
| `Fatal error: the Python package '…' is not installed` | Run the installer again, or `python -m pip install -r requirements.txt` in the environment you start the program with. |
| PyAudio fails to build (Linux/macOS) | Install the PortAudio development files: `portaudio19-dev` (Debian/Ubuntu), `portaudio-devel` (Fedora), `brew install portaudio` (macOS). |
| PyAudio fails to install (Windows) | Use Python 3.9–3.13: delete `.venv`, install Python 3.13, run `install_windows.bat` again. |
| `Python's Tk support is missing` | Install `python3-tk` (Debian/Ubuntu) or `python3-tkinter` (Fedora). |
| *The access code does not match the callsign* | The access code does not belong to the callsign. Check both in Settings → General (the callsign must be exactly the registered one). |
| *The Peanut network refused the login* | The server rejected the login; the reason is shown. Correct the callsign/code, or update the program. |
| No servers or rooms | The network is not reachable yet; the lists are retried automatically. Press **↻** to retry now. |
| *Reconnecting …* | The server stopped sending PINGs for 15 s; the program reconnects every 10 s. Press the button to cancel. |
| Audio device not found | The program falls back to the system default device and shows a warning. Choose the device again in Settings (press **↻** after plugging it in, while disconnected). |
| The PTT button is grayed out | Not connected yet, the server has not accepted the login, or another station is talking. |
| The radio does not key | TX control must be *Serial RTS* or *Serial DTR* with the right port; the speaker must not be muted. |
| VOX triggers on noise / does not trigger | Raise / lower the **VOX threshold**; speech is typically a few hundred. |
| The window is too large | Lower **Scale**, or start with `PEANUT_UI_SCALE=0.9`. |
| Anything else | Start with `--debug` and look in `peanut.log`. |

---

## Credits and licenses

- The **Peanut** network, its master list and the access-code registration are hosted at `pa7lim.nl`. OpenGroundnut is
  an independent client.
- **Orbitron** font (`fonts/orbitron`) is distributed under the **SIL Open Font License** (see
  `fonts/orbitron/OFL.txt`).
- Station data comes from **RadioID.net** and **QRZ.com**; logbook services are **eQSL.cc** and the **QRZ.com
  Logbook**; position reports go to **APRS-IS**. Each service has its own terms of use.

OpenGroundnut is released under the **Do What The Fuck You Want To Public License, Version 2** (WTFPL); see
`LICENSE.md`. Every source file carries the same notice.
