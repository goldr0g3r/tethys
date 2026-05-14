# Regenerate .github/instructions/*.instructions.md from .cursor/rules/*.mdc.
# Source of truth: .cursor/rules/. Mirror: .github/instructions/.
#
# Run before opening a PR that touches rule files; CI rules-mirror-drift.yml verifies.
# Resolves PR-7 follow-up F1.

$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel
Set-Location $repoRoot

New-Item -ItemType Directory -Force -Path ".github\instructions" | Out-Null

$count = 0
foreach ($src in Get-ChildItem .cursor\rules\*.mdc) {
    $name = $src.BaseName
    python infrastructure\rules\_convert.py $src.FullName ".github\instructions\$name.instructions.md"
    $count++
}

Write-Host "Mirrored $count rules to .github/instructions/"
