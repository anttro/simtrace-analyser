# simtrace-analyser

PWA frontend for browsing SIMtrace2 APDU traces. Connects to
[`simtrace2-pysniff-server`](https://github.com/anttro/simtrace2-pysniff)
to view live captures and saved sessions, decode APDUs, and export to PCAP.

## Try it now

A live instance is hosted at:

**[https://simtrace.atroshin.ru](https://simtrace.atroshin.ru)**

> Note: the PWA is a pure frontend — it still needs a local
> [`simtrace2-pysniff-server`](https://github.com/anttro/simtrace2-pysniff)
> to capture data. Point the URL in Settings at your server.

## Setup

```sh
git clone https://github.com/anttro/simtrace-analyser.git
cd simtrace-analyser
python3 -m http.server 8000
```

Open `http://127.0.0.1:8000` in a browser.  The PWA connects to the
server at `http://127.0.0.1:8081` by default (configurable in Settings).

## Requirements

- [`simtrace2-pysniff`](https://github.com/anttro/simtrace2-pysniff) — the
  server component (`simtrace2-pysniff-server`)
- A modern browser with JavaScript enabled

No other dependencies — static HTML + service worker.

## Features

- **Live capture** — view APDUs as they are sniffed (≈1 s latency)
- **Session browser** — save, rename, and delete capture sessions
- **APDU decoding** — CLA/INS/P1/P2/P3, CAT commands (FETCH/ENVELOPE/
  TERMINAL RESPONSE), FCP templates, AUTH responses, TR results
- **PCAP export** — download any session as a Wireshark-compatible PCAP
- **Installable PWA** — works offline, installs via the browser

## Related

- **[simtrace2-pysniff](https://github.com/anttro/simtrace2-pysniff)** — the
  sniffer CLI (`simtrace2-pysniff`) and analysis server
  (`simtrace2-pysniff-server`) that this PWA talks to.
