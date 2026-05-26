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

echo
echo "== kb init pcie =="
"${KB_BIN}" init pcie

echo
echo "== kb ingest ../pcie-config.md =="
cd pcie
"${KB_BIN}" ingest ../pcie-config.md

echo
echo "== kb learn =="
learn_output=$("${KB_BIN}" learn --goal "Build PCIe configuration notes")
echo "${learn_output}"
run_id=$(printf '%s\n' "${learn_output}" | awk -F': ' '/Learn run:/ {print $2}')

echo
echo "== kb accept ${run_id} =="
"${KB_BIN}" accept "${run_id}"

echo
echo "== kb compile --fast =="
"${KB_BIN}" compile --fast

echo
echo "== kb health =="
"${KB_BIN}" health

echo
echo "== Accepted notes =="
find notes/concepts/generated -type f -maxdepth 1 -print | sort

echo
echo "Demo completed."
