# simtrace-analyser

PWA frontend for browsing SIMtrace2 APDU traces. Connects to
`simtrace2-pysniff-server` to view live captures and saved sessions.

## Setup

```sh
git clone https://github.com/anttro/simtrace-analyser.git
cd simtrace-analyser
python3 -m http.server 8000
```

Open `http://127.0.0.1:8000` in a browser.  The PWA connects to the
server at `http://127.0.0.1:8081` by default (configurable in Settings).

## Requirements

- **simtrace2-pysniff** (server component) running `simtrace2-pysniff-server`
- A modern browser with JavaScript enabled

No other dependencies — static HTML + service worker.
