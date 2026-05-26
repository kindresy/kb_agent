#!/usr/bin/env bash
set -euo pipefail

# Demo for Phase 1 / 1.1 / 1.2 commands:
#   kb init
#   kb ingest
#   kb compile --fast
#   kb health
#
# Usage from the repository root:
#   bash examples/phase1_demo.sh
#
# Optional:
#   KB_BIN=/absolute/path/to/kb bash examples/phase1_demo.sh

KB_BIN="${KB_BIN:-kb}"
DEMO_ROOT="${DEMO_ROOT:-$(mktemp -d)}"

echo "Demo root: ${DEMO_ROOT}"
cd "${DEMO_ROOT}"

echo
echo "== Create input material =="
cat > pcie-mini-note.md <<'MARKDOWN'
# PCIe Mini Note

BAR sizing is part of PCIe enumeration.
MARKDOWN
mkdir -p pcie-book/pcie-book.assets
cat > pcie-book/pcie-book.md <<'MARKDOWN'
# PCIe Book Export

The LTSSM diagram is kept beside this Markdown export.

![LTSSM](pcie-book.assets/ltssm.png)
MARKDOWN
printf 'fake png bytes\n' > pcie-book/pcie-book.assets/ltssm.png
mkdir -p pcie-spec/"PCI Express Base-assets"/part_0001/images
cat > pcie-spec/"PCI Express Base.md" <<'MARKDOWN'
# PCI Express Base

This export uses the dash-assets layout common in converted specifications.

![Packet format](PCI Express Base-assets/part_0001/images/packet.jpg)
MARKDOWN
printf 'fake jpg bytes\n' > pcie-spec/"PCI Express Base-assets"/part_0001/images/packet.jpg
mkdir -p pcie-arch/parts/part_0001/images
cat > pcie-arch/pci_express_arch.md <<'MARKDOWN'
# PCI Express Architecture

This export links into a sibling parts directory.

![Topology](parts/part_0001/images/topology.jpg)
MARKDOWN
printf 'fake jpg bytes\n' > pcie-arch/parts/part_0001/images/topology.jpg
printf 'LTSSM: L0\n' > boot.log

echo
echo "== kb init pcie =="
"${KB_BIN}" init pcie

echo
echo "== kb ingest ../pcie-mini-note.md =="
cd pcie
"${KB_BIN}" ingest ../pcie-mini-note.md

echo
echo "== kb ingest ../boot.log =="
"${KB_BIN}" ingest ../boot.log

echo
echo "== kb ingest ../pcie-book/ =="
"${KB_BIN}" ingest ../pcie-book/

echo
echo "== kb ingest ../pcie-spec/ =="
"${KB_BIN}" ingest ../pcie-spec/

echo
echo "== kb ingest ../pcie-arch/ =="
"${KB_BIN}" ingest ../pcie-arch/

echo
echo "== kb ingest ../pcie-arch/ again skips duplicates =="
"${KB_BIN}" ingest ../pcie-arch/

echo
echo "== kb compile --fast =="
"${KB_BIN}" compile --fast

echo
echo "== kb health =="
"${KB_BIN}" health

echo
echo "== Source index =="
cat .kb/source_index.jsonl

echo
echo "Demo completed."
