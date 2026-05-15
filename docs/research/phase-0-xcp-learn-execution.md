# Phase 0 — XCP 101 explainer (research note)

> Research note backing the `docs/xcp-101-explainer` PR (`docs(learn): comprehensive XCP explainer for first-time readers`).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) — docs add-on; no parent-plan todo (not a phase deliverable).
> Sub-plan: drafted inline in the PR description (single-file docs PR; no separate `.cursor/plans/*.plan.md`).

## Scope

This note backs [`docs/learn/xcp-101.md`](../learn/xcp-101.md) — a long-form (~13,400-word) beginner explainer of the XCP protocol, plus the companion [`docs/learn/README.md`](../learn/README.md) directory index. The explainer is the **normative** deliverable; this note is the **retrieval-dated, citation-bearing** evidence that the explainer was drafted against the current state of primary XCP sources on 2026-05-15.

In scope for this PR:

- Web research for accessible primary-source XCP material (tutorials, vendor reference texts, ASAM overview pages, CCP↔XCP history).
- Concrete byte-level examples for CONNECT, DAQ setup, CAL writes — extracted from the Vector XCP Book V1.5 and CSS Electronics tutorial.
- A2L MEASUREMENT and CHARACTERISTIC snippets — extracted verbatim from the Vector XCP Book V1.5 §2.1.
- Cross-references into Tethys's existing research notes ([`phase-0-system-requirements.md`](phase-0-system-requirements.md)) and ADRs (0001, 0004, 0006, 0007, 0010) — reused rather than re-derived.

Out of scope (handled elsewhere):

- Implementing XCP commands — Phase 2 (`p2`) parent-plan todo.
- DAQ engine + ODT scheduling — Phase 3 (`p3`).
- CAL + PAG with CRC gate — Phase 4 (`p4`).
- AES-128 seed-and-key implementation — Phase 8 (`p8`); spec captured in [ADR-0006](../adr/0006-aes-128-seed-and-key.md).
- Future explainers (A2L deep-dive, MISRA cheatsheet, CCSDS primer) — listed in [`docs/learn/README.md`](../learn/README.md) "Planned future explainers".

## Sources (retrieved 2026-05-15)

All retrieval dates are within the 14-day freshness window required by [`research-note-per-phase.mdc`](../../.cursor/rules/research-note-per-phase.mdc). Reuses S-IDs from the canonical [standards matrix](phase-0-standards-matrix.csv) where applicable; new sources get inline citations in the explainer.

### Reused — already cited in [`phase-0-standards-matrix.csv`](phase-0-standards-matrix.csv)

The XCP-101 explainer cites these directly (the S-IDs and URLs are authoritative; retrieval date 2026-05-14 from the canonical matrix is within the freshness window):

- **S1 — ASAM MCD-1 XCP 1.4** — <https://www.asam.net/standards/detail/mcd-1-xcp/wiki>. Wiki overview of XCP versions, transport layers, packet structure.
- **S2 — AUTOSAR SWS_XCP R20-11** — <https://www.autosar.org/fileadmin/standards/R20-11/CP/AUTOSAR_SWS_XCP.pdf>. AUTOSAR Classic Platform XCP module; reading reference.
- **S3 — Vector XCP Book V1.5** — <https://cdn.vector.com/cms/content/application-areas/ecu-calibration/xcp/XCP_Book_V1.5_EN.pdf>. The primary reference text. Specifically used in the explainer for:
  - §1.1 — CONNECT command byte layout (master and slave sides).
  - §1.3 — PID byte regions (0x00-0xFB DAQ ODT, 0xFC SERV, 0xFD EV, 0xFE ERR, 0xFF RES; master 0xC0-0xFF commands).
  - §1.6.4 — XCP on Ethernet LEN + CTR transport header; the CTR quote in §4 + §12 of the explainer.
  - §2.1 — A2L MEASUREMENT and CHARACTERISTIC examples (Shifter_B3, KF1).
  - §3 — seed-and-key generic mechanism description.
