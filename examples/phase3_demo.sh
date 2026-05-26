#!/usr/bin/env bash
set -euo pipefail

KB_BIN="${KB_BIN:-kb}"
DEMO_ROOT="${DEMO_ROOT:-$(mktemp -d)}"

echo "Demo root: ${DEMO_ROOT}"
cd "${DEMO_ROOT}"

cat > pcie-config.md <<'MARKDOWN'
# Configuration Space

BAR assignment is part of PCIe enumeration.

## BAR Assignment

Firmware or the OS sizes and assigns BARs.
MARKDOWN

cat > boot.log <<'LOG'
BAR0 not assigned
LOG

echo
echo "== kb init pcie =="
"${KB_BIN}" init pcie

echo
echo "== kb ingest ../pcie-config.md =="
cd pcie
"${KB_BIN}" ingest ../pcie-config.md

echo
echo "== kb learn + accept =="
learn_output=$("${KB_BIN}" learn --goal "Build PCIe configuration notes")
echo "${learn_output}"
learn_run_id=$(printf '%s\n' "${learn_output}" | awk -F': ' '/Learn run:/ {print $2}')
"${KB_BIN}" accept "${learn_run_id}"

echo
echo "== kb ask =="
ask_output=$("${KB_BIN}" ask --with ../boot.log "Why was BAR0 not assigned?")
echo "${ask_output}"
session_path=$(printf '%s\n' "${ask_output}" | awk -F': ' '/Session:/ {print $2}')

echo
echo "== kb learn --from-session ${session_path} =="
session_learn_output=$("${KB_BIN}" learn --from-session "${session_path}")
echo "${session_learn_output}"
session_run_id=$(printf '%s\n' "${session_learn_output}" | awk -F': ' '/Learn run:/ {print $2}')
"${KB_BIN}" accept "${session_run_id}"

echo
echo "== kb compile --fast =="
"${KB_BIN}" compile --fast

echo
echo "== kb health =="
"${KB_BIN}" health

echo
echo "== Sessions =="
find sessions -type f | sort

echo
echo "Demo completed."
