Install the wheel below — the PWA is bundled inside it:

```
pip install ./simtrace_analyser-*.whl
simtrace-analyser-server --capture gsmtap
```

The UI is then served at http://127.0.0.1:8081/.  If your system Python is
externally managed (PEP 668 — common on Arch and Fedora), install into a
virtual environment first (`python3 -m venv .venv && . .venv/bin/activate`).

The source archive is the same tree a clone would have: unzip it and run
`./start.sh` (Linux/macOS) or `start.bat` (Windows).  Direct SIMtrace2 capture
on Linux additionally needs the attached `70-simtrace2-pysniff.rules` udev rule.

**Runtime zip (no installer)** — `simtrace-analyser-*.zip`
is the runtime tree only (packages, PWA, launchers, docs — no tests, no git):
extract it anywhere and run `start.bat` (Windows) or `./start.sh`
(Linux/macOS).  Python 3 has to be on `PATH`; `pip install pyusb` is only
needed for direct SIMtrace2 capture.

The project is MIT-licensed (see `LICENSE`).
