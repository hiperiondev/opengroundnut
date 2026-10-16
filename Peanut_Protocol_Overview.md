# Peanut Protocol Overview

Technical reference of the Peanut network protocol as implemented by OpenGroundnut 1.0.

This document describes how a desktop client discovers Peanut servers, logs in, joins rooms, exchanges voice and
keeps its connection alive. It covers the HTTP/JSON directory services and the UDP control and voice protocol, with
exact byte layouts, timing, state handling, robustness rules and the known security limits of the protocol.

It is **not an official specification**. Peanut has no published protocol document; everything here comes from
the behaviour of OpenGroundnut, which interoperates with the public Peanut servers. Where the meaning of a field or
the behaviour of the server cannot be established from the client side, the text says so.

---

## Contents

1. [Scope and conventions](#1-scope-and-conventions)
2. [What Peanut is](#2-what-peanut-is)
3. [Architecture](#3-architecture)
4. [HTTP/JSON directory interface](#4-httpjson-directory-interface)
5. [UDP transport](#5-udp-transport)
6. [Text field encoding](#6-text-field-encoding)
7. [Message catalogue](#7-message-catalogue)
8. [Control messages in detail](#8-control-messages-in-detail)
9. [DPCM voice frames](#9-dpcm-voice-frames)
10. [Connection life cycle](#10-connection-life-cycle)
11. [Transmitting](#11-transmitting)
12. [Receiving](#12-receiving)
13. [Rooms, room changes and scanning](#13-rooms-room-changes-and-scanning)
14. [Keepalive, watchdog and reconnection](#14-keepalive-watchdog-and-reconnection)
15. [Login refusal (REFU)](#15-login-refusal-refu)
16. [Audio format and playout](#16-audio-format-and-playout)
17. [Timing summary](#17-timing-summary)
18. [Robustness rules for implementers](#18-robustness-rules-for-implementers)
19. [Security considerations](#19-security-considerations)
20. [Open questions](#20-open-questions)
21. [Validation checklist for a new implementation](#21-validation-checklist-for-a-new-implementation)
22. [Related services used by the client](#22-related-services-used-by-the-client)
23. [Where each part lives in the source](#23-where-each-part-lives-in-the-source)
24. [Glossary](#24-glossary)
25. [Appendix A: message length summary](#appendix-a-message-length-summary)
26. [Appendix B: annotated examples](#appendix-b-annotated-examples)
27. [Appendix C: minimal client walkthrough](#appendix-c-minimal-client-walkthrough)

---

## 1. Scope and conventions

### 1.1 Certainty levels

Every statement belongs to one of three levels. When a section does not say otherwise, it is **Implemented**.

| Level | Meaning |
| --- | --- |
| **Implemented** | What OpenGroundnut sends, expects and does. Verifiable in the source code of this project. |
| **Observed** | Server behaviour that the client relies on and that works against the public servers, but that is not written down anywhere official. |
| **Unverified** | The meaning or behaviour cannot be determined from the client. Treat it as an assumption. |

### 1.2 Notation

- Byte offsets start at 0.
- `field(n)` is a text field of exactly *n* bytes (see [section 6](#6-text-field-encoding)).
- `␠` stands for one ASCII space (0x20) in examples.
- Hex dumps show bytes as two-digit hexadecimal values.
- *Client* is the program run by the station; *server* or *master* is the Peanut server it connects to.

---

## 2. What Peanut is

Peanut is an Internet push-to-talk network for licensed radio amateurs. A station connects to a **master server**,
enters a **room** and talks to every other station in that room. The server works as a reflector: the voice of the
station that is talking is relayed to every station in the same room. Some rooms are linked by their administrators
to other digital-voice systems (D-STAR, System Fusion, DMR and others); which rooms are linked, and how, is decided
on the server side and is invisible to the protocol.

Using the network requires:

- an amateur-radio **callsign**, and
- the **Peanut access code** that belongs to that callsign, obtained by registering with the network
  (`www.pa7lim.nl/peanut`).

A **DMR ID** is optional. It is carried inside every voice frame but does **not** replace the access code.

The network operator has warned that old clients may be rejected after protocol changes; the refusal reason
"upgrade required" ([section 15](#15-login-refusal-refu)) exists for that purpose. Room availability depends on the
administrators of each server.

---

## 3. Architecture

A client uses two independent channels:

1. **HTTP/JSON** for metadata: the list of master servers, the rooms of a server, the transmissions in progress
   and the connected stations. These are plain read-only GET requests.
2. **UDP** for everything that happens in real time: login, keepalive, room announcements, text messages and voice.

```
                        ┌──────────────────────────────┐
                        │  Directory host              │
   GET masters.json ───►│  www.pa7lim.nl/masters.json  │
                        └──────────────────────────────┘
                                       │ name → master
                                       ▼
 ┌────────┐  GET /api/rooms4.json  ┌──────────────────────────┐
 │        │ ─────────────────────► │                          │
 │        │  GET /api/whois.json   │                          │
 │ Client │ ─────────────────────► │   Master server          │
 │        │  GET /api/active.json  │   <master>               │
 │        │ ─────────────────────► │                          │
 │        │                        │                          │
 │        │ ◄═══ UDP port 6667 ══► │  LOGIN ACK INFO PING     │
 │        │                        │  PONG PMSG DPCM LOGOUT   │
 └────────┘                        └──────────────────────────┘
```

| Interface | Direction | Resource | Content |
| --- | --- | --- | --- |
| HTTP GET | Client → directory | `www.pa7lim.nl/masters.json` | List of master servers |
| HTTP GET | Client → master | `<master>/api/rooms4.json` | Room catalogue |
| HTTP GET | Client → master | `<master>/api/whois.json` | Connected stations |
| HTTP GET | Client → master | `<master>/api/active.json` | Transmissions in progress |
| UDP | Both ways | `<master>:6667` | Control messages and voice |

`<master>` is the `master` value of the server chosen from `masters.json`: a host name (or address) used both for the
HTTP requests and for the UDP socket.

The two channels are not linked by any token or session identifier. The HTTP resources are public and need no
authentication; only the UDP login uses the access code.

---

## 4. HTTP/JSON directory interface

### 4.1 Request rules (OpenGroundnut)

- Every request has a time-out of 5 s to connect and 15 s to read.
- Every request carries the header `User-Agent: OpenGroundnut/1.0 (<CALLSIGN>)` (without the parentheses part
  while no callsign is configured).
- A response is used only when its status is **200** and its body is valid JSON of the expected shape (a JSON
  array); anything else is treated as "not available" and the data already known is kept.
- **HTTPS is tried first.** Plain HTTP is used for a host only when its HTTPS port actively **refuses** the TCP
  connection. A certificate error, a time-out, a proxy refusal or a name that cannot be resolved never leads to plain
  HTTP, because blocking HTTPS is exactly what an attacker on the path would do to serve forged server or room
  lists. The scheme that worked is remembered per host; when it stops working both are tried again next time.
- TLS certificates are always verified.

> **Observed:** some Peanut hosts serve only plain HTTP. Clients written without the rule above usually request
> `http://` directly; the server side does not require either scheme.

### 4.2 Server directory: `masters.json`

```
GET https://www.pa7lim.nl/masters.json
```

Response: a JSON array of objects.

```json
[
  { "name": "<display name>", "master": "<server host>" },
  { "name": "<display name>", "master": "<server host>" }
]
```

| Field | Type | Use |
| --- | --- | --- |
| `name` | string | Text shown to the user in the server list. |
| `master` | string | Host of the server: used for every later HTTP request and for the UDP socket. |

- Entries without a `name` or without a `master` are ignored.
- The default server, used until the user chooses another one, is `peanut.pa7lim.nl`.
- When the user picks a server by name, its `master` value is looked up in this list. A server name that is not in
  the list (for example because the list has not loaded yet) keeps the master already in use.
- **Unverified:** the full schema. Other fields may exist; clients must ignore what they do not know.

When to request it: at start-up, on every retry while it has not loaded yet, and when the user presses the
refresh button.

### 4.3 Room catalogue: `rooms4.json`

```
GET https://<master>/api/rooms4.json
```

Response: a JSON array of room objects.

| Field | Type | Use |
| --- | --- | --- |
| `room` | string | Room name. Converted to upper case and trimmed before display and use. |
| `country` | string | Country (or group) of the room. Compared without regard to case. Used to group rooms. |
| `type` | string | `"local"` marks a room that is local to this server; any other value (or none) is a network room. |

How the client groups the rooms:

| Group | Contents |
| --- | --- |
| **PEANUT** | Every room whose `type` is not `local`. |
| **ALL** | Every room. |
| **BOOKMARKS** | Rooms the user saved as favourites on this server (client-side only). |
| `<COUNTRY>` | One group per distinct `country` value of the non-local rooms, upper case. |

When to request it: at start-up, every 10 minutes, every time a connection is accepted (so rooms created in the
meantime appear) and when the user presses the refresh button.

**Unverified:** the exact meaning of `type` values other than `local`, and the complete list of fields.

### 4.4 Connected stations: `whois.json`

```
GET https://<master>/api/whois.json
```

Response: a JSON array, one object per connected station.

| Field | Type | Use |
| --- | --- | --- |
| `Call` | string | Callsign of the station. Note the capital **C**. |
| `room` | string | Room the station is in. |
| `device` | string | Kind of client, as declared in its `INFO` message (for example `WINDOWS`, `ANDROID`, `HOTSPOT`). |

- Entries without `Call` are ignored. Stations of **every** device type are listed (hotspots, gateways and other
  clients included).
- The "stations in room" list shows the entries whose `room` equals the room the client is in (or the room selected
  in the interface while offline).
- The callsign alarms compare the full list with the watched callsigns to detect stations joining or leaving the
  network.

When to request it: right after the login is accepted, after every room change, then every 20 seconds while
connected (the first periodic check runs 3 seconds after connecting).

### 4.5 Transmissions in progress: `active.json`

```
GET https://<master>/api/active.json
```

Response: a JSON array, one object per transmission in progress on the server.

| Field | Type | Use |
| --- | --- | --- |
| `Call` | string | Callsign of the station transmitting. |
| `message` | string | The text the station sent with `PMSG` ([section 8.5](#85-pmsg)). |
| `room` | string | Room of the transmission. |
| `startPTT2` | string | Moment the transmission started, as text in server time. |

- `startPTT2` has no fixed format: **servers differ in how they write the date part**. OpenGroundnut looks for the
  first `H:MM:SS` or `HH:MM:SS` group anywhere in the text and shows it as `HH:MM:SS`; a text without such a group is
  shown unchanged. Treat the field as opaque.
- Polled **once per second**, and only while the user is looking at the Monitor view, to keep the load on the server
  low.

**Unverified:** the full schema, and how long an entry stays in the list after a transmission ends.

### 4.6 Development rooms

The room `DEVTEST` is used for server development. OpenGroundnut never shows it in the Monitor view, never stores it
as a bookmark and only lists it for the server developer's callsign. This is a client convention, not part of the
protocol.

---

## 5. UDP transport

| Property | Value |
| --- | --- |
| Protocol | UDP over IPv4 (`AF_INET`, `SOCK_DGRAM`) |
| Server port | **6667** |
| Server address | the `master` host, resolved once per connection |
| Client port | chosen by the operating system on the first send (no fixed local port) |
| Sockets | one per connection; a reconnection opens a new one |
| Encoding of text | ASCII |
| Fragmentation | none at application level: one message = one datagram |
| Acknowledgements | none per packet; only `LOGIN` is answered (`ACK`/`PING`) |

OpenGroundnut **connects** the UDP socket to the server address. The operating system then delivers only datagrams
that really come from that address and port, which is the simplest form of source validation (see
[section 19](#19-security-considerations)). It also means the host name is resolved once, not for every packet.

- Receive buffer: 2048 bytes, larger than any valid message, so an unexpectedly large datagram is read and
  discarded instead of causing an error on some systems.
- Receive time-out: 0.5 s, so the receive loop regularly checks whether the connection has ended.
- On Windows, an earlier send to an unreachable port is reported later as a "connection reset" on receive; this is
  not fatal and is ignored.
- A failed send is reported once per streak of failures, not once per voice frame.

**Messages are dispatched by their text prefix**, not by their length. The prefixes have different lengths:
`ACK` 3, `LOGIN` 5, `LOGOUT` 6, all others 4 bytes.

---

## 6. Text field encoding

All text inside protocol messages uses **fixed-width, right-aligned ASCII fields**:

1. The text is reduced to plain ASCII: accents are removed (`é` → `e`, `ü` → `u`) and any other non-ASCII
   character is dropped.
2. It is **cut** to the field width.
3. It is **left-padded with spaces** up to the field width.

```
field(8) of "N0CALL"   →  "␠␠N0CALL"
field(8) of "TEST"     →  "␠␠␠␠TEST"
field(8) of "LONGROOMNAME" → "LONGROOM"
field(20) of "Café"    →  "␠␠␠␠␠␠␠␠␠␠␠␠␠␠␠␠Cafe"
```

Callsigns are upper case and contain only `A–Z`, `0–9` and `/` (portable calls), at most 8 characters.

> **Interoperability note:** OpenGroundnut always cuts every field to its width, so every message has its nominal
> length. Other clients have been seen to pad without cutting, in which case a value longer than the field makes
> the whole datagram longer and shifts every following field. A receiver must therefore never assume a field fits:
> check lengths before reading fixed positions ([section 18](#18-robustness-rules-for-implementers)).

---

## 7. Message catalogue

| Prefix | Length | Direction | Purpose |
| --- | --- | --- | --- |
| `LOGIN` | 21 | Client → server | Callsign and access code: ask to be accepted. |
| `ACK` | ≥ 3 | Server → client | Login accepted; the client answers with `INFO`. |
| `INFO` | 37 | Client → server | Callsign, device type and protocol version. |
| `PING` | ≥ 4 | Server → client | Server keepalive; the client answers with `PONG`. |
| `PONG` | 20 | Client → server | Answer to `PING`; also announces the client's room. |
| `PMSG` | 32 | Client → server | Short text shown next to the callsign while transmitting. |
| `DPCM` | 350 | Both | Voice frame (type 1) or end-of-transmission frame (type 16). |
| `REFU` | ≥ 4 | Server → client | Login refused; byte 4 holds the reason. |
| `LOGOUT` | 6 | Client → server | The station leaves. |
| `PGPS` | ? | Server → client | Recognised and ignored (**Unverified:** may carry a position). |
| other | — | — | Ignored. |

Lengths are those of messages built by OpenGroundnut; for messages received from the server only the minimum the
client relies on is given.

---

## 8. Control messages in detail

### 8.1 LOGIN

```
"LOGIN" + field(8) callsign + field(8) access code            = 21 bytes
```

| Offset | Size | Content |
| --- | --- | --- |
| 0 | 5 | `LOGIN` |
| 5 | 8 | Callsign, right-aligned |
| 13 | 8 | Access code (decimal digits), right-aligned |

- Sent when the connection starts, then again every **2 s** until the server answers with `ACK` or `PING`, at most
  **5 times** in total.
- The access code travels **in clear text** (see [section 19](#19-security-considerations)).
- Before sending anything, OpenGroundnut checks locally that the configured code matches the callsign, and does not
  try to connect when it does not. This check is a convenience for the user: it is not part of the protocol, and it
  changes nothing in what is sent.

### 8.2 ACK

Sent by the server when the login is accepted. Only the prefix is examined; any further bytes are ignored.

On `ACK` the client:

1. sends `INFO`;
2. if the link was not up yet, marks it as up (see [section 10](#10-connection-life-cycle)).

### 8.3 INFO

```
"INFO" + field(8) callsign + field(20) device + field(5) version  = 37 bytes
```

| Offset | Size | Content | OpenGroundnut value |
| --- | --- | --- | --- |
| 0 | 4 | `INFO` | |
| 4 | 8 | Callsign | the station callsign |
| 12 | 20 | Device type | `WINDOWS` |
| 32 | 5 | Protocol version | `0.11` |

- **Device type.** The device names known on the network are `WINDOWS` and `ANDROID` (hotspots and gateways
  report other values such as `HOTSPOT`). Some station lists only show the first two, so OpenGroundnut reports
  `WINDOWS` on every operating system to be listed like any other desktop client. The value is what other clients
  see in the `device` field of `whois.json`.
- **Protocol version.** The server checks it, and may refuse an outdated client with `REFU` reason 3. It is
  independent of the program's own version number (1.0). OpenGroundnut reports `0.11`.
- **Unverified:** whether the server requires `INFO` before it relays voice, and what it does with an unknown device
  name.

### 8.4 PING and PONG

```
Server → client:  "PING" ...                                  (prefix only is examined)
Client → server:  "PONG" + field(8) callsign + field(8) room  = 20 bytes
```

| Offset | Size | Content |
| --- | --- | --- |
| 0 | 4 | `PONG` |
| 4 | 8 | Callsign |
| 12 | 8 | Room the client is in (blank field when none) |

- The server sends `PING` periodically. Every `PING` proves the server is alive; it feeds the client watchdog
  ([section 14](#14-keepalive-watchdog-and-reconnection)) and is answered at once with `PONG`.
- The first `PING` (like `ACK`) marks the link as up.
- **`PONG` is also the room announcement.** The client sends an unsolicited `PONG` right after the link comes up and
  every time it changes room. There is no separate "join room" message.
- **Observed:** the server places the station in the room named by its latest `PONG` (and by the room field of its
  voice frames). **Unverified:** the exact server-side transition and whether anything else is needed.

### 8.5 PMSG

```
"PMSG" + field(8) room + field(20) message                    = 32 bytes
```

| Offset | Size | Content |
| --- | --- | --- |
| 0 | 4 | `PMSG` |
| 4 | 8 | Room |
| 12 | 20 | Free text (first 20 characters, ASCII) |

- The message is the short text the user configured (for example a name or a location). The server publishes it as
  the `message` field of `active.json` while the station transmits.
- OpenGroundnut sends it **just before each of the first two voice frames** of every transmission (sequence numbers
  0 and 1), which makes it more likely that at least one copy arrives over UDP.
- `PMSG` received from the server is ignored.
- **Unverified:** why two copies are customary, and whether the server stores the message per transmission or per
  station.

### 8.6 LOGOUT

```
"LOGOUT"                                                       = 6 bytes
```

Carries no callsign or session. Sent when the user disconnects, and when the client drops a connection the server
stopped answering. It is sent **after** the end frame of any transmission in progress and before the socket is
closed. No answer is expected.

### 8.7 REFU

See [section 15](#15-login-refusal-refu).

### 8.8 PGPS

Recognised by its prefix and ignored. **Unverified:** whether it carries a position or anything else.

---

## 9. DPCM voice frames

Voice travels in `DPCM` frames in both directions. Despite the name, the audio is **not compressed**: a frame
carries raw 16-bit PCM. Do not replace it with a codec (Opus, AMBE, real DPCM) without evidence that the servers
expect one.

### 9.1 Layout (350 bytes)

| Offset | Size | Field | Encoding |
| --- | --- | --- | --- |
| 0 | 4 | Message type | ASCII `DPCM` |
| 4 | 8 | Callsign of the sender | field(8) |
| 12 | 8 | Room | field(8) |
| 20 | 1 | Reserved | `0x00` |
| 21 | 1 | Reserved | `0x00` |
| 22 | 1 | DMR ID, high byte | bits 23–16 |
| 23 | 1 | DMR ID, middle byte | bits 15–8 |
| 24 | 1 | DMR ID, low byte | bits 7–0 |
| 25 | 1 | Sequence counter, low byte | bits 7–0 |
| 26 | 1 | Sequence counter, high byte | bits 15–8 |
| 27 | 1 | RSSI / status | `0x01` |
| 28 | 1 | Frame type | `0x01` audio, `0x10` (16) end of transmission |
| 29 | 1 | Session number | 1–253 at the start of a transmission |
| 30 | 320 | Audio | 160 samples, signed 16-bit little-endian, 8 kHz mono |

The first 30 bytes are the **header**: 20 ASCII bytes followed by 10 binary bytes.

```
 0                   4                  12                  20  22      25    27 28 29 30
 ├───────────────────┼───────────────────┼───────────────────┼───┼───────┼─────┼──┼──┼──┼──────────── … ─┤
 │ D  P  C  M        │ callsign (8)      │ room (8)          │0 0│DMR ID │ seq │RS│TY│SE│ 320 bytes PCM   │
 └───────────────────┴───────────────────┴───────────────────┴───┴───────┴─────┴──┴──┴──┴──────────── … ─┘
                                                                  big-end. little    type session
```

### 9.2 Field notes

- **Mixed byte order.** The DMR ID is written most significant byte first (big-endian, 24 bits); the sequence
  counter least significant byte first (little-endian, 16 bits). This is how the network carries them and must be
  kept.
- **DMR ID.** 0 to 16 777 215 (24 bits); 0 means "none". Higher bits do not fit and must not be sent.
- **Sequence counter.** Starts at 0 for every transmission and increases by one after each audio frame sent. It
  goes back to 0 after the end frame.
- **RSSI / status.** OpenGroundnut always sends 1. **Unverified:** the meaning and valid range; a value outside
  0–255 cannot be represented.
- **Reserved bytes 20 and 21.** Always zero. **Unverified:** their meaning.
- **Session number.** Identifies one transmission (one "over"). A new random value from **1 to 253** is chosen every
  time a transmission starts; after the end frame it is increased by one (modulo 256). Receivers use a change of
  session (or of callsign) to detect that a new transmission began. There is no negotiation and no protection
  against two stations choosing the same value.
- **Audio.** Exactly 320 bytes = 160 samples = 20 ms. The PCM bytes are sent as little-endian samples; a
  big-endian platform must swap them.

### 9.3 Audio frame (type 1)

Sent every 20 ms while transmitting: header with type `0x01`, followed by the 320 bytes captured from the
microphone (or from the radio interface).

### 9.4 End-of-transmission frame (type 16)

Sent once when a transmission ends: the same header with type `0x10` and **320 bytes of zeros** (silence), so the
frame keeps the full 350-byte length. After sending it the client increases the session number and resets the
sequence counter.

The end frame must always be sent, whatever ended the transmission (PTT released, transmit time-out, microphone
failure, room change refused, disconnection). OpenGroundnut guarantees this by sending it as the last step of the
transmit loop, and by sending it before `LOGOUT` when disconnecting.

---

## 10. Connection life cycle

### 10.1 States

```
          user presses Connect
 ┌─────────┐   (UDP socket opened,   ┌─────────────┐   ACK or first PING   ┌────────┐
 │ OFFLINE │ ─── LOGIN sent) ──────► │ CONNECTING  │ ────────────────────► │ ONLINE │
 └─────────┘                         └─────────────┘                       └────────┘
      ▲   ▲                              │      │                             │   │
      │   └──── REFU (no retry) ─────────┘      │                             │   │
      │                                         │ no answer after 5 LOGINs    │   │
      │                                         ▼ (watchdog, 15 s)            │   │
      │                                  ┌──────────────┐  no PING for 15 s  │   │
      │                                  │ RECONNECTING │ ◄──────────────────┘   │
      │                                  └──────────────┘                         │
      │                                    │ after 10 s: new socket, LOGIN        │
      │                                    └──────────► CONNECTING                │
      └──────────────── user presses Disconnect (end frame, LOGOUT) ─────────────┘
```

### 10.2 Connecting

1. Check that a callsign and an access code are configured and match, and that a room is chosen.
2. Resolve the master host and open a UDP socket connected to `(<master>, 6667)`.
3. Start a new **connection generation**: every worker thread of the connection carries this number and ends on its
   own when a newer connection replaces it.
4. Start the server watchdog ([section 14](#14-keepalive-watchdog-and-reconnection)).
5. Start the receive loop, which sends `LOGIN` (and repeats it every 2 s, up to 5 times, until answered).
6. Start the online-station monitor (`whois.json`) and, when the radio-link mode is VOX or a serial squelch line,
   the input loop.

Until the server answers, the station is **connecting**: transmitting is not allowed.

### 10.3 Link up

The link is up at the first `ACK` or `PING`, whichever comes first. Then the client:

1. records the moment as the last sign of life of the server;
2. sends a `PONG` to announce its room;
3. refreshes the list of stations in the room (`whois.json`);
4. reloads the room list (`rooms4.json`).

On `ACK` it also sends `INFO`.

**Observed:** the usual sequence is `LOGIN` → `ACK` → `INFO`, then periodic `PING`/`PONG`.

### 10.4 Disconnecting

In this order:

1. stop the room scanner, if running;
2. end any transmission in progress, **sending its end frame** while the socket is still open;
3. stop the watchdog;
4. send `LOGOUT`;
5. close the socket and let the worker threads end.

A disconnection asked for by the user cancels any pending automatic reconnection. A disconnection caused by a
silent server keeps the wish to be connected, so the reconnection can restore it.

---

## 11. Transmitting

### 11.1 Starting

A transmission can start only while the link is up and no transmission is in progress. In Manual mode, a new
transmission also waits until the microphone loop of the previous one has finished (it sends that transmission's end
frame); a PTT press that arrives earlier is ignored.

At the start the client:

1. chooses a new random session number (1–253) and resets the sequence counter to 0;
2. starts capturing audio: one 160-sample frame every 20 ms;
3. for each frame: when the sequence counter is 0 or 1, sends `PMSG` first; then sends the `DPCM` audio frame;
   then increases the counter.

### 11.2 What starts and ends a transmission

| Trigger | Start | End |
| --- | --- | --- |
| PTT button / Ctrl key | press | press again |
| VOX | input level above the threshold | after *delay* frames of silence |
| Serial squelch (CD, CTS or DSR line) | line becomes active | line drops |
| Transmit time-out | — | 30–300 s after the start (default 180 s) |
| Disconnection | — | always |

Automatic (VOX or squelch) transmissions are not started while the room is being heard, nor during a short
*return* hold after the network audio ends (time for a linked radio to go back to receive). After a transmission
ended by something else (time-out, button, disconnection), the input must go quiet once before VOX or squelch can
start a new one.

### 11.3 Ending

1. Stop capturing audio.
2. Send the end frame (type 16, silent audio).
3. Increase the session number; reset the sequence counter.

### 11.4 Room and transmission

The room **never changes during the client's own transmission**: every frame of one transmission must carry the
same room. A room change requested while transmitting is refused until the transmission ends.

### 11.5 Incoming audio while transmitting

Voice frames received while the client is transmitting are ignored.

---

## 12. Receiving

The receive loop reads one datagram at a time and dispatches it by prefix.

| Prefix | Action |
| --- | --- |
| `DPCM` | Voice handling, below. |
| `PING` | Note the server is alive; send `PONG`; mark the link up if it was not. |
| `ACK` | Send `INFO`; mark the link up if it was not. |
| `REFU` | Handle the refusal ([section 15](#15-login-refusal-refu)) and end the loop. |
| anything else | Ignore (`PMSG`, `PGPS`, unknown prefixes, empty datagrams). |

### 12.1 Voice handling

For each `DPCM` datagram:

1. Ignore it while the client itself is transmitting.
2. Ignore it when it is shorter than the 30-byte header.
3. Read the callsign (bytes 4–11, ASCII, spaces and anything outside `A–Z`, `0–9`, `/` removed), the frame type
   (byte 28) and the session number (byte 29).
4. The frame belongs to the **same transmission** as the previous one when both the callsign and the session number
   are unchanged.
5. **End frame (type 16):**
   - when it belongs to the transmission being heard: record that transmission as finished (callsign and duration),
     forget the current talker and, if enabled, play the short "roger beep";
   - otherwise (a repeated end frame, or one that arrives just after joining a room): ignore it.
6. **Audio frame:** play it only when the audio part is exactly **320 bytes**; otherwise ignore the frame.
   - When it starts a new transmission and another one was being heard without its end frame (another station took
     over), record the earlier one as finished first.
   - A new transmission also triggers the lookup of the station's picture, name and DMR ID.

The client considers itself **receiving** while an audio frame arrived during the last 600 ms; the state goes back
to idle by itself when the audio stops, even if no end frame arrives.

---

## 13. Rooms, room changes and scanning

- A room is identified by its name, at most 8 characters (longer names are cut by the 8-byte fields).
- **Joining a room** = sending a `PONG` carrying the new room, then using that room in every following voice frame.
  There is no explicit leave message: the previous room is left implicitly.
- After a room change the client refreshes the station list of the new room from `whois.json`.

### 13.1 Room scanner (client feature)

The scanner is built entirely on room changes; the server sees nothing special:

- it visits the chosen rooms in turn, staying 1000 ms in each by default (250–60 000 ms), announcing each one with a
  `PONG`;
- incoming audio, the client's own transmission and VOX/squelch activity pause the rotation; it resumes 5 s after
  the last voice frame;
- stopping the scanner returns to the room the station was in before scanning.

**Observed:** a short stay is enough for the server to start relaying a room's audio. **Unverified:** whether the
server rate-limits frequent room changes.

---

## 14. Keepalive, watchdog and reconnection

| Rule | Value |
| --- | --- |
| Server keepalive | `PING` from the server, answered with `PONG` |
| Watchdog check interval | every 5 s |
| Server considered silent | no `PING` (or `ACK`) for **15 s** |
| Wait before reconnecting | **10 s** |
| Reconnection attempts | repeated until success, until the user cancels or disconnects, or the program closes |

The watchdog watches the **incoming `PING`s**. The time of the last `PING` is measured with a monotonic clock, so
changes of the wall clock (daylight saving, NTP corrections) never trigger a false time-out.

When the server is silent for 15 s, the client drops the connection (end frame and `LOGOUT` are still sent), waits
10 s and connects again to the same server and room with a new socket and a new `LOGIN`. While a reconnection is
pending the user can cancel it.

A login that is never answered (no `ACK`, no `PING` after five `LOGIN`s) is caught by the same watchdog.

> **Observed:** the 15 s limit works against the public servers, which send `PING` every few seconds. The exact
> server interval is not documented; keep the limit comfortably above it.

---

## 15. Login refusal (REFU)

```
"REFU" + reason(1) [+ unknown]
```

| Byte 4 | Meaning shown to the user |
| --- | --- |
| 1 | Incorrect (callsign or code not accepted) |
| 2 | Wrong user / access code |
| 3 | Client must be upgraded (protocol version too old) |
| other, or missing | Unknown reason |

On `REFU` the client disconnects, tells the user the reason, and **does not retry automatically**: the server would
only refuse again, and repeated credential attempts are undesirable. A wrong callsign or code can then be corrected
in the settings.

**Unverified:** the exact difference between reasons 1 and 2 (the meanings are inferred from the user-visible
texts), and whether `REFU` carries more fields after the reason byte.

---

## 16. Audio format and playout

| Parameter | Value |
| --- | --- |
| Sample rate | 8000 Hz |
| Channels | 1 (mono) |
| Sample format | signed 16-bit, little-endian (PCM) |
| Samples per frame | 160 |
| Frame duration | 20 ms |
| Audio bytes per frame | 320 |
| Datagram size | 350 bytes |
| Bit rate (audio only) | 128 kbit/s |
| Bit rate on the wire | ≈ 140 kbit/s (350 bytes every 20 ms), plus UDP/IP headers |
| Compression | none |

### 16.1 Playout (jitter) buffer

UDP frames arrive at uneven moments. OpenGroundnut plays them from a separate thread through a small buffer:

- at most **25 frames** (500 ms) wait in the buffer; when the sound card falls behind, the **oldest** frame is
  dropped, so the delay never grows;
- after a pause of 100 ms or more, playback waits for **3 frames** (or 60 ms, whichever comes first) before starting,
  which absorbs short network delays;
- the network receive loop never waits for the sound card.

### 16.2 Roger beep

When the transmission being heard ends, the client may play a short local beep: 600 Hz for 120 ms at about 10 % of
full scale, 8 kHz mono. It is generated locally and never sent to the network.

### 16.3 Level

The audio level (used for the meter and by VOX) is the RMS value of the 160 samples of a frame, from 0 (silence) to
32 767 (full scale). Normal speech is a few hundred.

---

## 17. Timing summary

| Item | Value |
| --- | --- |
| Voice frame interval | 20 ms |
| `LOGIN` retry | every 2 s, at most 5 attempts |
| Server silence before reconnecting | 15 s without `PING` |
| Watchdog check | every 5 s |
| Reconnection delay | 10 s |
| First `whois.json` check after connecting | 3 s (plus one right after the link comes up) |
| `whois.json` refresh | every 20 s |
| `active.json` refresh | every 1 s, only while visible |
| `rooms4.json` refresh | every 10 min, and on every accepted connection |
| Directory retry while unavailable | 5 s, 10 s, 30 s, then every 60 s |
| Receiving state hold | 600 ms after the last audio frame |
| Transmit time-out | 30–300 s (default 180 s) |
| Scanner dwell | 1000 ms per room (250–60 000 ms) |
| Scanner resume | 5 s after the last voice frame |
| HTTP time-outs | 5 s connect, 15 s read |

---

## 18. Robustness rules for implementers

A receiver must assume nothing about what arrives. OpenGroundnut applies these rules; any new implementation
should too:

1. **Validate the source.** Accept datagrams only from the server address and port (a connected UDP socket does
   this).
2. **Check the length before reading fixed positions.** At least 30 bytes for any `DPCM`; an audio frame must carry
   exactly 320 bytes of audio; a `REFU` without its reason byte means "unknown reason".
3. **Dispatch by prefix**, and ignore unknown prefixes and empty datagrams.
4. **Never trust text fields.** Decode as ASCII with replacement, then keep only the expected characters.
5. **Track transmissions by (callsign, session).** Ignore end frames of transmissions that were never heard; treat a
   change of callsign or session as a new transmission even without an end frame.
6. **Never block the receive loop** on audio output, DNS, HTTP or the user interface.
7. **Bound every buffer**, dropping the oldest data when full.
8. **Always send the end frame** of every transmission, before `LOGOUT`.
9. **Do not retry after `REFU`**; do retry, with a delay, after a silent server.
10. **HTTP:** set time-outs, check the status code and the JSON shape, keep the previous data on failure, and never
    let a network error end the program.
11. **Use a monotonic clock** for every time-out.
12. **Keep each value within its field**: cut text fields, mask the DMR ID to 24 bits and the counters to their
    byte widths.

---

## 19. Security considerations

The Peanut protocol was designed for simplicity, not security. A client should be aware of these limits and not
make them worse.

| Area | Situation | What OpenGroundnut does |
| --- | --- | --- |
| Access code | Sent **in clear text** inside `LOGIN`; anyone on the path can read it. | Nothing can be done at protocol level. The code is stored owner-only on disk. |
| Access code strength | The code is a short number derived deterministically from the callsign, so it identifies more than it authenticates. | Treat it as a weak shared secret; never reuse it elsewhere. |
| UDP authentication | No session token, no challenge-response, no signature: control and voice datagrams can be forged by anyone who can send packets with the right source. | Accepts datagrams from the connected server address only. |
| Voice integrity | No MAC or tag on voice frames; no encryption. | — |
| Replay / reordering | No protection; the sequence counter is not checked by the client. | Session tracking limits the visible effect. |
| HTTP metadata | Public, unauthenticated; some hosts offer plain HTTP only. A forged server list could send a client to a hostile server that collects access codes. | HTTPS first, certificate always verified, plain HTTP only when the HTTPS port refuses the connection. |
| Denial of service | A long or malformed datagram must not crash a client. | Fixed-size receive buffer, length checks, every error caught and logged. |

Tests against the network must be done on a lab server or with the permission of the server operator, and captured
traffic must have callsigns and codes removed before it is shared.

---

## 20. Open questions

These points cannot be settled from the client side and need confirmation from the server side or from captures:

- whether current servers still accept every message in this document unchanged;
- the full `LOGIN` grammar: field limits, handling of a code longer than 8 digits;
- the official rules for `INFO`, `PONG` and `PMSG`; whether `LOGIN` must precede them;
- the meaning of the reserved bytes 20–21 and of the RSSI byte 27, and the valid range of byte 27;
- whether the sequence counter is per transmission, per room or per connection on the server side, and how the
  server handles its wrap-around;
- the full catalogue of server messages (`PING`, `ACK`, `REFU`, `PGPS`, others) and the complete layout of `REFU`;
- whether `PGPS` carries a position;
- room join semantics on the server, and any rate limit on room changes;
- the server `PING` interval, its own time-out for silent clients, and any abuse control;
- the official JSON schemas of `masters.json`, `rooms4.json`, `whois.json` and `active.json`, their stability, and
  the format of `startPTT2`;
- server behaviour with malformed messages, long callsigns, duplicated and reordered datagrams.

---

## 21. Validation checklist for a new implementation

1. Confirm the `master` host of the chosen server and that UDP port 6667 answers.
2. Capture a complete session of a working client and compare every length with [Appendix A](#appendix-a-message-length-summary).
3. Capture `LOGIN` → `ACK` → `INFO` → `PING`/`PONG` and compare with [section 10](#10-connection-life-cycle).
4. Check what the server does with `INFO`, `PONG` and `DPCM` sent before `LOGIN` (expect them to be ignored).
5. Check the meaning of DPCM bytes 20, 21 and 27.
6. Check sequence numbering, its wrap-around and the session number change after the end frame.
7. Test simultaneous sessions, room changes, `LOGOUT`, and lost, duplicated and reordered datagrams.
8. Test short replies, unknown prefixes and malformed datagrams; confirm a wrong code is rejected with `REFU` and
   that the client does not keep retrying.
9. Validate the four JSON documents against real responses (with callsigns removed).
10. Compare reception and playback with known PCM blocks; check `startPTT2` parsing on several servers.
11. Run every test on a lab network or with the authorisation of the server operator.

---

## 22. Related services used by the client

These services are not part of the Peanut protocol but complete the station experience. All requests follow the
HTTP rules of [section 4.1](#41-request-rules-opengroundnut).

| Service | Address | Use |
| --- | --- | --- |
| RadioID user list | `https://database.radioid.net/static/user.csv` | Name, city, state, country and DMR ID of a callsign. Downloaded on first start and on demand; stored locally in 256 small files. |
| RadioID API | `https://radioid.net/api/dmr/user/?callsign=<CALL>` | DMR IDs registered for the station's own callsign. A `404` means "none". |
| QRZ.com XML | `https://xmldata.qrz.com/xml/current/` | Picture of a station (needs a QRZ.com subscription with XML data). |
| QRZ.com public page | `https://www.qrz.com/db/<CALL>` | Picture of a station when no XML account is configured. QRZ.com's stock "no photo" image counts as no picture. |
| QRZ.com Logbook API | `https://logbook.qrz.com/api` | Logbook upload (`ACTION=INSERT`). |
| eQSL.cc | `https://www.eQSL.cc/qslcard/ImportADIF.cfm` | Logbook upload as an ADIF file. |
| APRS-IS | configured host:port, TCP (default `rotate.aprs2.net:14580`) | Position beacon. |

### 22.1 APRS position beacon

When enabled, the client sends its position to APRS-IS at the start of a transmission, at most once every 30
minutes:

| Item | Value |
| --- | --- |
| Source | base callsign + `-10` (the APRS SSID for Internet-linked stations) |
| Destination (tocall) | `APZPNT` (from the block reserved for experimental software) |
| Path | `TCPIP*` |
| Format | timestamped position `@DDHHMMz`, symbol table `/`, symbol `-`, comment `via OpenGroundnut` |
| Login | base callsign with its standard APRS-IS passcode |

Example:

```
N0CALL-10>APZPNT,TCPIP*:@101530z3352.20S/15112.60E-via OpenGroundnut
```

### 22.2 ADIF export

Logbook records are exported as ADIF 3.1.4 with `MODE=DIGITALVOICE`, `RST_RCVD=59` and `RST_SENT=59`.

---

## 23. Where each part lives in the source

| Topic | File | Functions |
| --- | --- | --- |
| Endpoints, port, versions, device name | `src/bootstrap.py` | `PEANUT_UDP_PORT`, `MASTERS_URL_PATH`, `DEFAULT_MASTER`, `PROTOCOL_VERSION`, `DEVICE_NAME` |
| Field encoding | `src/bootstrap.py` | `ascii_text`, `ascii_field`, `clean_callsign` |
| HTTPS-first rule | `src/bootstrap.py` | `http_get_with_fallback`, `_https_port_refused` |
| UDP socket | `src/network.py` | `open_udp_socket`, `send_datagram`, `close_udp_socket` |
| Control messages | `src/network.py` | `login`, `info`, `pong`, `send_room_message`, `logout`, `handle_refusal` |
| Voice frames | `src/network.py` | `_dpcm_header`, `send_audio_frame`, `send_end_of_transmission` |
| Receive loop and playout | `src/network.py` | `receive_loop`, `_playout_loop` |
| Transmit loops | `src/network.py` | `manual_transmit_loop`, `vox_transmit_loop` |
| Starting and ending a transmission | `src/audio.py` | `start_transmit`, `stop_transmit`, `auto_ptt_start` |
| Connection, watchdog, reconnection | `src/core.py` | `connect_to_server`, `mark_link_up`, `disconnect_from_server`, `_server_watchdog`, `schedule_reconnect` |
| Directory and monitors | `src/core.py` | `load_server_list`, `load_room_list`, `active_monitor_loop`, `online_monitor_loop` |
| Room change | `src/core.py` | `enter_room` |
| Scanner | `src/settings.py` | `scanner_start`, `scanner_room`, `scanner_stop` |
| `startPTT2` parsing | `src/gui.py` | `_gui_transmission_time` |
| Local access-code check | `src/utils.py` | `access_code_for` |
| APRS | `src/aprs.py` | `aprs_string`, `send_aprs` |
| Tests of the frame layout | `tests/test_core.py` | `test_voice_frame_header_layout`, `test_text_fields_are_ascii_and_right_aligned` |

Run the client with `--debug` to log every UDP datagram sent and received, in ASCII and in hex.

---

## 24. Glossary

| Term | Meaning |
| --- | --- |
| Master | A Peanut server; also the `master` field that gives its host. |
| Room | A talk group on a server; at most 8 characters on the wire. |
| Callsign | The station's amateur-radio identifier. |
| Access code | Number obtained by registration, sent with `LOGIN`; not the DMR ID. |
| DMR ID | Optional numeric identifier (24 bits) carried in voice frames. |
| Session | One transmission ("over"), identified by the session byte. |
| End frame | `DPCM` frame of type 16 that closes a transmission. |
| PCM | Uncompressed digital audio. |
| PTT / VOX | Push-to-talk / voice-operated transmission. |
| Squelch line | Radio output that signals a received carrier, read through a serial control line. |
| RSSI | Received signal strength indicator. |
| Datagram | One independent UDP packet. |
| Watchdog | Client timer that detects a silent server. |

---

## Appendix A: message length summary

| Message | Length | Breakdown |
| --- | --- | --- |
| `LOGIN` | 21 | 5 + 8 + 8 |
| `LOGOUT` | 6 | 6 |
| `INFO` | 37 | 4 + 8 + 20 + 5 |
| `PONG` | 20 | 4 + 8 + 8 |
| `PMSG` | 32 | 4 + 8 + 20 |
| `DPCM` audio | 350 | 20 + 10 + 320 |
| `DPCM` end | 350 | 20 + 10 + 320 (zeros) |
| `ACK` | ≥ 3 | prefix only is examined |
| `PING` | ≥ 4 | prefix only is examined |
| `REFU` | ≥ 5 | 4 + reason byte |

Lengths assume every field is cut to its width, as OpenGroundnut does.

---

## Appendix B: annotated examples

All examples use the placeholder callsign `N0CALL`, access code `12345`, room `TEST`, DMR ID 1 234 567
(`0x12D687`), sequence `0x0102` and session 7. They are illustrations of the layout, not real credentials.

### B.1 LOGIN (21 bytes)

```
LOGIN␠␠N0CALL␠␠␠12345

4c 4f 47 49 4e                    "LOGIN"
20 20 4e 30 43 41 4c 4c           "␠␠N0CALL"
20 20 20 31 32 33 34 35           "␠␠␠12345"
```

### B.2 INFO (37 bytes)

```
49 4e 46 4f                       "INFO"
20 20 4e 30 43 41 4c 4c           "␠␠N0CALL"
20 20 20 20 20 20 20 20 20 20
20 20 20 57 49 4e 44 4f 57 53     "␠␠␠␠␠␠␠␠␠␠␠␠␠WINDOWS"
20 30 2e 31 31                    "␠0.11"
```

### B.3 PONG (20 bytes)

```
50 4f 4e 47                       "PONG"
20 20 4e 30 43 41 4c 4c           "␠␠N0CALL"
20 20 20 20 54 45 53 54           "␠␠␠␠TEST"
```

### B.4 PMSG (32 bytes)

```
50 4d 53 47                       "PMSG"
20 20 20 20 54 45 53 54           "␠␠␠␠TEST"
20 20 20 20 20 20 20 20 20 20
20 20 20 20 20 48 65 6c 6c 6f     "␠␠␠␠␠␠␠␠␠␠␠␠␠␠␠Hello"
```

### B.5 DPCM audio header (first 30 of 350 bytes)

```
0000  44 50 43 4d 20 20 4e 30 43 41 4c 4c 20 20 20 20   DPCM␠␠N0CALL␠␠␠␠
0010  54 45 53 54 00 00 12 d6 87 02 01 01 01 07         TEST..........

      44 50 43 4d                 "DPCM"
      20 20 4e 30 43 41 4c 4c     callsign  "␠␠N0CALL"
      20 20 20 20 54 45 53 54     room      "␠␠␠␠TEST"
      00 00                       reserved
      12 d6 87                    DMR ID 1234567, big-endian
      02 01                       sequence 0x0102, little-endian
      01                          RSSI / status
      01                          frame type: audio
      07                          session 7
      … 320 bytes of PCM follow
```

The end frame of the same transmission has byte 28 = `10` and 320 zero bytes of audio.

### B.6 A short session

```
Client                                         Server
  │  GET masters.json, GET rooms4.json  (HTTP)    │
  │ ─── LOGIN ␠␠N0CALL␠␠␠12345 ───────────────► │
  │ ◄────────────────────────────────── ACK ─── │
  │ ─── INFO ␠␠N0CALL … WINDOWS ␠0.11 ────────► │
  │ ─── PONG ␠␠N0CALL␠␠␠␠TEST ────────────────► │   room announced
  │ ◄───────────────────────────────── PING ─── │
  │ ─── PONG ␠␠N0CALL␠␠␠␠TEST ────────────────► │
  │                                              │
  │ ◄──── DPCM W1AW … type 1, session 42 ────── │   another station talks
  │ ◄──── DPCM W1AW … type 1, session 42 ────── │   (every 20 ms)
  │ ◄──── DPCM W1AW … type 16, session 42 ───── │   end of its transmission
  │                                              │
  │ ─── PMSG ␠␠␠␠TEST … Hello ────────────────► │   user presses PTT
  │ ─── DPCM N0CALL … seq 0, type 1, session 7 ►│
  │ ─── PMSG ␠␠␠␠TEST … Hello ────────────────► │
  │ ─── DPCM N0CALL … seq 1, type 1, session 7 ►│
  │ ─── DPCM N0CALL … seq 2 … (every 20 ms) ───►│
  │ ─── DPCM N0CALL … type 16, session 7 ──────►│   user releases PTT
  │                                              │
  │ ─── LOGOUT ───────────────────────────────► │   user disconnects
```

---

## Appendix C: minimal client walkthrough

A minimal, receive-and-talk client needs only the following steps. Error handling is omitted for brevity; apply
[section 18](#18-robustness-rules-for-implementers) in real code.

```python
import random
import socket
import time

PORT = 6667


def field(text, width):
    """Fixed-width, right-aligned ASCII field."""
    return text.encode("ascii", "ignore")[:width].rjust(width)


def header(call, room, dmr_id, sequence, frame_type, session):
    return (
        b"DPCM" + field(call, 8) + field(room, 8)
        + bytes((0, 0,
                 (dmr_id >> 16) & 255, (dmr_id >> 8) & 255, dmr_id & 255,
                 sequence & 255, (sequence >> 8) & 255,
                 1, frame_type, session & 255))
    )


def run(master, call, code, room):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect((socket.gethostbyname(master), PORT))
    sock.settimeout(0.5)

    sock.send(b"LOGIN" + field(call, 8) + field(code, 8))
    last_ping = time.monotonic()

    while time.monotonic() - last_ping < 15:
        try:
            packet = sock.recv(2048)
        except socket.timeout:
            continue
        if packet.startswith(b"ACK"):
            sock.send(b"INFO" + field(call, 8) + field("WINDOWS", 20) + field("0.11", 5))
            sock.send(b"PONG" + field(call, 8) + field(room, 8))
        elif packet.startswith(b"PING"):
            last_ping = time.monotonic()
            sock.send(b"PONG" + field(call, 8) + field(room, 8))
        elif packet.startswith(b"REFU"):
            print("refused, reason", packet[4] if len(packet) > 4 else 0)
            return
        elif packet.startswith(b"DPCM") and len(packet) >= 30:
            talker = packet[4:12].decode("ascii", "replace").strip()
            if packet[28] == 1 and len(packet) - 30 == 320:
                pcm = packet[30:]          # 160 samples, 16-bit LE, 8 kHz: play it
            elif packet[28] == 16:
                print(talker, "stopped talking")

    sock.send(b"LOGOUT")
    sock.close()


def transmit(sock, call, room, dmr_id, frames, message=""):
    """Send one transmission: `frames` is an iterable of 320-byte PCM blocks."""
    session = random.randrange(1, 254)
    sequence = 0
    for pcm in frames:
        if sequence < 2:
            sock.send(b"PMSG" + field(room, 8) + field(message[:20], 20))
        sock.send(header(call, room, dmr_id, sequence, 1, session) + pcm)
        sequence += 1
        time.sleep(0.02)
    sock.send(header(call, room, dmr_id, sequence, 16, session) + bytes(320))
```

The complete, production version of each step is listed in [section 23](#23-where-each-part-lives-in-the-source).
