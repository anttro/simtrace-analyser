Install the wheel below — the PWA is bundled inside it:

```
pip install ./simtrace_analyser-*.whl
simtrace-analyser-server --capture gsmtap
```

The UI is then served at http://127.0.0.1:8081/.  If your system Python is
externally managed (PEP 668 — common on Arch and Fedora), install into a
virtual environment first (`python3 -m venv .venv && . .venv/bin/activate`).

**Highlights in 2.7.16**

- The Files view now follows a live capture: it refreshes while visible,
  supports row jumps and Show diff live, and keeps the final timeline on
  screen after the capture stops.
- EF file-descriptor decoding now follows TS 102 221 V18.4.0 Table 11.5
  (p. 91): cyclic EFs (`110`) decode their READ/UPDATE RECORD bodies,
  BER-TLV EFs (`0x39`/`0x79`) are recognised, and the fabricated
  `num_dfs_efs` field is gone.

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