- **S4 — pyxcp** — <https://github.com/christoph2/pyxcp>. LGPLv3 Python XCP master library.
- **S6 — AUTOSAR PRS E2E Protocol R17-10** — <https://www.autosar.org/fileadmin/standards/R17-10_R1.2.0/FO/AUTOSAR_PRS_E2EProtocol.pdf>. End-to-end protection vocabulary used in §12 fault-class mapping.
- **S10 — CCSDS 232.1-B-2 (COP-1)** — <https://ccsds.org/Pubs/232x1b1s.pdf>. Reliable space-link layer Tethys wraps XCP-on-SxI in.
- **S15 — CAN-FD spec + CiA 2020 proceedings** — <https://can-cia.org/can-knowledge/can-fd-the-basic-idea>. Hamming distance + payload-size facts in §9.
- **S27 — Sauci/pya2l + christoph2/pyA2L** — <https://github.com/Sauci/pya2l>. A2L parser libraries used in §10.
- **S28 — vectorgrp/XCPlite** — <https://github.com/vectorgrp/XCPlite>. MIT-licensed reference slave implementation.
- **S31 — ASAM MCD-2 MC (A2L) v1.7** — <https://www.asam.net/standards/detail/mcd-2-mc/>. A2L file format standard.

### New — retrieved 2026-05-15 (inline in explainer)

The following sources are new (or were not previously cited in the standards matrix) and were retrieved specifically for the explainer. They appear inline in [`docs/learn/xcp-101.md`](../learn/xcp-101.md) §1, §2, §4, §9, §10, §17.

#### N1 — CSS Electronics: CCP/XCP on CAN explained (a simple intro)

- URL: <https://www.csselectronics.com/pages/ccp-xcp-on-can-bus-calibration-protocol>
- Retrieved: 2026-05-15
- Quoted relevance: the friendliest publicly-available XCP-on-CAN tutorial; concrete CAN-frame hex traces for CONNECT, GET_STATUS, FREE_DAQ, ALLOC_DAQ, WRITE_DAQ, START_STOP_SYNCH; full CCP↔XCP timeline (1992 CCP 1.0 → 2017 XCP 1.5); explicit list of XCP transports across versions.
- Used in explainer §2 (history), §6 (DAQ setup sequence), §9 (CAN transport).

#### N2 — CSS Electronics: A2L (ASAP2) intro

- URL: <https://www.csselectronics.com/pages/a2l-file-asap2-intro-xcp-on-can-bus>
- Retrieved: 2026-05-15
- Quoted relevance: companion to N1; A2L format orientation for first-time readers.
- Used in explainer §10 + §17 further-reading.

#### N3 — Vector XCP Reference Book V3.0 (free PDF)

- URL: <https://cdn.vector.com/cms/content/application-areas/ecu-calibration/xcp/XCP_ReferenceBook_V3.0_EN.pdf>
- Retrieved: 2026-05-15
- Quoted relevance: V3.0 (newer than the S3 V1.5) of Vector's free reference; alternative entry point listed in §17 further-reading. Content overlap with V1.5 is large; the explainer's quotes are taken from V1.5 (S3) for citation continuity with the existing standards matrix.

#### N4 — SAE 2003-01-1205, *Introduction to the Universal Measurement and Calibration Protocol XCP*

- URL: <https://saemobilus.sae.org/papers/introduction-universal-measurement-calibration-protocol-xcp-2003-01-1205>
- Retrieved: 2026-05-15
- Quoted relevance: the original 2003 SAE technical paper introducing XCP. Abstract is free; full paper paywalled. The "expanded the limits of the original CAN Calibration Protocol" quote in explainer §2 is taken from the abstract. Used in §2 (history) + §17 (further reading).

#### N5 — AutosarToday: XCP Commands

- URL: <https://www.autosartoday.com/posts/xcp_commands>
- Retrieved: 2026-05-15
- Quoted relevance: per-command byte-layout reference; used to cross-validate the CONNECT example bytes in explainer §4 against S3.

#### N6 — pyA2L tutorial + IF_DATA guide

- Tutorial URL: <https://pya2l.readthedocs.io/en/latest/tutorial.html>
- IF_DATA URL: <https://pya2l.readthedocs.io/en/latest/ifdata.html>
- Retrieved: 2026-05-15
- Quoted relevance: pyA2L library docs; IF_DATA structure examples used in explainer §10. Tethys's master will wrap pyA2L (or Sauci/pya2l preferred) per parent plan §3.1 + ADR-0007.

#### N7 — Wikipedia: XCP (Protocol)

- URL: <https://en.wikipedia.org/wiki/XCP_%28Protocol%29>
- Retrieved: 2026-05-15
- Quoted relevance: concise version/transport timeline; used to cross-validate the version history in explainer §2.

