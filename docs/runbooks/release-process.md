# Runbook - Release process

> Audience: project owner cutting a new versioned release of Tethys (both
> `tethys-master` Python package and `tethys-slave` C library).
> Goal: take `main` at a known-good commit, tag `v0.x.y`, watch `release.yml`
> build all artefacts, attach the CycloneDX SBOM, publish the GitHub Release,
> push to PyPI, push the Docker image. Wall-clock target: **45 minutes** for a
> full release; **<10 minutes** for a hot-fix patch release.
> Style: every step states the expected outcome; rollback procedure at the end.
>
> Implements parent plan §6.7 (`release.yml`) and §11 (public deliverables).
> Companion: [`docs/runbooks/supply-chain-and-sbom.md`](supply-chain-and-sbom.md)
> covers the SBOM regeneration cadence outside of releases.

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Pre-flight checklist](#2-pre-flight-checklist)
3. [Version bump](#3-version-bump)
4. [Generate the CHANGELOG entry](#4-generate-the-changelog-entry)
5. [Tag and push](#5-tag-and-push)
6. [Watch release.yml](#6-watch-releaseyml)
7. [Post-release verification](#7-post-release-verification)
8. [Publish announcements](#8-publish-announcements)
9. [Rollback and re-run](#9-rollback-and-re-run)
10. [Cross-references](#10-cross-references)

---

## 1. Prerequisites

| Tool | Minimum version | Why |
| --- | --- | --- |
| `gh` (GitHub CLI) | 2.50 | Tag pushes, release validation. |
| `git` | 2.40 | Signed tags. |
| `uv` | 0.4 | Python build for `tethys-master`. |
| `cmake` | 3.20 | Slave library build verification. |
| GPG **or** SSH signing key | any | All tags signed. |
| Docker | 24.x | Local SBOM smoke (release.yml does the real build). |

Verify:

```powershell
gh --version ; git --version ; uv --version ; cmake --version ; docker --version
```

```bash
gh --version && git --version && uv --version && cmake --version && docker --version
```

Expected: five version banners, no errors.

## 2. Pre-flight checklist

Before cutting any release, confirm:

- [ ] `main` is green - every required-status-check passes on the head SHA.
- [ ] No open `phase-acceptance` issue for the current phase (parent §6.6).
- [ ] No open `security` label issues (else hotfix first; see §9).
- [ ] `docs/misra-deviations.md` summary shows zero open mandatory deviations.
- [ ] `docs/traceability.csv` validated (`make trace-check` or
      `python scripts/trace_check.py` if present).
- [ ] Coverage on `slave/src/core/` >= 95% statement, >= 90% MC/DC (parent §6.7).
- [ ] Renovate / Dependabot PRs reviewed; no unresolved CVEs in
      `pip-audit` / `osv-scanner` output (see
      [`supply-chain-and-sbom.md`](supply-chain-and-sbom.md)).

Run the pre-flight script:

```powershell
gh api "repos/goldr0g3r/tethys/commits/main/status" `
  --jq '.statuses[] | select(.state != "success") | "\(.context): \(.state)"'
```

```bash
gh api "repos/goldr0g3r/tethys/commits/main/status" \
  --jq '.statuses[] | select(.state != "success") | "\(.context): \(.state)"'
```

Expected output: empty.

## 3. Version bump

Tethys uses **SemVer** with the rules below. Decide the new version BEFORE
touching files.

| Change kind | Rule | Example |
| --- | --- | --- |
| Breaking API / wire format | MAJOR bump | `0.4.7` -> `1.0.0` |
| New backward-compatible feature | MINOR bump | `0.4.7` -> `0.5.0` |
| Bug fix only | PATCH bump | `0.4.7` -> `0.4.8` |
| Pre-1.0 breaking change | MINOR bump (pre-1.0 grace) | `0.4.7` -> `0.5.0` |

### 3.1 Update master/pyproject.toml

```powershell
$NEW_VERSION = "0.4.8"
$pyproject = Get-Content master/pyproject.toml -Raw
$pyproject = $pyproject -replace 'version\s*=\s*"[^"]+"', "version = `"$NEW_VERSION`""
$pyproject | Set-Content master/pyproject.toml -NoNewline
```

```bash
NEW_VERSION=0.4.8
sed -i.bak -E 's/^version = "[^"]+"/version = "'"$NEW_VERSION"'"/' master/pyproject.toml
rm master/pyproject.toml.bak
```

### 3.2 Update slave/CMakeLists.txt

```powershell
$cmakelists = Get-Content slave/CMakeLists.txt -Raw
$cmakelists = $cmakelists -replace 'VERSION\s+\d+\.\d+\.\d+', "VERSION $NEW_VERSION"
$cmakelists | Set-Content slave/CMakeLists.txt -NoNewline
```

```bash
sed -i.bak -E 's/VERSION [0-9]+\.[0-9]+\.[0-9]+/VERSION '"$NEW_VERSION"'/' slave/CMakeLists.txt
rm slave/CMakeLists.txt.bak
```

### 3.3 Update simulator/pyproject.toml (matches master)

Same procedure as §3.1 against `simulator/pyproject.toml`.

### 3.4 Commit the bump

```powershell
git checkout -b release/v$NEW_VERSION
git add master/pyproject.toml slave/CMakeLists.txt simulator/pyproject.toml
git commit -m "release: v$NEW_VERSION"
```

```bash
git checkout -b release/v$NEW_VERSION
git add master/pyproject.toml slave/CMakeLists.txt simulator/pyproject.toml
git commit -m "release: v$NEW_VERSION"
```

Expected: single commit, three files modified, no other changes.

## 4. Generate the CHANGELOG entry

Tethys uses `semantic-release` to generate CHANGELOG entries from Conventional
Commit subjects on every merge to main (see `release.yml`). For a manual
release, dry-run first:

```powershell
npx --yes semantic-release --dry-run --branches=main --no-ci 2>&1 | Select-String -Pattern "next release version"
```

```bash
npx --yes semantic-release --dry-run --branches=main --no-ci 2>&1 | grep "next release version"
```

Expected output: `The next release version is X.Y.Z`. Confirm it matches
`$NEW_VERSION`. If not, an unconventional commit slipped in - audit `git log`
and fix the commit messages OR override the version with
`--release-as $NEW_VERSION`.

Commit the generated `CHANGELOG.md`:

```powershell
git add CHANGELOG.md
git commit --amend --no-edit
```

```bash
git add CHANGELOG.md && git commit --amend --no-edit
```

## 5. Tag and push

### 5.1 Open the release PR

```powershell
gh pr create --title "release: v$NEW_VERSION" --body "Release v$NEW_VERSION." --base main --head release/v$NEW_VERSION
```

```bash
gh pr create --title "release: v$NEW_VERSION" --body "Release v$NEW_VERSION." --base main --head release/v$NEW_VERSION
```

Wait for required status checks; merge as squash; delete the branch.

### 5.2 Pull main and tag

```powershell
git checkout main
git pull --rebase
git tag -s v$NEW_VERSION -m "Tethys v$NEW_VERSION"
git push origin v$NEW_VERSION
```

```bash
git checkout main
git pull --rebase
git tag -s v$NEW_VERSION -m "Tethys v$NEW_VERSION"
git push origin v$NEW_VERSION
```

Expected output: `[new tag]         v0.4.8 -> v0.4.8`. The tag must be signed
(`-s`) - the GitHub Release page shows a "Verified" badge.

### 5.3 Verify tag is signed

```powershell
git verify-tag v$NEW_VERSION
```

```bash
git verify-tag v$NEW_VERSION
```

Expected: GPG / SSH signature good.

## 6. Watch release.yml

`release.yml` triggers on `push: tags: ['v*']`. Watch live:

```powershell
gh run watch
```

```bash
gh run watch
```

Expected jobs (executed sequentially per release.yml):

1. `build-master-bundles` - PyInstaller bundles for win-amd64, linux-amd64,
   linux-arm64, macos-arm64 (~6 min each).
2. `build-slave-tarball` - cmake build matrix (posix-sim, arm-none-eabi-gcc
   for cortex-m4/m7/m33), tarball each.
3. `build-docker-image` - multi-arch Docker image `ghcr.io/goldr0g3r/tethys:vX.Y.Z`.
4. `generate-sbom` - `cyclonedx-cli` + `gh-python-generate-sbom`; SBOM
   uploaded as artefact.
5. `publish-pypi` - uploads master bundle to PyPI (`pypi-publish` action).
6. `publish-release` - creates the GitHub Release, attaches all artefacts,
   includes the CHANGELOG diff in the body.

Total target: **<20 minutes wall-clock** on GitHub Actions free tier.

If any job fails, see [§9 Rollback and re-run](#9-rollback-and-re-run).

## 7. Post-release verification

### 7.1 GitHub Release

Open <https://github.com/goldr0g3r/tethys/releases/tag/vX.Y.Z>.

- [ ] CHANGELOG diff visible.
- [ ] At least 9 artefacts attached:
  - `tethys-master-vX.Y.Z-win-amd64.zip`
  - `tethys-master-vX.Y.Z-linux-amd64.tar.gz`
  - `tethys-master-vX.Y.Z-linux-arm64.tar.gz`
  - `tethys-master-vX.Y.Z-macos-arm64.zip`
  - `tethys-slave-vX.Y.Z-posix-sim.tar.gz`
  - `tethys-slave-vX.Y.Z-arm-cortex-m4.tar.gz`
  - `tethys-slave-vX.Y.Z-arm-cortex-m7.tar.gz`
  - `tethys-slave-vX.Y.Z-arm-cortex-m33.tar.gz`
  - `tethys-sbom-vX.Y.Z.cyclonedx.json`
- [ ] All artefact signatures verify (`.sig` next to each).
- [ ] "Verified" tag badge present.

### 7.2 PyPI

```powershell
pip index versions tethys-master | Select-Object -First 3
```

```bash
pip index versions tethys-master | head -n 3
```

Expected output includes the new version.

### 7.3 Docker image

```powershell
docker pull ghcr.io/goldr0g3r/tethys:v$NEW_VERSION
docker run --rm ghcr.io/goldr0g3r/tethys:v$NEW_VERSION tethys-master --version
```

```bash
docker pull ghcr.io/goldr0g3r/tethys:v$NEW_VERSION
docker run --rm ghcr.io/goldr0g3r/tethys:v$NEW_VERSION tethys-master --version
```

Expected output: `tethys-master $NEW_VERSION`.

### 7.4 SBOM lint

```powershell
docker run --rm -i cyclonedx/cyclonedx-cli validate `
  --input-format json `
  --input-version v1_5 `
  --input-file - < tethys-sbom-v$NEW_VERSION.cyclonedx.json
```

```bash
docker run --rm -i cyclonedx/cyclonedx-cli validate \
  --input-format json \
  --input-version v1_5 \
  --input-file - < tethys-sbom-v$NEW_VERSION.cyclonedx.json
```

Expected: `BOM is valid`.

## 8. Publish announcements

- [ ] Update README badges (build, coverage, latest release).
- [ ] Update Sphinx docs site (`gh workflow run docs-deploy.yml` from PR-11).
- [ ] Post short summary on the project owner's site / LinkedIn / etc.
- [ ] Update `docs/case-study.pdf` if the release closes a Phase milestone
      (Phase 7 -> marine demo, Phase 8 -> space demo, Phase 11 -> v1.0).

## 9. Rollback and re-run

### 9.1 Workflow failure

```powershell
gh run rerun (gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId') --failed
```

```bash
gh run rerun "$(gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --failed
```

Re-runs only the failed jobs - cheap on credits.

### 9.2 Delete the tag (full restart)

If the release is unsalvageable (e.g. wrong version number, wrong main SHA):

```powershell
gh release delete v$NEW_VERSION --yes
git push origin :refs/tags/v$NEW_VERSION
git tag -d v$NEW_VERSION
```

```bash
gh release delete v$NEW_VERSION --yes
git push origin :refs/tags/v$NEW_VERSION
git tag -d v$NEW_VERSION
```

Then restart from §3.

### 9.3 PyPI upload failed (PyPI does not allow over-upload)

PyPI **never** allows re-uploading the same version. Bump PATCH and re-cut.

```powershell
$NEW_VERSION = "0.4.9"
# repeat from §3
```

### 9.4 Docker image corrupt

```powershell
gh workflow run release.yml --ref v$NEW_VERSION --jobs build-docker-image,publish-release
```

```bash
gh workflow run release.yml --ref v$NEW_VERSION --jobs build-docker-image,publish-release
```

Re-runs only the Docker build + publish.

## 10. Cross-references

- Parent plan section 6.1 (SemVer + tag-as-release).
- Parent plan section 6.7 (`release.yml`, `sbom.yml`).
- Parent plan section 11 (public deliverables).
- [ADR-0008 License-free toolchain](../adr/0008-license-free-toolchain.md) -
  CycloneDX choice.
- [Runbook: supply-chain-and-sbom.md](supply-chain-and-sbom.md) - SBOM
  maintenance outside of releases.
- [Runbook: incident-and-defect.md](incident-and-defect.md) - hot-fix release
  procedure.
- [Conventional Commits 1.0](https://www.conventionalcommits.org/en/v1.0.0/) -
  drives the CHANGELOG generation.
- [PyPI publishing best practices](https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/).
- [GitHub Container Registry docs](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
