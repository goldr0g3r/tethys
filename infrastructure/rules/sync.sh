#!/usr/bin/env bash
# Regenerate .github/instructions/*.instructions.md from .cursor/rules/*.mdc.
# Source of truth: .cursor/rules/. Mirror: .github/instructions/.
#
# Run before opening a PR that touches rule files; CI rules-mirror-drift.yml verifies.
# Resolves PR-7 follow-up F1.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

mkdir -p .github/instructions

count=0
for src in .cursor/rules/*.mdc; do
  [ -f "$src" ] || continue
  name=$(basename "$src" .mdc)
  python3 infrastructure/rules/_convert.py "$src" ".github/instructions/${name}.instructions.md"
  count=$((count + 1))
done

echo "Mirrored $count rules to .github/instructions/"
