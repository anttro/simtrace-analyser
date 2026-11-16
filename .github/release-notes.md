Install the wheel below — the PWA is bundled inside it:

```
pip install ./simtrace_analyser-*.whl
simtrace-analyser-server --capture gsmtap
```

The UI is then served at http://127.0.0.1:8081/.  If your system Python is
externally managed (PEP 668 — common on Arch and Fedora), install into a
virtual environment first (`python3 -m venv .venv && . .venv/bin/activate`).

**Highlights in 2.7.20**

- Fixes the broken 2.7.19 PWA: a page-size comment lost its `//`, so the
  inline script failed to parse and no tab worked.  2.7.19 has been
  withdrawn.
- Saved sessions load **2,000 messages per page**, so common sessions
  (923 / 1,810 / 1,991 messages) open in one request instead of stopping at
  500; larger sessions page as before.
- Scrolling the APDU list near the bottom loads the next page
  automatically; the **Load more** button remains as an explicit fallback.

The source archive is the same tree a clone would have: unzip it and run
`./start.sh` (Linux/macOS) or `start.bat` (Windows).  Direct SIMtrace2 capture
on Linux additionally needs the attached `70-simtrace2-pysniff.rules` udev rule.

The `.sh` launchers are for Linux/macOS only: on Windows use `start.bat` /
`sniff-start.bat` from `cmd.exe` or PowerShell (WSL, Git Bash, MSYS2, MinGW and
Cygwin are refused).

**Runtime zip (no installer)** — `simtrace-analyser-*.zip`
is the runtime tree only (packages, PWA, launchers, docs — no tests, no git):
extract it anywhere and run `start.bat` (Windows) or `./start.sh`
(Linux/macOS).  Python 3 has to be on `PATH`; `pip install pyusb` is only
needed for direct SIMtrace2 capture.

The project is MIT-licensed (see `LICENSE`).
