#!/bin/bash
# simtrace-analyser-server startup script
#
# Usage: ./start.sh [--capture gsmtap|direct|disabled] [--port PORT] [--db PATH] [--gsmtap-port PORT]
#
# Options set via environment variables act as defaults; CLI flags override them.

set -euo pipefail
shopt -s nullglob

# Windows guard: start.sh is the native Linux/macOS launcher.  Under WSL the
# Linux guest cannot reach the Windows SIMtrace2 USB device, and a Git Bash /
# MSYS2 / MinGW / Cygwin shell has no Linux /sys + /dev/bus/usb view for the
# udev pre-flight below.  Use start.bat from cmd.exe or PowerShell, which drives
# the Windows Python/PyUSB stack.  A deliberate WSL/Cygwin flow can run
# `python -m simtrace_analyser` directly.
if grep -qi microsoft /proc/version 2>/dev/null || \
   uname -s 2>/dev/null | grep -qiE 'MINGW|MSYS|CYGWIN'; then
    echo "Error: start.sh is the Linux/macOS helper and cannot run on Windows" >&2
    echo "(WSL / MSYS2 / MinGW / Cygwin detected)." >&2
    echo "Use start.bat from a Windows command prompt (cmd.exe / PowerShell) instead." >&2
    exit 2
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

CAPTURE="${CAPTURE:-gsmtap}"
PORT="${PORT:-8081}"
DB="${DB:-}"
GSMTAP_PORT="${GSMTAP_PORT:-4729}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --capture)       CAPTURE="$2"; shift 2 ;;
        --port)          PORT="$2"; shift 2 ;;
        --db)            DB="$2"; shift 2 ;;
        --gsmtap-port)   GSMTAP_PORT="$2"; shift 2 ;;
        *)               EXTRA_ARGS+=("$1"); shift ;;
    esac
done

if [[ "$CAPTURE" == "direct" ]]; then
    bad_perms=0

    for devdir in /sys/bus/usb/devices/*/; do
        [[ -f "${devdir}busnum" ]] || continue
        [[ -f "${devdir}devnum" ]] || continue
        [[ -f "${devdir}uevent" ]] || continue

        vid=$(grep -oP 'PRODUCT=\K[a-f0-9]+' "${devdir}uevent" 2>/dev/null || true)
        [[ "$vid" == "1d50" ]] || continue

        busnum=$(<"${devdir}busnum")
        devnum=$(<"${devdir}devnum")
        node=$(printf '/dev/bus/usb/%03d/%03d' "$busnum" "$devnum")

        if [[ ! -e "$node" ]]; then
            continue
        fi

        if [[ -w "$node" ]]; then
            break
        fi

        bad_perms=1
        echo "Permission denied on $node" >&2
    done

    if [[ $bad_perms -eq 1 ]]; then
        echo "" >&2
        echo "Install the udev rule (then reconnect the device):" >&2
        echo "──────────────────────────────────────────────────" >&2
        echo "  sudo cp '$PROJECT_DIR/70-simtrace2-pysniff.rules' /etc/udev/rules.d/" >&2
        echo "  sudo udevadm control --reload-rules" >&2
        echo "  sudo udevadm trigger" >&2
        echo "──────────────────────────────────────────────────" >&2
        exit 3
    fi
fi

ARGS=()
ARGS+=(--capture "$CAPTURE")
ARGS+=(--port "$PORT")
[[ -n "$DB" ]] && ARGS+=(--db "$DB")
[[ "$CAPTURE" == "gsmtap" ]] && ARGS+=(--gsmtap-port "$GSMTAP_PORT")
ARGS+=("${EXTRA_ARGS[@]}")

echo "Starting simtrace-analyser-server..." >&2
echo "PWA (simtrace-analyser) will be served at http://127.0.0.1:$PORT/" >&2
exec env PYTHONPATH="$PROJECT_DIR" python3 -m simtrace_analyser "${ARGS[@]}"
