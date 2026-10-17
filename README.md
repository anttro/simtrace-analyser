# SIMtrace Analyser

English | [Русский](README_RUS.md)

APDU trace analyser for the GSMTAP-SIM format — captures SIM/UICC
communication from a UDP GSMTAP stream (or imports PCAP/PCAPNG files),
decodes it, and serves an installable web app for browsing.  The repository
also bundles **simtrace2-pysniff**, a Python replacement for
`simtrace2-sniff` that captures from Osmocom SIMtrace2 hardware and can feed
GSMTAP into this analyser.

![SIMtrace Analyser PWA](frontend.png)

## Components

- **Analysis server + PWA** (`simtrace-analyser-server`) — stores captured
  traffic in SQLite, decodes it, and serves the PWA ([`frontend/`](frontend/))
  plus the HTTP API on a single origin.  Three capture modes: a GSMTAP
  listener, direct SIMtrace2 hardware capture, or disabled (browse existing
  captures only).
- **Capture utility** (`simtrace2-pysniff`) — captures SIMtrace2 hardware
  traffic and writes it to stdout, GSMTAP (Wireshark), or PCAP files.  It is
  one GSMTAP source of several that the analyser accepts (see also
  [sigrok_iso7816_stream](https://github.com/anttro/sigrok_iso7816_stream)).
- **PWA** ([`frontend/`](frontend/)) — trace browser with decoded APDU,
  SIM Toolkit, SMS and SCP80 OTA detail; sessions, PCAP and COMPRION trace
  import, EN/RU UI.

## Features

**APDU decoder** (server-side, rendered by the PWA):

- Full APDU decode — CLA per ISO 7816-4 / ETSI coding with the **logical
  channel 0-19** (standard channels from b2-b1, the extended channels 4-19
  from b4-b1 per TS 102 221 §10.3), secure messaging and command chaining,
  INS names from a spec table, SFI-aware P1/P2 for READ/UPDATE BINARY and
  record commands; MANAGE CHANNEL replies show the channel the card
  assigned
- Status words — full ISO 7816-4 set plus UICC-specific values:
  `91XX` (proactive command pending), `62F1/F2/F3`, `63F1/F2` (more data),
  `9300` (SAT busy), `9850`, `9862–64`
- SIM Toolkit — SAT (GSM 11.14), CAT (TS 102 223) and USAT (TS 31.111)
  proactive commands with decoded qualifiers, TERMINAL RESPONSE, ENVELOPE
  (Menu Selection, Call Control, SMS-PP download…); tolerates known
  non-compliant legacy-card quirks and preserves unrecognized TLVs
- TERMINAL CAPABILITY (TS 102 221 §11.1.19) — terminal power supply
  (voltage class, maximum current, clock), extended logical channels,
  additional interfaces (UICC-CLF) and eUICC device capabilities
  (SGP.22/SGP.32)
- SMS TPDU — SMS-DELIVER/SUBMIT, SCTS timestamps, UDH information elements
- SCP80 OTA secured packets — SPI bits (ciphering, PoR requirement/mode,
  RC/CC/DS, counter), KIc/KID algorithm + key set, TAR, CNTR/PCNTR;
  Response Packet (PoR) decode on GET RESPONSE; **optional client-side
  decryption** of ciphered packets — paste the card's 3DES/AES key in the
  detail view to reveal the real CNTR and secured application data (the
  key stays in the browser, in-memory only; ciphered on-wire CNTR/PCNTR/RC
  are ciphertext and labeled as such); the secured application message is
  decoded as a stream of **C-APDUs** (SELECT, UPDATE BINARY, …) with
  full CLA/INS/P1/P2/Lc/Le breakdown — plaintext immediately, or after
  decryption for ciphered packets
- ATR parse (clock-rate conversion, Fi/Di, T-bitmask, truncated-ATR safe)
  and FCP/FCI TLV; the historical bytes are decoded as the UICC's
  COMPACT-TLV objects (TS 102 221 §6.3.1) — card service data, the **card
  capabilities** (ISO 7816-4 §8.1.1.2.7 Table 88: the assignment methods
  and the announced maximum number of logical channels, `8 or more` for the
  extended-capable cards) and the trailing status indicator (LCS/SW)

**SIMtrace Analyser PWA** ([`frontend/`](frontend/)):

- Trace view with Map/List modes — proactive, TERMINAL RESPONSE, ENVELOPE
  and AUTH commands get distinctive styling in map view
- Sessions with deep links (`#session=N`), PCAP import (`.pcap/.pcapng/.cap`),
  COMPRION trace import (the Device Manager *ISO Protocol Layer* text export),
  search and type filtering
- Installable PWA, dark theme, English/Russian UI

## Prerequisites

- **Python 3.9+**
- **PyUSB** — `pip install pyusb` (needed only for capture from SIMtrace2
  hardware; GSMTAP/UDP capture and PCAP import work without it)
- **libusb** — system library, present by default on Linux; on Windows the
  SIMtrace2 driver must be swapped (see [USB Device Access](#usb-device-access))
- **SIMtrace2 hardware** running firmware in *trace* mode (only for direct
  capture; VID `1d50`, PID `60e3`, USB class `ff`, subclass `01`). For
  building and flashing trace firmware, see the
  [upstream SIMtrace2 project](https://gitea.osmocom.org/sim-card/simtrace2).

No other dependencies. PCAP, GSMTAP, and hex dump output use only Python stdlib.

## Install

```sh
git clone https://github.com/anttro/simtrace-analyser.git
cd simtrace-analyser
pip install pyusb
```

Or install the package into your environment:

```sh
pip install -e .
# then run: simtrace-analyser-server [opts]
# or:       simtrace2-pysniff [opts]
```

## Running

### Analysis server + PWA (`simtrace-analyser-server`)

Stores captured APDU traffic in SQLite and serves it over HTTP, together with
the bundled **SIMtrace Analyser** PWA (`frontend/`) on the same origin.  Three
capture modes:

```sh
# Listen for GSMTAP from simtrace2-pysniff (or original simtrace2-sniff):
simtrace-analyser-server --capture gsmtap

# Capture directly from SIMtrace2 hardware (no external tool needed):
simtrace-analyser-server --capture direct

# Browse/analyse existing captures without a capture backend:
simtrace-analyser-server --capture disabled
```

The server logs its capture liveness to stderr (each line timestamped
with the local time): `Capture started` on begin, a periodic
`Capture alive: session=N messages=M bytes=B dropped=D` heartbeat, and
`Capture stopped` (or `ERROR: capture thread stopped on error …` if the
capture thread died unexpectedly). A mis-framed or non-SIM GSMTAP
datagram is dropped and counted (`dropped`) rather than silently
killing the capture; a `tpdu` packet that is not APDU-shaped at all
(shorter than the header, the invalid CLA `FF` or an ISO-reserved class)
is skipped and counted (`skipped`) — a character-level or mis-sampled
stream no longer pollutes the decode. The heartbeat interval defaults to 60 s and is
tunable via `--log-interval SECONDS`.

The GSMTAP listener also accepts the **sigrok-iso7816-stream** decoder
(https://github.com/anttro/sigrok_iso7816_stream) — an FX2-logic-analyzer
passive SIM sniffer that emits the same GSMTAP-SIM format on UDP 4729. Its
standard PPS request/response sub-types (`0x02`/`0x03`) are decoded as PPS,
and its custom sub-types for RST/VCC line events (`0x10`/`0x11`, added for
compatibility with that project) are decoded as `RESET ASSERTED` /
`RST de-asserted — ATR follows` and `VCC ON/OFF` timeline markers, and a
reset-assert or power-removal
correctly invalidates the file-selection tracking. When an RST event carries
the measured CLK frequency (decoder v1.9.0+, optional payload extension), the
following ATR is annotated with the CLK frequency, data rate and ETU derived
from its TA1 Fi/Di (`data_rate = clk_hz × D / F`); the measurement is
consumed by the ATR so a later ATR without a reset gets no stale rate (a
late-arriving measurement is backfilled onto the ATR it belongs to). GSMTAP
packets carrying the `GSMTAP_FLAG_BAD_FCS` desync flag (set by that decoder
on mis-framed exchanges) are surfaced as a flagged/desynced entry in the
capture timeline, so such artefacts are easy to spot when reviewing a capture
rather than silently altering the decode.

### COMPRION text export import

The **Import COMPRION trace** button accepts the tab-separated **ISO Protocol
Layer** export of COMPRION's Device Manager — the byte-accurate protocol view
(ATR, PPS, APDUs with their return codes). The *ISO Application Layer* export
carries no raw response bytes and is not needed; selecting it answers with a
pointer to the Protocol Layer file (the same check runs in the PWA before the
upload and on the server for API callers).

Exchanges are re-encoded into the same wire-shaped TPDUs a GSMTAP capture
carries (a case-4 exchange becomes the command, a `61 xx` status word and a
GET RESPONSE with the response data and the final SW), so command/response
pairing, FCP/file decoding and the filters behave exactly as for a live
capture.

**Exact timestamps:** the import dialog asks for the *ISO Protocol Layer*
export (required) and, optionally, the matching *ISO Application Layer*
export — two separate pickers, both file names visible, and an error stays in
the dialog until it is fixed or cancelled. With both files the Application
Layer's per-exchange wall-clock times become the trace's timeline — the
session window and the inter-APDU gaps are then exact; without it the
timeline is the estimate described below. Before anything is imported the
two files are verified to belong to the same session (`Session Name`,
falling back to `Working directory`; the export timestamps of the two layers
differ and are not compared) and their exchange counts must align (the two
exports must cover the same set of exchanges) — a mismatch refuses the import
instead of mixing sessions. The ATR and the PPS exchange have no Application
Layer blocks, so they carry the timestamp of the preceding exchange.

**Protocol Layer alone:** the `Delay` column measures only card/line activity
— host pauses between APDU bursts are absent — so the timeline keeps the
message order and the short-term gaps but is much shorter than the real
session. Its unit comes from an assumed 3.8 MHz interface clock (`CLK_HZ` in
`simtrace_analyser/comprion.py`), which is a scale, not a measurement: the
export carries no CLK, and the import deliberately does not invent one (the
ATR shows the F/D the file states, with no data-rate/ETU annotation, unlike
a capture from the sigrok-iso7816-stream sniffer). The session's wall-clock
window is taken from the file's `Session Name` timestamp when it carries
one.

Exchanges larger than 255 bytes (extended-length APDUs) cannot be represented
in the stored wire shape and are skipped with a note in the import report.

### Files view (per-file tracking)

The Trace tab has a view selector (*Map* / *Stats* / **Files**) in its topbar,
right-aligned over the side panel with the panel's width, so it stays visible
while the panel scrolls (a drop-down, since three tab captions no longer
fit).  The Files view is a
trace-wide timeline of file operations — every **Read** and **Update** row
shows the same file name as the Map view (a card-side change appears as a
read with a **Changed on card!** link that opens its details), and clicking
a row jumps straight to the APDU in the trace and leaves it highlighted
until another one is focused (the APDU list keeps the reader's position:
new messages pin the view to the bottom only while the reader is already
there, so a jump is never pulled away or un-highlighted by the live poll).  Rows that carry a recorded change (a
card-side change, or an update that wrote or first observed bytes) also offer
**Details**: a modal showing the full file path (`MF/EF_ICCID (2FE2)`,
`ADF/EF_IMSI (6F07)`, `DF_GSM_ACCESS/EF_KcGPRS (4F52)`, `AID …/4F09` — the DF
named from the EF.DIR labels when known) and the affected unit — the whole
file, or the single record that changed — **before and after** the change, as
hex views (16 bytes per row, never-observed bytes drawn as `--`) with the bytes
that changed highlighted in one colour and the bytes the operation first
observed in another, the changed/new byte counts, the APDU reference and the
colour legend below the views.

The images come from `GET /api/sessions/<id>/files/image?key=…&change=…` and
are reconstructed from the current image by undoing the later changes
(`filetrack.FileTracker.change_images`) — nothing is duplicated per event.
Every value change is recorded, so the values are exact; a byte that was only
*first observed* after the selected change can appear as known in both views.

The data comes from `simtrace_analyser/filetrack.py`
(`GET /api/sessions/<id>/files`), a single-pass tracker over the decoded
session that keeps, keyed by (DF, FID) and **across card resets**: access
counters (`select`/`read`/`update`, successful operations only), a sparse image
of the observed contents and the change log.  Device-initiated changes are the
UPDATE operations seen in the trace; card-initiated ones are inferred when a
read returns bytes differing from what the image already knew — bytes never
seen before just fill the image (an observation, not a change).  Files reached
by SFI share the entry of their path/FID accesses: the SFI ↔ FID relations come
from the normative tables (TS 102 221 Annex H.1 and the TS 31.102 H.1–H.12
annexes; the ISIM SFI rows come from TS 31.103) and from every
surfaced FCP carrying the `88` DO, including the spec's "SFI = the 5 LSBs of the
FID" rule when the DO is absent; an SFI used before its relation is learned
stays provisional and merges into the resolved entry.  A file's DF context
follows TS 102 221 §8.4/Table 8.2 (selecting an EF leaves its parent DF current,
a path selection included); applications selected by an unknown AID get the AID
as their DF identity, named from EF.DIR when the trace surfaced it.  Bounds: the
image freezes past 64 KB of observed bytes per file (`image_truncated`) and the
change log keeps the last 1000 events per file (`changes_total` keeps counting).
Counters are returned by the API but not shown in this view yet.

File names are **DF-scoped**: `simtrace_analyser/ef_tables.py` holds the complete
per-DF file tables and SFI lists extracted from the pinned specs (TS 102 221,
TS 31.102 including its H.1–H.12 SFI annexes, TS 31.103, TS 51.011), so a FID
reused across DFs resolves to the file its DF context names — `4F09` is
EF_SUPI_NAI under DF_5GS but EF_PROSE_GC under DF_ProSe, `6F07` is EF_IMSI in
the USIM/SIM but EF_IST in the ISIM, `6F4E` is EF_EXT4 in DF_TELECOM but
EF_EXT5 in the USIM ADF — with the flat table as the fallback when no DF is
known.  `tests/extract_spec_tables.py` regenerates the pinned fixture
(`tests/data/spec_files.json`) and `--check` re-verifies the tables against the
PDFs.

Server options:

```
--host ADDR          HTTP bind address (default: 127.0.0.1)
--port PORT          HTTP server port (default: 8081)
--db FILE            SQLite database path (default: ~/.simtrace-analyser/sessions.db)
--capture MODE       gsmtap | direct | disabled  (default: gsmtap)
--gsmtap-port PORT   UDP port for the GSMTAP listener (default: 4729)
--web-dir PATH       PWA static files directory (default: <repo>/frontend)
```

Then open **http://127.0.0.1:8081/** in a browser — the PWA is served by the
server, so the UI and the API share an origin and no CORS/Private-Network-Access
setup is involved.  Use `--web-dir PATH` to serve a different PWA directory
(default: `<repo>/frontend`).

### Hosted PWA (landing page)

A standalone copy of the PWA is hosted at **https://simtrace.atroshin.ru**.
It is a pure frontend: point it (Settings → Server URL) at a locally running
`simtrace-analyser-server`.

> **Browser restriction:** when the PWA is served from a public HTTPS host,
> reaching a local server (`http://127.0.0.1:8081`) requires two things: the
> server must send `Access-Control-Allow-Private-Network: true` (this server
> does), and the browser must be allowed to access the local network — in
> Chrome/Edge/Vivaldi: Site settings → Local network access → allow the site
> (or accept the permission prompt).  Without the browser permission, the
> request to `127.0.0.1` is blocked before any preflight is sent.

### Capture utility (`simtrace2-pysniff`)

Captures SIMtrace2 hardware traffic and writes it to stdout, GSMTAP
(Wireshark), or PCAP files.  It is the bundled replacement for the original
Osmocom `simtrace2-sniff`.

The `./sniff-start.sh` startup script performs a pre-flight USB permission
check (prints udev install instructions if the SIMtrace2 device is not
writable) and then launches the Python module. On Windows, use
`sniff-start.bat` with the same options (no permission check needed).

```sh
./sniff-start.sh
./sniff-start.sh --format timestamp
./sniff-start.sh --gsmtap 127.0.0.1:4729
./sniff-start.sh --pcap trace.pcap --format atr-time
```

OPTIONS can also be set via environment variables:

```sh
FORMAT=timestamp GSMTAP=127.0.0.1 ./sniff-start.sh
```

Cross-platform module invocation:

```sh
python -m simtrace2_pysniff
python -m simtrace2_pysniff --format timestamp --gsmtap 127.0.0.1:4729
python -m simtrace2_pysniff --pcap trace.pcap
```

If installed via `pip install -e .`, use the console script directly:

```sh
simtrace2-pysniff --format atr-time
```

## USB Device Access

Required for capture from SIMtrace2 hardware (the utility and the server's
`--capture direct` mode); not needed for GSMTAP or PCAP sources.

### Linux

A udev rule is required for non-root USB access to the SIMtrace2 device.

```sh
sudo cp 70-simtrace2-pysniff.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Then reconnect the SIMtrace2 USB cable. The rule uses `TAG+="uaccess"`
(systemd-logind ACL) — no group membership or world-writable permissions needed.

### Windows

Windows does not ship a libusb-compatible driver for SIMtrace2. Use
[Zadig](https://zadig.akeo.ie/) to replace the default driver:

1. Download and run **Zadig**
2. Plug in the SIMtrace2 device
3. Select it in the dropdown (VID `1D50`, PID `60E3` — "Osmocom SIMtrace 2")
4. Choose **WinUSB** (or libusbK) as the replacement driver
5. Click **Replace Driver** (one-time operation)

After that, `python -m simtrace2_pysniff` works identically to Linux.

## Utility CLI Options

```
python -m simtrace2_pysniff [OPTIONS]

  --format, -f FORMAT       Output format (default: hex)
                            hex       — plain hex dump
                            timestamp — TPDU lines prefixed with [HH:MM:SS.mmm]
                            atr-time  — TPDU lines prefixed with [SSSS.mmm] from last ATR
  --gsmtap HOST[:PORT]      Send ATR/TPDU as GSMTAP over UDP (default port 4729)
  --pcap FILE               Write sniffed data to PCAP file for Wireshark
  --output, -o FILE         Write hex dump to file
  --no-stdout               Suppress hex dump to stdout
  --vendor HEX              USB vendor ID (default: 0x1d50)
  --product HEX             USB product ID (default: auto-detect)

Recovery options:
  --no-reconnect            Exit on USB disconnect instead of reconnecting
  --reconnect-delay-min SEC Minimum reconnect delay (default: 1.0)
  --reconnect-delay-max SEC Maximum reconnect delay cap (default: 30.0)
  --backoff-factor N        Exponential backoff multiplier (default: 1.5)
  --inactivity-timeout SEC  Reconnect after N seconds of silence (default: disabled)
```

## Output Formats

- **`hex`** (default): plain hex dump — `ATR: 3b 9e ...`, `TPDU: a0 a4 00 00 02 3f 00`
- **`timestamp`**: TPDU lines prefixed with local time — `[14:32:05.123] TPDU: a0 a4 00 00 02 3f 00`
- **`atr-time`**: TPDU lines prefixed with seconds since last ATR — `[0001.234] TPDU: a0 a4 00 00 02 3f 00`

Non-TPDU messages (ATR, PPS, card state changes, Fi/Di) print identically in all formats.

- **GSMTAP**: ATR and APDU messages over UDP (port 4729) to Wireshark
- **PCAP**: ATR/TPDU messages as Ethernet/IP/UDP/GSMTAP packets, openable in Wireshark

## Background / Daemon

SIGHUP is automatically ignored when stdin is not a terminal (i.e. run in
background or via a pipe). Foreground terminal sessions still respond to
SIGHUP normally.

To run persistently in the background with output to files:

```sh
nohup ./sniff-start.sh --output /tmp/sniff.log &> /tmp/sniff-err.log &
# or
FORMAT=timestamp nohup python -m simtrace2_pysniff --output /tmp/sniff.log &> /tmp/sniff-err.log &
```

## Library Usage

```python
from simtrace2_pysniff import SniffSession

session = SniffSession(inactivity_timeout=30.0)
for msg in session.iter_messages():
    print(f"{msg.type}: {msg.data.hex()}")
```

## Recovery

The utility survives hardware resets, cable disconnects, and firmware hangs
by default — it reconnects with exponential backoff (1s → 30s cap).
Use `--inactivity-timeout` to also trigger reconnect on silent firmware hangs.

## Related

- **[simtrace2](https://gitea.osmocom.org/sim-card/simtrace2)** — the upstream
  SIMtrace2 hardware/firmware project that the capture utility sniffs from.
- **[sigrok_iso7816_stream](https://github.com/anttro/sigrok_iso7816_stream)** —
  FX2LP-based passive ISO 7816 sniffer that emits the same GSMTAP-SIM stream
  on UDP 4729 (accepted by this project's GSMTAP listener).
