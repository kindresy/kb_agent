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
echo "== kb learn + accept =="
learn_output=$("${KB_BIN}" learn --goal "Build PCIe configuration notes")
echo "${learn_output}"
learn_run_id=$(printf '%s\n' "${learn_output}" | awk -F': ' '/Learn run:/ {print $2}')
"${KB_BIN}" accept "${learn_run_id}"

echo
echo "== kb graph export =="
"${KB_BIN}" graph export

echo
echo "== second kb learn =="
conflict_output=$("${KB_BIN}" learn --goal "Create conflicting PCIe configuration notes")
echo "${conflict_output}"
conflict_run_id=$(printf '%s\n' "${conflict_output}" | awk -F': ' '/Learn run:/ {print $2}')

echo
echo "== modify ${conflict_run_id} candidate claim to conflict =="
python - "${conflict_run_id}" <<'PY'
import json
import sys
from pathlib import Path

run_id = sys.argv[1]
accepted_path = Path(".kb/claims/claims.jsonl")
candidate_path = Path(".kb/learn_runs") / run_id / "claims.jsonl"

accepted_claim = json.loads(accepted_path.read_text(encoding="utf-8").splitlines()[0])
candidate_claim = json.loads(candidate_path.read_text(encoding="utf-8").splitlines()[0])

candidate_claim["topic_id"] = accepted_claim["topic_id"]
candidate_claim["claim"] = accepted_claim["claim"].replace(
    "The source introduces", "The source not introduces", 1
)

candidate_path.write_text(
    json.dumps(candidate_claim, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(candidate_claim["claim"])
PY

echo
echo "== kb accept ${conflict_run_id} should fail =="
set +e
accept_output=$("${KB_BIN}" accept "${conflict_run_id}" 2>&1)
accept_status=$?
set -e
echo "${accept_output}"

if [ "${accept_status}" -eq 0 ]; then
  echo "Expected conflict rejection, but accept succeeded." >&2
  exit 1
fi

if ! printf '%s\n' "${accept_output}" | grep -q "reviews/conflicts/${conflict_run_id}/conflict_report.md"; then
  echo "Expected conflict report path was not printed." >&2
  exit 1
fi

echo
echo "== Conflict artifacts =="
find "reviews/conflicts/${conflict_run_id}" -type f | sort

echo
echo "== Conflict report =="
sed -n '1,120p' "reviews/conflicts/${conflict_run_id}/conflict_report.md"

echo
echo "== Conflict JSONL =="
sed -n '1,20p' "reviews/conflicts/${conflict_run_id}/conflicts.jsonl"

echo
echo "== kb compile --fast =="
"${KB_BIN}" compile --fast

echo
echo "== kb health =="
"${KB_BIN}" health

echo
echo "Demo completed with expected conflict rejection."