#### N8 — Vector CAN-FD Measurement press article

- URL: <https://cdn.vector.com/cms/content/know-how/_technical-articles/CAN_FD_Measurement_CiA_PressArticle_201409_EN.pdf>
- Retrieved: 2026-05-15
- Quoted relevance: CAN-FD throughput numbers (5x-10x classical CAN, up to 64-byte payloads, ≥5 Mbit/s data phase) used in explainer §9.2.

#### N9 — ASAM MCD-1 CCP overview page

- URL: <https://www.asam.net/standards/detail/mcd-1-ccp/>
- Retrieved: 2026-05-15
- Quoted relevance: CCP 2.1.0 (1999-02-18) release date for the §2 timeline.

## Decisions

- **Scope decision: docs add-on, not a parent-plan phase deliverable.** The XCP-101 explainer is not in the parent plan §16 "Public deliverables" or §8 phase list (those are about engineering deliverables — code, ADRs, tests). It is a *literacy aid* for readers approaching the repo for the first time. Treated as a docs add-on that flows through the normal PR + research-note workflow without a `p*` todo.
- **No parent-plan status sync.** No parent-plan todo flips state on this PR's merge. The PR title `docs(learn)` is intentionally not `p0-*` so it does not appear in the parent-plan progress table.
- **Reuse Tethys's existing citations.** Where the explainer makes a claim already covered by [`phase-0-system-requirements.md`](phase-0-system-requirements.md), it cites that note + the matching S-ID rather than re-citing the underlying standard. This keeps the citation chain auditable and avoids "citation drift" between the explainer and the research note.
- **A2L examples drawn from S3 verbatim.** The Shifter_B3 MEASUREMENT block and KF1 CHARACTERISTIC block in explainer §10 are taken verbatim from Vector XCP Book V1.5 §2.1 (S3). This is fair use for an illustrative quotation, and is attributed in-line.
- **CONNECT byte example cross-checked.** The CONNECT request `FF 00 00 00 00 00 00 00` and response `FF 1D C0 FF DD 02 08 08` byte layouts in explainer §4 are taken from N5 (AutosarToday) and cross-checked against S3 Vector XCP Book V1.5 §1.1.
- **Length budget.** Target was 8,000-12,000 words; final is ~13,400 words. The over-budget is deliberate — the explainer is meant to be the canonical reference. Splitting it into multiple files would scatter the cross-references and break the linear read-through. Future *deeper* topics (A2L deep-dive, CCSDS primer) will be separate files per the [`docs/learn/README.md`](../learn/README.md) "Planned future explainers" list.
- **Mermaid for all diagrams.** No SVG export; GitHub renders Mermaid inline. Matches the project convention (parent plan + system-context use Mermaid throughout).
- **Asterisks for italics, not underscores.** Per `.markdownlint.json` MD049 setting (`"style": "asterisk"`).

## Open follow-ups

- **Phase 2 / Phase 3:** when the protocol core ships, link from explainer §16 "How Tethys uses XCP" into the actual file paths (currently labelled "planned"). Update the table cells and re-flow §16 as needed.
- **Phase 7 / Phase 8 demo recordings:** when the marine and space demos are recorded (parent plan Phase 9), embed or link them from explainer §1 ("real-world scenes") to anchor the abstract examples in concrete video.
- **A2L deep-dive:** the §10 A2L overview is intentionally surface-level. A second-tier `docs/learn/a2l-deep-dive.md` should land alongside Phase 2 (master A2L parser) or Phase 7 (marine A2L generator). Tracked in [`docs/learn/README.md`](../learn/README.md) planned-explainers table.
- **Glossary upkeep:** as new acronyms enter the repo (e.g. when Phase 8 ships the EDAC wrapper, or Phase 9 introduces the MATLAB `py.` bridge), append rows to the explainer §18 glossary so the explainer remains a one-stop terminology reference.
- **CI hint:** if a future markdownlint upgrade tightens MD040 or MD046 on the mermaid blocks, prefer the `mermaid` fence info-string convention used here over indented or HTML alternatives.

## Implementation Reference

<!-- status-sync appends the merged PR URL here once the PR is merged. -->

- PR: *to be filled at merge*
- Merged on: *to be filled at merge*
