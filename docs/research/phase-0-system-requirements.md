# Phase 0 — System requirements, standards landscape, and packet-loss tolerance budget

> Research note backing PR-0c `docs(research): system requirements + packet-loss tolerance budget`.
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) — provisional todo `p0-system-requirements-research`.
> Sub-plan: [`.cursor/plans/p0c_system_requirements_research_07de5485.plan.md`](../../.cursor/plans/p0c_system_requirements_research_07de5485.plan.md).
>
> Companion artefacts: [`phase-0-standards-matrix.csv`](phase-0-standards-matrix.csv) (canonical) + [`phase-0-standards-matrix.md`](phase-0-standards-matrix.md) (generated view).
> ADR drafts (PR-3 will formalise): [`adr-0001`](../adr/drafts/adr-0001-xcp-as-development-protocol.md), [`adr-0004`](../adr/drafts/adr-0004-transport-abstraction-layer.md), [`adr-0005`](../adr/drafts/adr-0005-no-dynamic-allocation.md), [`adr-0010`](../adr/drafts/adr-0010-packet-loss-tolerance-budget.md).

## Table of contents

1. [Executive summary](#1-executive-summary)
2. [Scope and definitions](#2-scope-and-definitions)
3. [Standards landscape](#3-standards-landscape)
4. [XCP protocol behaviour under loss](#4-xcp-protocol-behaviour-under-loss)
5. [Per-transport SLA](#5-per-transport-sla)
6. [Profile loss budgets — the canonical table](#6-profile-loss-budgets--the-canonical-table)
7. [DAQ recovery semantics](#7-daq-recovery-semantics)
8. [CAL and PAG integrity](#8-cal-and-pag-integrity)
9. [STIM safety](#9-stim-safety)
10. [Fault-injection test catalogue](#10-fault-injection-test-catalogue)
11. [ADR draft inputs](#11-adr-draft-inputs)
12. [References](#12-references)
13. [Implementation Reference](#13-implementation-reference)

---

## 1. Executive summary

Tethys is an XCP master + slave designed to operate under two profiles — **marine** and **space** — across an explicitly bounded set of transports. XCP is, per [ADR-0001 draft](../adr/drafts/adr-0001-xcp-as-development-protocol.md), a **development-time** protocol; operational telemetry buses (NMEA 2000, CCSDS, MIL-STD-1553B) sit beside it, not under it. This research note answers two questions the parent plan parks as TBD:

1. **How much packet loss can a Tethys deployment tolerate?** — answered concretely in §6 (the canonical budget table); rationale anchored in ISO 26262 (S9) + IEC 61508 (S7) + IEC 61784-3 (S8) — "residual error rate ≤ 1% of PFH" — applied per transport per direction per XCP service.
2. **What architectural commitments flow from those budgets?** — answered in §11, which seeds four ADR drafts ([ADR-0001](../adr/drafts/adr-0001-xcp-as-development-protocol.md), [ADR-0004](../adr/drafts/adr-0004-transport-abstraction-layer.md), [ADR-0005](../adr/drafts/adr-0005-no-dynamic-allocation.md), [ADR-0010](../adr/drafts/adr-0010-packet-loss-tolerance-budget.md)) that PR-3 elevates to accepted status.

The **one-table summary** is in §6; every cell is a row in [ADR-0010 draft](../adr/drafts/adr-0010-packet-loss-tolerance-budget.md). Numbers are **proposed**, subject to revision once Phase 3 (DAQ) and Phase 5 (transports) produce measured data on the actual hardware.

### Headline conclusions

- **XCP-native loss detection exists but is detection-only.** XCP-on-Ethernet carries a 16-bit CTR (counter) field in the transport header that the master uses to detect dropped packets (S3 — Vector XCP Book V1.5). XCP itself never retransmits DAQ packets; the master decides the recovery policy (log + interpolate / log + halt) per ODT.
- **CTO commands are always ACKed; DAQ never is.** CTO (Command Transfer Object) round-trip ACK/RES gives ≥99.9% reliable command delivery with master-side timeout + retry (cap 3). DTO (Data Transfer Object) is fire-and-forget — that is why the loss budget for DAQ is loose and the loss budget for CTO is tight.
- **The space profile must wrap XCP-on-SxI inside CCSDS COP-1 / FARM-1 (S10).** Raw UART/SxI BER is 1e-5..1e-7; CCSDS COP-1 AD-service brings residual to mission target (~1e-12 per frame) via N(S)/N(R) automatic retransmission within a Virtual Channel.
- **The marine profile sits comfortably above CAN-FD's intrinsic residual error rate (~4.7e-11 per frame per CiA, S15) and inside Ethernet/UDP's "observed loss ≤ 1e-4" envelope on a typical shipboard LAN per IEC 61162-450 (S13).**
- **ISO 26262 is included as first-class context** even though Tethys is not an automotive product, because (a) XCP is an automotive protocol by origin (ASAM, S1) and (b) ISO 26262 ASIL D's PFH target ≤ 1e-8/h (S9) is the single tightest residual-error envelope in the industry, and so anchors the upper end of every per-profile budget.

The loss budget table in §6 is the single most actionable output of this document.

---

## 2. Scope and definitions

### 2.1 Scope of this note

- Defines the per-profile-per-transport-per-direction packet-loss tolerance budget for Tethys.
- Documents XCP-native fault-tolerance mechanisms (CTR, ACK/RES, SYNCH, A2L hash, EDAC wrapper).
- Maps each cited standard's fault-class language onto Tethys's mechanism set.
- Catalogues fault-injection scenarios that Phase 8 + Phase 10 must implement and Phase 5's transport conformance suite must exercise.
- Seeds four ADR drafts.

### 2.2 Out of scope

- Hardware reliability budgets (FIT rates of STM32F4/F7/H7 packages — picked up by the marine and space profile phases).
- Cryptographic proof of the AES-128 seed-and-key scheme — separate Phase-8 security research note.
- Mechanical / environmental qualification (IEC 60945 salt-spray, vibration, thermal-vacuum) — referenced for completeness only; out-of-scope for this note.
- Tool qualification (DO-330) — handled by an ADR forward-noted in §11.

### 2.3 Error vocabulary

These terms are used precisely throughout the note (per IEC 61508-4, S7; AUTOSAR PRS E2E §4.3.3, S6):

| Term | Definition | Detection layer in Tethys |
| --- | --- | --- |
| Bit error | A single bit flipped on the wire. | Transport CRC (CAN-FD, Ethernet, COP-1). |
| Frame error | The transport layer (CAN, Ethernet, UART) rejected the frame because of CRC mismatch, bad framing, or length mismatch. | Transport stack — surfaces as a missing CTR step at the XCP layer. |
| Packet loss | An XCP packet (CTO or DTO) was sent but never arrived. | XCP CTR for DTO; CTO timeout for CTO. |
| Packet reorder | An XCP packet arrived out-of-order. Possible on UDP / SocketCAN. | XCP CTR (gap-then-fill-in detection). |
| Packet duplication | An XCP packet arrived twice. | XCP CTR (duplicate detection). |
| Latency violation | The packet arrived but missed its event-channel deadline. | Master-side timestamp delta against A2L event period. |
| Masquerade | A packet was injected by an unauthenticated party. | AES-128 seed-and-key (space) / network-level (marine). |
| Corruption | The payload bits are wrong but the transport CRC accepted them (residual). | A2L-typed limit check; CAL CRC; EDAC. |
| Bus-off | The CAN controller transmit-error-counter exceeded 256 and the node stopped transmitting. | Transport-layer event surfaced to master. |
| Blackout | A continuous burst of frame loss (no DAQ for >N ms). | Master `DAQ_GAP` event with measured duration. |

### 2.4 Profile semantics

Per parent plan §3.3, Tethys ships two compile-time profiles. The packet-loss budgets in §6 are defined per profile, per transport, per direction, per XCP service (CTO vs DAQ vs STIM vs CAL):

- **Marine profile** — assumes a shipboard environment per IEC 60945 + IACS UR E22 Rev.3 + IACS UR E26/E27 cyber (S11, S12). Transports: CAN-FD + Ethernet (UDP via IEC 61162-450). DAQ is full-rate (1 kHz); CAL is online; STIM permitted under a whitelist. Cyber posture: layered with TLS-or-equivalent above XCP; AES-128 seed-and-key optional.
- **Space profile** — assumes a flight environment per ECSS-E-ST-40C Rev.1 + NPR 7150.2D + DO-178C DAL-B (S18, S20, S22). Transports: UART/SxI (wrapped in CCSDS COP-1, S10) + CAN (1-wire fault-tolerant). DAQ is **disabled by default**, enabled by an authenticated AES-128 service-mode unlock (parent §3.3, table row "Permitted commands in flight mode"). STIM is service-mode-only.

The XCP-as-dev-protocol stance (ADR-0001) means that during normal flight there should be **zero XCP traffic on the bus**. The budgets in §6 govern (a) the development bench (always-on Tethys), (b) the integration HIL bench (always-on), and (c) the in-flight service-mode window (which the budgets call "service mode loss budget").

### 2.5 Implications for Tethys

- Every transport in `tethys_transport/` must expose the error vocabulary above as a structured event so the master can log gaps and budgets are auditable. This drives ADR-0004 (transport interface contract).
- The two profiles compile from the same source — the compile-time `tethys_profile.h` flags switch which budget row applies, not which code runs.
- Tethys never gates flight-critical paths on its own data. Any safety-critical loop runs on the operational bus (CCSDS / NMEA 2000), not XCP.

---

## 3. Standards landscape

This section gives the rapid orientation; the **canonical** matrix lives in [`phase-0-standards-matrix.csv`](phase-0-standards-matrix.csv) (and its generated markdown view) with per-standard applicability flags per profile.

### 3.1 Protocol layer (XCP itself + nearest cousins)

| Std | Title | Applicability | Section pointer |
| --- | --- | --- | --- |
| ASAM MCD-1 XCP 1.4 | XCP Protocol Layer + Transport Layer Specifications | Both profiles | Whole document — Tethys implements the public spec. (S1) |
| ASAM MCD-2 MC (A2L) | A2L (description file) | Both profiles | Whole document — Tethys parses A2L via pya2l (parent §3.1). |
| AUTOSAR SWS_XCP R22-11 | AUTOSAR Classic XCP module | Reference only | Used as a reading reference for the slave clean-room implementation. (S2) |
| AUTOSAR PRS E2E Protocol | End-to-end protection profiles 1-22 | Both (referenced) | §5 — profile mapping in §4.5 below. (S6) |

### 3.2 Generic functional safety (anchors the residual-error envelope)

| Std | Title | Applicability | Section pointer |
| --- | --- | --- | --- |
| IEC 61508 | Functional safety of E/E/PE safety-related systems, parts 1-7 | Both profiles | Parts 2 (HW) + 3 (SW); SIL 2 PFH 1e-7..1e-6, SIL 3 1e-8..1e-7. (S7) |
| IEC 61784-3 | Industrial communication networks — Functional safety fieldbuses — General | Both profiles | Safe-communication residual-error budget; 1% of PFH rule. (S8) |
| IEC 62443 | Industrial cybersecurity | Section-only cite | Deferred to a Phase-8 security research note (sub-plan Q3). |

### 3.3 Automotive (added at user request — first-class)

| Std | Title | Applicability | Section pointer |
| --- | --- | --- | --- |
| ISO 26262:2018 part 5 | Hardware safety | Reference | Random failure PFH; FIT-rate methodology. (S9) |
| ISO 26262:2018 part 6 | Software safety | Reference | Software-architectural patterns; freedom from interference. (S9) |
| ISO 26262:2018 part 9 | ASIL-oriented analyses | Reference | Decomposition; ASIL D PFH ≤ 1e-8/h, ASIL B ≤ 1e-7/h. (S9) |

ISO 26262 is **referenced**, not **claimed**. Tethys is not an automotive product. But ISO 26262's PFH/ASIL apparatus is the single most mature application of IEC 61508 in the industry, and so anchors the upper end of the budget envelope (§6).

### 3.4 Space (production-environment reference for the space profile)

| Std | Title | Applicability | Section pointer |
| --- | --- | --- | --- |
| CCSDS 132.0-B-3 | TM Space Data Link Protocol | Space profile (reference) | Telemetry frame structure, no automatic retransmission. (S14) |
| CCSDS 232.0-B-4 | TC Space Data Link Protocol | Space profile (reference) | Telecommand frame structure; carries Type-AD frames for AD service. (S10) |
| CCSDS 232.1-B-2 | Communications Operation Procedure-1 (COP-1) | **Space profile — used** | AD service automatic retransmission via FOP-1/FARM-1; Sequence-Controlled Service. (S10) |
| CCSDS 130.0-G-3 | Space Data Link Protocols Summary | Space profile | Orientation. (S14) |
| ECSS-E-ST-50C | Communications | Space profile | ESA umbrella for space data links. (S16) |
| ECSS-E-ST-50-04C | Telecommand protocols, synchronization, channel coding | Space profile | CCSDS-aligned via adoption notices. |
| ECSS-E-ST-50-03C | Telemetry transfer frame protocol | Space profile | CCSDS-aligned. |
| ECSS-E-ST-50-12C | SpaceWire | Space profile (reference) | Future-work transport. |
| ECSS-E-AS-50-25C Rev.1 | (Adopted from CCSDS) | Space profile | Adoption notice. (S17) |
| ECSS-E-ST-40C Rev.1 | Software engineering | Space profile | Process layer (April 2025). (S18) |
| ECSS-Q-ST-80C | Software product assurance | Space profile | Process layer. |
| ECSS-Q-ST-60-02C | ASIC/FPGA | Future hardware | Reference. |
| NPR 7150.2D | NASA software engineering requirements | Space profile | NASA process anchor. (S20) |
| NASA-STD-8739.8 | NASA software assurance | Space profile | Assurance anchor. |
| NASA-HDBK-2203 | NASA software engineering handbook | Space profile | Engineering handbook. |

### 3.5 Avionics (DAL-B target per parent §4)

| Std | Title | Applicability | Section pointer |
| --- | --- | --- | --- |
| DO-178C | Software considerations in airborne systems | Both (informational) | DAL-B objective coverage tracked in `docs/traceability.csv`. (S22) |
| DO-330 | Software tool qualification considerations | Future (tool qual) | Future ADR. |
| DO-326A / ED-202A | Airworthiness Security Process Specification | Section-only cite | Deferred to a Phase-8 security research note. |

### 3.6 Marine

| Std | Title | Applicability | Section pointer |
| --- | --- | --- | --- |
| IACS UR E22 Rev.3 | Computer-based systems on ships | **Marine profile — used** | In force 1 Jul 2024; Sep 2025 corrigendum. (S11, S12) |
| IACS UR E26 Rev.1 | Cyber resilience of ships | Marine profile | Cyber-related normative reference. |
| IACS UR E27 | Cyber resilience of on-board systems and equipment | Marine profile | Cyber-related normative reference. |
| IEC 60945 | Maritime navigation equipment — general environmental | Marine profile (env only) | Out-of-scope here. |
| IEC 61162-450 | Maritime UDP Ethernet | **Marine profile — used** | UDP shipboard LAN; informs marine/UDP/DAQ row. (S13) |
| IEC 61162-1 | NMEA 0183 | Reference | Operational bus. |
| NMEA 2000 (=SAE J1939) | Marine CAN bus | Reference | Operational bus. |
| DNV-CG-0264 | Software systems class guidance | Reference | Alternative class-society anchor. |
| LR ShipRight Software | Lloyd's Register procedure | Reference | Alternative class-society anchor. |
| ISO 24060:2021 | Ship software logging system | Marine profile | Referenced by UR E22 (S12). |
| IMO MSC.428(98) | Maritime cyber risk in SMS | Reference | Cyber posture. |

### 3.7 CAN family

| Std | Title | Applicability | Section pointer |
| --- | --- | --- | --- |
| ISO 11898-1:2024 | CAN data link layer + physical signalling | Both profiles | Underlying transport. |
| CAN-FD | Bosch CAN-FD spec (now part of ISO 11898-1) | Marine + space (reference) | Wire format (S15). |

### 3.8 Implications for Tethys

- The standards matrix in [`phase-0-standards-matrix.csv`](phase-0-standards-matrix.csv) is the single source of truth — this section is a navigation aid.
- "Reference" means we read it and align where reasonable; "used" means a normative requirement traces back to it in `docs/traceability.csv`.
- The cyber standards (IEC 62443, DO-326A, IACS UR E26/E27) get **section-level** treatment in PR-0c per sub-plan Q3 — deeper mapping lives in a Phase-8 security research note alongside ADR-0006.

---

## 4. XCP protocol behaviour under loss

This section establishes what XCP itself does and does not do about packet loss, and what the master must do to compensate. All claims are drawn from the ASAM XCP 1.4 spec (S1) and the Vector XCP Book V1.5 (S3).

### 4.1 XCP packet structure (refresher)

Every XCP frame has three layers:

```text
+---------------------+----------------+---------------------+
| Transport header    | XCP Packet     | Transport tail      |
| (CAN-ID / UDP hdr / | PID | Optional | (CAN CRC / UDP chk /|
|  COP-1 frame hdr)   | Fill | Payload | COP-1 frame trailer)|
+---------------------+----------------+---------------------+
```

The XCP packet identifier (PID) byte distinguishes:

- **CTO** (Command Transfer Object) — command + response/error/event. Bidirectional, transactional, master-initiated.
- **DTO** (Data Transfer Object) — DAQ measurement or STIM stimulation. Unidirectional, periodic, event-driven by the slave (DAQ) or the master (STIM).

### 4.2 The CTR field — XCP's only built-in loss detection

XCP-on-Ethernet (UDP/TCP) prepends each XCP packet with a **transport-layer header** that includes a **16-bit CTR (counter)** field. The Vector XCP Book V1.5 (S3) states it directly:

> "The CTR is used to identify a packet loss. UDP/IP is not a secure protocol. If a packet loss occurs, it is not intercepted by [UDP]." — Vector XCP Book V1.5, §"XCP on Ethernet"

The slave increments CTR on every transmitted packet. The master maintains a running expected CTR; any non-unit step is logged as a `DAQ_GAP` event (see §7) — this is the entire built-in mechanism.

CTR is per-direction and per-connection. On reconnect (CONNECT command) CTR resets to zero.

**Limitations of the CTR mechanism:**

- 16 bits — wraps every 65536 packets. At 1 kHz DAQ that is ~65 seconds. The master's CTR tracker must implement modular comparison (a 16-bit wraparound is not a loss event).
- Not used on XCP-on-CAN — there the CAN frame counter (per CAN-ID) plays a similar role implicitly via the CAN controller's bus-off / TEC/REC counters.
- Not authenticated — a masquerading injector can fabricate CTR values. Authenticity is provided by the AES-128 seed-and-key for the space profile (ADR-0006).

### 4.3 CTO ACK / RES / ERR semantics

CTO commands are transactional. The slave always responds with one of:

- **RES** (response) — successful execution, with optional return data.
- **ERR** (error) — failure with error code (per XCP §1.3 "Standard error codes").
- **EV** (event) — asynchronous slave-initiated event (e.g. CAL_PAGE_CHANGED).
- **SERV** (service request) — slave asks master for help (e.g. RESET).

The master applies a timeout per command type (parent §10 will pin these; provisional defaults: CONNECT 1000 ms, DISCONNECT 100 ms, GET_VERSION 100 ms, SET_MTA 100 ms, UPLOAD 100 ms, DOWNLOAD 100 ms, BUILD_CHECKSUM 1000 ms, SET_CAL_PAGE 100 ms). On timeout the master retries (cap 3) then declares the connection lost.

**Implication:** CTO loss is recovered to ≥99.9% reliability by master-side retry. This is why the CTO column of §6's budget table can be tight (residual ≤ 1e-9 per command).

### 4.4 SYNCH and START_STOP_SYNC — race-window guidance

XCP 1.4 (S5) added `START_STOP_SYNC` to address a race condition when starting multiple DAQ lists. The race: with the older `START_STOP_DAQ_LIST` issued per-list, the slave can begin transmitting DAQ packets for list N before the master finishes issuing the start command for list N+1, producing out-of-order ODT entries at the master.

`START_STOP_SYNC` starts/stops all configured DAQ lists atomically. Tethys's dispatcher must implement `START_STOP_SYNC` (parent §8 Phase-2 acceptance) as the canonical start path, exposing `START_STOP_DAQ_LIST` only for compatibility.

`SYNCH` resets the slave's protocol state machine without dropping the XCP connection. Used by the master to recover from CTO timeouts.

### 4.5 AUTOSAR E2E profile mapping

AUTOSAR PRS E2E Protocol (S6) defines eight profiles (1, 2, 4, 5, 6, 7, 11, 22) each combining {Counter, CRC, DataID, Timeout} to protect against fault classes {repetition, loss, delay, insertion, corruption, masquerade}. Tethys does not implement E2E, but its mechanisms are easily mapped onto the E2E vocabulary, which is helpful for safety-engineering reviewers:

| Fault class (per AUTOSAR PRS E2E §4.3.3) | Tethys mechanism | Standards trace |
| --- | --- | --- |
| Repetition | XCP CTR duplicate detection | S3 |
| Loss | XCP CTR gap detection → `DAQ_GAP` event; CTO retry on timeout | S3, S1 |
| Delay | Master timestamp delta against A2L event period | S1 |
| Insertion | AES-128 seed-and-key (space profile) | ADR-0006 |
| Corruption | Transport CRC (CAN-FD / Ethernet / COP-1) + A2L-typed limit check on CAL | S15, S10, S1 |
| Masquerade | AES-128 seed-and-key + service-mode authentication (space profile) | ADR-0006 |
| Addressing | XCP A2L hash mismatch detected at CONNECT time | S1 |

This is a **mapping**, not a claim of E2E conformance — the cipher suite and the counter widths differ. The mapping helps reviewers familiar with ISO 26262 communication-protection language read Tethys's fault-coverage posture quickly.

### 4.6 Implications for Tethys

- The transport layer must surface `transport_loss_event`, `transport_latency_us`, `transport_mtu` to the protocol layer. Codified in [ADR-0004 draft](../adr/drafts/adr-0004-transport-abstraction-layer.md).
- The master must implement a wrap-aware CTR tracker, with per-CONNECT reset. Codified in `tethys_master/protocol/ctr_tracker.py` (Phase 2).
- `START_STOP_SYNC` is the canonical DAQ-start command; `START_STOP_DAQ_LIST` is supported for compatibility only. Codified in Phase-2 dispatcher.
- AES-128 seed-and-key is mandatory in the space profile, optional in the marine profile (parent §3.3).

---

## 5. Per-transport SLA

For each transport Tethys supports (or plans to support), the table below gives observed/specified raw loss numbers and the layer that handles them. **Raw** = bit-error rate or frame-error rate on the wire. **Residual** = corrupted packet accepted as valid (i.e. CRC false-positive). **Observed** = realistic measured loss on a reference deployment.

### 5.1 UDP (master ↔ posix-sim, marine dev bench)

- **Raw BER:** ~1e-12 on a well-tuned Gigabit Ethernet LAN per the [OSADL real-time Ethernet UDP RTT monitor](https://www.osadl.org/Real-time-Ethernet-UDP-worst-case-roun.qa-farm-rt-ethernet-udp-monitor.0.html) historical record.
- **Observed packet loss:** 1e-4..1e-6 per packet on a typical industrial LAN under cyclic real-time load per [Industrial Ethernet UDP technical reference](https://industrialmonitordirect.com/blogs/knowledgebase/industrial-ethernet-protocols-using-udp-technical-reference).
- **Detection:** Tethys's XCP-on-Ethernet CTR field (§4.2).
- **Recovery:** None for DTO; master-side retry for CTO.
- **Implication for Tethys:** marine/UDP/DAQ budget = ≤ 1e-4 per packet; CTO = ≤ 1e-9 per command (post-retry).

### 5.2 TCP

- **Raw BER:** same as UDP.
- **Observed packet loss:** 0 (TCP retransmits at the stream layer).
- **Latency cost:** head-of-line blocking; a single retransmission stalls all subsequent DTO arrivals by one RTT.
- **Detection:** TCP itself; XCP CTR is still present but should never trip.
- **Recovery:** TCP.
- **Implication for Tethys:** TCP is the right choice for CAL/PAG write traffic where one-shot reliable delivery matters more than minimum latency. TCP is the wrong choice for high-rate DAQ because of head-of-line blocking. Use UDP for DAQ, TCP for CAL/PAG — configurable per A2L `XCP_ON_TCP_IP` vs `XCP_ON_UDP_IP` directive.

### 5.3 CAN-FD

- **Hamming distance:** ≥ 6 for both header and frame CRCs (CiA 2020 proceedings, S15).
- **Detectable errors:** up to 5 bit errors per frame (CiA, S15).
- **Specified residual frame error rate:** ~4.7e-11 per frame (CiA-derived; conservative bound from Hamming distance + CRC polynomial).
- **Dominant failure mode:** bus-off (transmit-error-counter ≥ 256) per ISO 11898-1.
- **Detection:** transport-layer error frames + CAN controller TEC/REC counters.
- **Recovery:** automatic for ordinary bit errors (error-frame retransmit); bus-off requires bus-off recovery (128 occurrences of 11 recessive bits) per ISO 11898-1.
- **Implication for Tethys:** marine/CAN-FD/CTO budget = ≤ 4.7e-11 per frame; no master-side compensation needed. Bus-off events are surfaced to the master as a `transport_bus_off` event for logging.

### 5.4 SocketCAN (CANable 2.0 host adapter)

- **Adds:** host-side queueing latency + driver-buffer overflow as a loss path.
- **Observed loss:** dominated by the user-space → kernel handover; pinning the receiver thread to a core eliminates most loss.
- **Recovery:** none — kernel drops are silent.
- **Implication for Tethys:** Tethys CI uses SocketCAN in loopback (vcan); a smoke test asserts a minimum throughput (e.g. 10000 frames in < 5 s with zero loss) so regressions in pinning / scheduling surface as failures.

### 5.5 UART / SxI (raw)

- **Raw BER:** 1e-5..1e-7 depending on link margin, baud rate, and shielding (industry typical; standard wireline reference numbers).
- **Specified residual frame error rate:** depends entirely on layer above.
- **Detection:** none at the raw UART level — needs a framing layer (HDLC, SLIP, or COP-1).
- **Recovery:** none at the raw UART level.
- **Implication for Tethys:** **Raw UART is not a usable Tethys transport for the space profile.** It must be wrapped in CCSDS COP-1 (§5.6). For development benches the raw UART/SxI mode is fine because the loss budget is loose (loopback or short cable).

### 5.6 CCSDS TC + COP-1 (space profile production reference)

CCSDS COP-1 (S10) defines two services on a Virtual Channel:

- **AD service** (Sequence-Controlled) — automatic retransmission via N(S) frame sequence number + N(R) acknowledgement carried in the CLCW (Communications Link Control Word). Quoting S10: *"For the AD Service, COP-1 ensures with a high probability of success that... [FDUs are delivered] in-order on a single Virtual Channel."*
- **BD service** (Expedited) — no retransmission; used for emergency uplink (e.g. anomaly recovery).

For Tethys's space profile, CTO commands ride AD service (guaranteed in-order). DAQ telemetry rides TM Space Data Link Protocol (CCSDS 132.0-B-3, S14) which is unreliable by design — the ground station accepts what it gets within the contact window. This matches the parent plan's space-profile philosophy (parent §3.3 "Logging: budgeted: ring buffer with watermark").

- **Raw BER target:** 1e-5..1e-7 budgeted for the SxI wire.
- **AD service residual:** ~1e-12 per frame typical (CCSDS-class mission target; achieved by ARQ retransmission).
- **TM-style residual:** none for the protocol (each frame stands alone); the ground-side software interpolates / discards.
- **Implication for Tethys:** the space profile splits its XCP traffic across two CCSDS services. CTO uses AD service; DAQ uses TM. CAL writes must use AD service (CTO-equivalent reliability). STIM uses AD service. Codified in [ADR-0010 draft](../adr/drafts/adr-0010-packet-loss-tolerance-budget.md).

### 5.7 CAN (1-wire fault-tolerant for space)

- **Raw BER:** higher than CAN-FD because of the lower bit rate and the single-wire fallback mode.
- **Specified residual:** ~1e-9 per frame (the same CRC polynomial gives the same residual; the worse raw BER doesn't change residual when frames that fail CRC are discarded).
- **Detection:** transport-layer error frames; bus-off.
- **Recovery:** error-frame retransmit; bus-off recovery; in 1-wire mode, automatic fallback from differential to single-wire.
- **Implication for Tethys:** space/CAN/CTO budget = ≤ 1e-9 per frame; mandatory CRC + EDAC on payload (parent §3.3 "Memory protection: mandatory ECC/EDAC wrapper on RAM regions exposed to XCP").

### 5.8 Loopback (posix-sim)

- **Raw BER:** 0 (in-process memory copy).
- **Observed loss:** 0.
- **Implication for Tethys:** the posix-sim loopback case is the only context where Tethys's acceptance criterion is "zero loss for 60 minutes" (parent §8 Phase-3 acceptance). Any observed loss in loopback is a test failure.

### 5.9 Summary

The per-transport facts above feed §6 directly; each cell of §6's table cites the row above it produced.

---

## 6. Profile loss budgets — the canonical table

This is the headline output of this research note. Every row is a row in [ADR-0010 draft](../adr/drafts/adr-0010-packet-loss-tolerance-budget.md). Numbers below are **proposed** (sub-plan Q1 — ADR-0010 status `proposed`); they will be revisited at Phase 3 acceptance if empirical measurement on the actual hardware diverges materially (sub-plan Q2).

### 6.1 The table

| # | Profile | Transport | Direction | XCP service | Raw loss target | Residual error target | Detection / recovery | Standards source |
| - | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Marine | UDP (IEC 61162-450) | master→slave | CTO | ≤ 1e-4 / pkt | ≤ 1e-9 / cmd (post-retry, cap 3) | XCP CTO timeout + retry | S13, S1 |
| 2 | Marine | UDP | slave→master | DAQ | ≤ 1e-4 / pkt | n/a (DAQ is unreliable by design) | XCP CTR → `DAQ_GAP` event into MDF4 | S13, S3 |
| 3 | Marine | UDP | slave→master | CAL (= CTO response) | same as row 1 | same as row 1 | same as row 1 | S13, S1 |
| 4 | Marine | TCP | both | CTO + CAL writes | 0 (TCP) | TCP CRC residual (~1e-12) | TCP retransmit | S13 |
| 5 | Marine | CAN-FD | master→slave | CTO | ≤ ~error-frame rate | ≤ 4.7e-11 / frame | CAN error-frame + TEC/REC; CTO retry | S15 |
| 6 | Marine | CAN-FD | slave→master | DAQ | same as row 5 | ≤ 4.7e-11 / frame | CAN error-frame; XCP CTR | S15, S3 |
| 7 | Marine | SocketCAN (host) | both | any | depends on host scheduling | same as row 5 + host-drop ε | smoke test on minimum-throughput | — |
| 8 | Space | UART/SxI + COP-1 AD | master→slave | CTO + CAL + STIM | raw BER 1e-7 budgeted | ≤ 1e-12 / frame (post-ARQ) | COP-1 N(S)/N(R) automatic retransmission | S10 |
| 9 | Space | TM (CCSDS 132.0-B-3) | slave→master | DAQ | mission-window-defined | none (per protocol) | XCP CTR → `DAQ_GAP`; ground software interpolates | S14, S3 |
| 10 | Space | CAN (1-wire FT) | both | CTO | ≤ ~error-frame rate | ≤ 1e-9 / frame | CAN error-frame; mandatory EDAC on CAL payload | S15 |
| 11 | Space | CAN (1-wire FT) | slave→master | DAQ | same as row 10 | ≤ 1e-9 / frame | same; XCP CTR | S15, S3 |
| 12 | Any | Loopback (posix-sim) | both | any | 0 | 0 | observed loss = test failure | — |

### 6.2 Continuous-loss (blackout) bounds

Per-packet residual is necessary but not sufficient; we also bound the length of a continuous-loss burst (blackout):

| Profile | Service | Max acceptable blackout | Rationale |
| --- | --- | --- | --- |
| Marine | DAQ @ 1 kHz | 100 ms (i.e. 100 packets) | Operator notification threshold; longer → alert. |
| Marine | DAQ @ 10 Hz | 1000 ms | Operator notification threshold. |
| Marine | CTO | 1000 ms (= 10× longest CTO timeout) | Connection-lost declared; auto-reconnect. |
| Space | DAQ in service mode | 1000 ms | Service-mode window is short; longer than 1 s and operators lose visibility. |
| Space | CTO | 5000 ms | Ground-link RTT can be high; longer timeout. |
| Any | Loopback | 0 | Loopback is reliable. |

### 6.3 Derivation — how the residual targets are justified

Per IEC 61784-3 (S8) and the residual-error paper (S8): the **residual error rate for a communication channel should be ≤ 1% of the IEC 61508 requested PFH** for the safety function the channel supports.

- IEC 61508 SIL 2 PFH: 1e-7 to 1e-6 per hour → channel residual ≤ 1e-9 to 1e-8 per hour. At 1000 packets/hour that gives ≤ 1e-12 to 1e-11 per packet.
- IEC 61508 SIL 3 PFH: 1e-8 to 1e-7 per hour → channel residual ≤ 1e-10 to 1e-9 per hour. At 1000 packets/hour: ≤ 1e-13 to 1e-12 per packet.
- ISO 26262 ASIL B PFH ≤ 1e-7/h (= IEC 61508 SIL 2 lower band) → residual ≤ 1e-9/h.
- ISO 26262 ASIL D PFH ≤ 1e-8/h (= IEC 61508 SIL 3 lower band) → residual ≤ 1e-10/h.

XCP is **not** the safety function in any Tethys deployment (per ADR-0001 it's a dev-time protocol; the safety function rides CCSDS / NMEA 2000 / the operational bus). Therefore Tethys's residual-error targets are anchored to **SIL 2 lower band** (the most permissive that still buys us into the IEC 61508 vocabulary) as a conservative defensive posture:

- Marine residual target: ≤ 1e-9 per command (CTO) → satisfied by CTO ACK + retry over any underlying transport.
- Marine residual target: ≤ 4.7e-11 per frame (DAQ on CAN-FD, no recovery) → satisfied by CAN-FD intrinsic Hamming distance 6 + CRC.
- Space residual target: ≤ 1e-12 per frame (CTO over COP-1 AD) → satisfied by COP-1 ARQ.
- Space residual target: ≤ 1e-9 per frame (CTO over 1-wire FT CAN) → satisfied by CAN CRC + mandatory EDAC.

The full PFH→residual derivation goes into [ADR-0010 draft](../adr/drafts/adr-0010-packet-loss-tolerance-budget.md).

### 6.4 Implications for Tethys

- Each row of §6.1 becomes one CI test in Phase 5 (transport conformance) and one row in Phase 10 (robustness suite). Pass criterion: measured residual ≤ target for the test campaign duration.
- Phase 3 acceptance ("1 kHz, zero loss for 60 minutes on simulator") = row 12. If a non-loopback run produces zero loss, that is bonus reliability; if it produces loss within the row 1/2 budget, the test still passes — the failure is on row 12 only.
- The marine/UDP/DAQ row (row 2) is loose by design — XCP-on-UDP is unreliable. Operational marine deployments that need lossless DAQ must use CAN-FD (row 6) or TCP (row 4).

---

## 7. DAQ recovery semantics

XCP does not retransmit DAQ packets. When the master detects a CTR gap, the recovery is master-side and the policy is configurable per ODT.

### 7.1 Master-side `DAQ_GAP` event

On a CTR gap the master emits a structured event into the MDF4 record:

```text
DAQ_GAP {
  timestamp_us: <master clock>,
  daq_list_id: <list number>,
  odt_id: <ODT number within list>,
  ctr_expected: <next expected CTR>,
  ctr_received: <CTR of next packet that arrived>,
  packets_lost: <ctr_received - ctr_expected, wrap-aware>,
  duration_us: <inter-packet arrival gap>,
  policy_applied: <none | interpolate | hold-last | halt>,
}
```

The MDF4 file contains both the measured signals **and** the gap events; downstream consumers (asammdf, Vector free MDF Viewer, Tethys's own viewer) render gaps visibly.

### 7.2 Per-ODT gap policy

A2L's CHARACTERISTIC / MEASUREMENT records do not encode a gap policy. Tethys adds a profile-specific extension via the IF_DATA section:

- `none` — record the gap and continue; downstream consumer chooses.
- `interpolate` — linear interpolation between the last known sample and the next; suitable for slowly-varying signals.
- `hold-last` — repeat the last value until the next packet; suitable for digital / step signals.
- `halt` — stop the measurement on gap; suitable for safety-critical signals where missing samples are unsafe to fill.

Default policy:

- Marine profile: `none` (operator interprets).
- Space profile: `halt` (no silent extrapolation in the space-flight window).

### 7.3 Phase 3 acceptance mapping

Parent §8 Phase-3 acceptance is "1 kHz DAQ on simulator with zero loss for 60 minutes". The simulator is the posix-sim loopback (row 12). Acceptance: 60 minutes × 1000 packets/s = 3.6e6 packets, zero loss. Any loss is a regression to investigate.

The same acceptance criterion does **not** apply over real Ethernet/CAN-FD — those are governed by rows 2 and 6 of §6.1.

### 7.4 Implications for Tethys

- The `DAQ_GAP` event schema is part of the Phase 3 master ODT engine deliverable.
- The per-ODT policy extension is an A2L IF_DATA section authored in PR-2 ([`xcp-protocol-discipline.mdc`](.cursor/rules/xcp-protocol-discipline.mdc) will assert it) and parsed by Phase 2's A2L parser.
- The default-per-profile mapping (marine `none`, space `halt`) is codified in `marine.cmake` / `space.cmake`.

---

## 8. CAL and PAG integrity

Calibration writes (DOWNLOAD / SHORT_DOWNLOAD against the calibration page) are higher-stakes than DAQ reads — a corrupted calibration value can break the next CAL session, the next reboot, or the next flight window. Tethys treats CAL writes as transactional + verified.

### 8.1 The write protocol

Tethys's CAL write sequence (extending XCP §2.3.2 standard flow):

1. Master sends `SET_MTA` to the CAL page address.
2. Master sends `DOWNLOAD` (or `SHORT_DOWNLOAD` for small payloads ≤ 6 bytes) with the new value.
3. Slave responds `RES` (success) or `ERR`.
4. Master sends `BUILD_CHECKSUM` over the address range covering the written value.
5. Slave returns the checksum.
6. Master verifies the checksum matches the expected value; if not, the write is **rolled back** (master re-DOWNLOADs the old value, then re-CHECKSUMs).
7. Master sends `COPY_CAL_PAGE` to commit the working page to the active page.

The CRC mismatch in step 6 is the gate that blocks a commit (parent §8 Phase-4 acceptance "CRC mismatch correctly blocks commit").

### 8.2 Marine profile additions

- Optional CRC on CAL page (compile-time `TETHYS_MARINE_CAL_PAGE_CRC=1`); the CRC is recomputed on every CAL page change and stored in a dedicated CAL-meta region.
- Recommended for production marine deployments; optional for development benches.

### 8.3 Space profile additions

- Mandatory EDAC wrapper on the CAL page RAM region (`tethys_edac.c`).
- Single-bit errors are corrected silently; double-bit errors raise a fault event that triggers a reload from the flash mirror page.
- EDAC parity overhead: 8 parity bits per 64 data bits (SEC-DED Hamming code) → ~12.5% memory cost; budgeted in ADR-0005.
- The flash mirror page is the canonical CAL backup; reboot reads from the mirror and re-applies to active RAM.

### 8.4 Implications for Tethys

- Phase 4 (CAL + PAG) builds the write protocol, the CRC gate, and the optional marine CRC.
- Phase 8 (space) adds the EDAC wrapper + flash mirror.
- The `tethys_edac.c` interface is a static-pure C module — no dynamic allocation, no recursion, MISRA C:2023 Mandatory + Required clean. Buffer sizes are derived from ADR-0005.

---

## 9. STIM safety

STIM (stimulation) is the slave-side counterpart of DAQ: the master sends DTO packets that the slave applies to a writable variable each cycle. STIM is powerful (used for closed-loop tuning, fault injection, software-in-the-loop) and dangerous (can drive an actuator to a destructive state).

### 9.1 Marine profile

- STIM permitted on a whitelist (A2L `STIM` directive on specific MEASUREMENT entries — only those entries can be STIM targets).
- Whitelist enforced at the slave; out-of-whitelist STIM packets are rejected with `ERR_OUT_OF_RANGE`.
- The whitelist is compile-time + A2L-derived; no runtime mutation.

### 9.2 Space profile

- STIM is **service-mode-only** (parent §3.3 "Permitted commands in flight mode: DAQ disabled by default, enabled via authenticated service-mode command").
- Service-mode unlock requires successful AES-128 seed-and-key exchange (16-byte challenge, 16-byte response).
- The whitelist still applies — service mode does not enable arbitrary STIM, only the whitelisted entries.
- Service mode auto-locks after an inactivity timeout (provisional default: 60 s).

### 9.3 Implications for Tethys

- The `stim_whitelist` table is populated at compile time by the A2L parser's IF_DATA scan.
- The `service_mode` state machine is a Phase-8 deliverable (`tethys_service_mode.c`).
- The `seed_and_key` interface is ADR-0006-defined; Phase 8 implements.

---

## 10. Fault-injection test catalogue

The catalogue below is the per-fault-class test list that Phase 5 (transport conformance) + Phase 8 (fault injection) + Phase 10 (robustness suite) must collectively cover. Each row gives the scenario, the detection layer, the expected master behaviour, the expected slave behaviour, and the pass criterion. This catalogue seeds the libFuzzer corpus (parent §6.7 `fuzz-nightly.yml`) and the robustness suite (parent §8 Phase-10).

### 10.1 Catalogue

| # | Scenario | Injection point | Detection layer | Expected master | Expected slave | Pass criterion |
| - | --- | --- | --- | --- | --- | --- |
| 1 | Drop 1 of every N DTO packets | Transport (UDP / vcan) | XCP CTR | Emit `DAQ_GAP` event | No change | Master count(DAQ_GAP) == ceil(total/N); MDF4 valid |
| 2 | Burst-K consecutive DTO loss | Transport | XCP CTR + master timestamp delta | Emit single `DAQ_GAP` event with `packets_lost = K` | No change | One DAQ_GAP per burst; duration_us within ±1 ms of expected |
| 3 | Reorder DTO packets at distance D | Transport (UDP) | XCP CTR | Out-of-order packets are dropped (older CTR rejected) | No change | Master count(rejected) == count(reordered); MDF4 valid |
| 4 | Duplicate DTO packets at rate R | Transport | XCP CTR | Duplicate packets dropped | No change | Master count(duplicate) ≈ R × total; MDF4 valid |
| 5 | Single-bit corruption on DTO payload | Transport | Transport CRC | DTO dropped at transport layer → counts as loss → row 1 | No change | Reduces to row 1 |
| 6 | Single-bit corruption on CTO payload | Transport | Transport CRC + CTO retry | Retry the CTO | No change | Master observes one retry; final command succeeds |
| 7 | CTO timeout (no response) | Slave | Master timeout | Retry (cap 3); then declare connection lost | No change | After 3 retries, connection-lost event raised |
| 8 | Slave reboot mid-DAQ | Slave | Connection lost + CONNECT mismatch on reconnect | Detect reconnect; reset CTR; restart DAQ | Reboots; new XCP session | Master DAQ resumes; MDF4 has explicit reboot marker |
| 9 | A2L drift (slave hash ≠ master A2L hash) | Master | CONNECT response | Refuse to start DAQ; require A2L re-fetch | No change | DAQ does not start; error surfaced to operator |
| 10 | CRC mismatch on CAL write | Slave | Master checksum verification | Roll back the write; raise error | No change | Old value preserved; error surfaced |
| 11 | Bus-off on CAN-FD | Slave / bus | Transport (CAN) | Connection lost event; auto-reconnect when bus recovers | Bus-off recovery (128× 11 recessive bits) | Master reconnects within 5 s of bus recovery |
| 12 | ECC double-bit error on CAL page (space) | Slave RAM | EDAC | Connection survives; slave raises EV_FAULT | Reload CAL from flash mirror | CAL re-applied; no operator action required |
| 13 | Service-mode auth failure (wrong key) | Master | Slave seed-and-key | Service mode remains locked; error surfaced | No state change | After 3 failed unlocks, slave locks for 10 minutes |
| 14 | MTU overflow (CTO > MAX_CTO) | Master | XCP slave | Reject malformed CTO with `ERR_CMD_SYNTAX` | Reject | Error returned; no slave state change |
| 15 | Malformed CTO PID byte | Master / fuzzer | XCP slave dispatcher | Reject with `ERR_CMD_UNKNOWN` | Reject | No crash; no memory unsafety (ASan / UBSan clean) |
| 16 | Continuous loss > blackout bound (§6.2) | Transport | Master blackout timer | Raise alert (`area/profile-marine` or `area/profile-space`); halt DAQ if policy `halt` | No change | Alert fires within ±100 ms of bound |

### 10.2 Mapping to Phase deliverables

- Rows 1-7 → Phase 5 transport conformance suite (one test per transport per row).
- Rows 8-11, 14-16 → Phase 10 robustness suite + libFuzzer corpus.
- Rows 12-13 → Phase 8 space-profile fault-injection bench.

### 10.3 Implications for Tethys

- The catalogue above is the canonical specification for the test corpus directories `slave/fuzz/corpus/` (parent §16) and `slave/tests/robustness/` (Phase 10).
- Each row produces one test fixture + one expected-output golden file. Phase 10's gate is "every row passes deterministically across three back-to-back runs".

---

## 11. ADR draft inputs

This research note seeds four ADR drafts under [`docs/adr/drafts/`](../adr/drafts/). PR-3 `p0-docs` formalises them with MADR v3.0 status headers and accepted-by-PR-N annotations. The drafts are self-contained but reference back here for derivations.

| ADR | Title | Status (PR-0c) | Key claim |
| --- | --- | --- | --- |
| [ADR-0001 (extension)](../adr/drafts/adr-0001-xcp-as-development-protocol.md) | XCP as a development-time protocol | proposed | XCP is dev-time; service-mode optionally enables flight DAQ; per-profile flight-mode whitelist; STIM service-mode-only in space. |
| [ADR-0004](../adr/drafts/adr-0004-transport-abstraction-layer.md) | Transport-abstraction-layer interface | proposed | The transport interface must surface `transport_loss_event`, `transport_latency_us`, `transport_mtu`, `transport_supports_reliable`, `transport_max_burst_loss`. |
| [ADR-0005](../adr/drafts/adr-0005-no-dynamic-allocation.md) | No dynamic allocation in the slave | proposed | Buffers are statically sized per the worst-case loss/burst row in ADR-0010; ODT buffer = `ceil(burst_loss_K × ODT_size × safety_margin)`. |
| [ADR-0010 (new)](../adr/drafts/adr-0010-packet-loss-tolerance-budget.md) | Packet-loss tolerance budget | proposed | The §6 canonical table is the contractual loss budget; SIL 2 lower-band residual; per-profile-per-transport-per-direction rows. |

---

## 12. References

All retrieval dates are 2026-05-14 unless noted.

### S1 — ASAM MCD-1 XCP 1.4

- URL: <https://www.asam.net/standards/detail/mcd-1-xcp/wiki>
- Cites: §1 (TL/DR), §3.1, §4 (whole), §6.3.
- Notes: XCP 1.4 (2017) adds packed DAQ, ODT optimisation strict mode, `START_STOP_SYNC`. Spec document itself is paywalled; the wiki is public.

### S2 — AUTOSAR SWS_XCP R20-11

- URL: <https://www.autosar.org/fileadmin/standards/R20-11/CP/AUTOSAR_SWS_XCP.pdf>
- Cites: §3.1, §4 (reference reading), §4.5.
- Notes: Document ID 412; XCP module for AUTOSAR Classic Platform; CAN-FD added in 4.4.0.

### S3 — Vector XCP Book V1.5

- URL: <https://cdn.vector.com/cms/content/application-areas/ecu-calibration/xcp/XCP_Book_V1.5_EN.pdf>
- Cites: §4.2 (CTR field), §4.3 (CTO ACK/RES), §4.4 (race), §4.5 (mapping), §5.1 (UDP).
- Key quote: "The CTR is used to identify a packet loss. UDP/IP is not a secure protocol. If a packet loss occurs, it is not intercepted by [UDP]" — XCP-on-Ethernet chapter.

### S4 — pyxcp (LGPLv3 reference implementation)

- URL: <https://github.com/christoph2/pyxcp>
- Cites: parent §3.1.
- Notes: Used for differential testing in Phase 2.

### S5 — XCP 1.4 release notes summary

- URL: <https://www.asam.net/standards/detail/mcd-1-xcp/wiki> (section "XCP 1.4")
- Cites: §4.4 (`START_STOP_SYNC` race fix).

### S6 — AUTOSAR PRS E2E Protocol R17-10

- URL: <https://www.autosar.org/fileadmin/standards/R17-10_R1.2.0/FO/AUTOSAR_PRS_E2EProtocol.pdf>
- Cites: §2.3 (error vocabulary), §4.5 (profile mapping).
- Notes: Profiles 1, 2, 4, 5, 6, 7, 11, 22 each with {Counter, CRC, DataID, Timeout}. Profile 1 = CRC-8-SAE J1850 (0x1D), CP-only.

### S7 — IEC 61508 parts 1-7

- URL: <https://webstore.iec.ch/publication/22273> (IEC 61508-1)
- Cites: §2.3 (vocabulary), §3.2, §6.3.
- Notes: Paywalled; SIL 2 PFH 1e-7..1e-6/h, SIL 3 PFH 1e-8..1e-7/h. The parent functional-safety standard.

### S8 — IEC 61784-3 + the residual-error paper

- IEC 61784-3 URL: <https://webstore.iec.ch/publication/63027>
- Residual-error paper URL: <https://easychair.org/publications/preprint/qM7d/open>
- Cites: §2.3, §6.3.
- Key quote (paper): "the residual error rate for a communication channel should be not more than 1% of the IEC61508 requested PFH".

### S9 — ISO 26262:2018 (user-requested explicit inclusion)

- URL: <https://www.iso.org/standard/68383.html> (part 1); <https://www.iso.org/standard/90028.html> (part 9 WD).
- Cites: §1 (TL/DR), §3.3, §6.3.
- Notes: Paywalled; 12 parts; ASIL D PFH ≤ 1e-8/h, ASIL B ≤ 1e-7/h. ISO 26262 communication protection delegates to AUTOSAR E2E (S6) and IEC 61784-3 (S8).

### S10 — CCSDS 232.1-B-2 (COP-1)

- URL: <https://ccsds.org/Pubs/232x1b1s.pdf>
- Cites: §1 (TL/DR), §5.6, §6.1 (row 8).
- Key quote: "For the AD Service, COP-1 ensures with a high probability of success that... [FDUs are delivered] in-order on a single Virtual Channel."

### S11 — IACS UR E22 Rev.3

- URL: <https://www.classnk.or.jp/hp/pdf/info_service/iacs_ur_and_ui/ur_e22_rev.3_june_2023_ul.pdf>
- Cites: §2.4 (marine profile), §3.6.
- Notes: In force 1 Jul 2024.

### S12 — IACS UR E22 Rev.3 Sep 2025 corrigendum

- URL: <https://www.classnk.or.jp/HP/pdf/info_service/iacs_ur_and_ui/ur_e22_rev.3_corr.1_sep_2025_cln.pdf>
- Cites: §2.4 (marine profile), §3.6.
- Notes: Latest applicable version.

### S13 — IEC 61162-450 + industrial UDP reference

- IEC 61162-450 URL: <https://webstore.iec.ch/publication/61011>
- Industrial Ethernet reference URL: <https://industrialmonitordirect.com/blogs/knowledgebase/industrial-ethernet-protocols-using-udp-technical-reference>
- OSADL RTT monitor URL: <https://www.osadl.org/Real-time-Ethernet-UDP-worst-case-roun.qa-farm-rt-ethernet-udp-monitor.0.html>
- Cites: §5.1, §6.1 (rows 1-3).

### S14 — CCSDS 132.0-B-3 (TM Space Data Link Protocol) + 130.0-G-3 summary

- TM SDLP URL: <https://ccsds.org/Pubs/132x0b3.pdf>
- 130.0-G-3 summary URL: <https://ccsds.org/Pubs/130x2g1s.pdf>
- Yamcs frame processing reference URL: <https://docs.yamcs.org/yamcs-server-manual/links/ccsds-frame-processing/>
- Cites: §5.6, §6.1 (row 9).

### S15 — CAN-FD specification + CiA 2020 proceedings

- CAN-FD spec URL: <https://tekeye.uk/downloads/can_fd_spec.pdf>
- CiA basic-idea URL: <https://can-cia.org/can-knowledge/can-fd-the-basic-idea>
- CiA 2020 proceedings (Mutter) URL: <https://can-cia.org/fileadmin/cia/documents/proceedings/2020_mutter.pdf>
- Cites: §5.3, §5.7, §6.1 (rows 5-7, 10-11).
- Notes: Hamming distance ≥ 6 for both header and frame CRCs; up to 5 detected bit errors per frame.

### S16 — ECSS-E-ST-50C

- URL: <http://everyspec.com/ESA/download.php?spec=ECSS-E-ST-50C.048171.pdf>
- Cites: §3.4.

### S17 — ECSS-E-AS-50-25C Rev.1 (CCSDS adoption)

- URL: <https://ecss.nl/wp-content/uploads/2023/01/ECSS-E-AS-50-25C-Rev.1(13January2023).pdf>
- Cites: §3.4.

### S18 — ECSS-E-ST-40C Rev.1 (April 2025)

- URL: <https://ecss.nl/standard/ecss-e-st-40c-rev-1-software-general-requirements-2-april-2025/>
- Cites: §2.4 (space profile), §3.4.
- Notes: Latest revision; SW general requirements.

### S19 — ECSS-Q-ST-80C + ECSS-Q-ST-60-02C

- ECSS-Q-ST-80C URL: <https://ecss.nl/standard/ecss-q-st-80c-rev-1-software-product-assurance-15-february-2017/>
- ECSS-Q-ST-60-02C URL: <https://ecss.nl/standard/ecss-q-st-60-02c-asic-and-fpga-development-30-july-2008/>
- Cites: §3.4.

### S20 — NPR 7150.2D + NASA-STD-8739.8 + NASA-HDBK-2203

- NPR 7150.2D URL: <https://nodis3.gsfc.nasa.gov/npg_img/N_PR_7150_002D_/N_PR_7150_002D_.pdf>
- NASA-STD-8739.8 URL: <https://standards.nasa.gov/standard/nasa/nasa-std-87398>
- NASA-HDBK-2203 URL: <https://swehb.nasa.gov/>
- Cites: §3.4, §2.4.

### S21 — IACS UR E26 Rev.1

- URL: <https://www.classnk.or.jp/hp/pdf/info_service/iacs_ur_and_ui/ur_e26_rev.1_nov_2023_cr.pdf>
- Cites: §3.6.
- Notes: Cyber resilience of ships.

### S22 — DO-178C + DO-330

- DO-178C: RTCA / EUROCAE ED-12C, paywalled.
- DO-330: RTCA / EUROCAE ED-215, paywalled.
- Cites: §1 (informational), §3.5.

### S23 — DO-326A / ED-202A

- RTCA / EUROCAE, paywalled.
- Cites: §3.5 (section-only).

### S24 — IEC 62443

- URL: <https://webstore.iec.ch/publication/7029>
- Cites: §3.2 (section-only).

### S25 — IEC 60945 + IEC 61162-1 + NMEA 2000 + ISO 24060:2021 + IMO MSC.428(98)

- ISO 24060 URL: <https://www.iso.org/standard/77761.html>
- IMO MSC.428(98) URL: <https://wwwcdn.imo.org/localresources/en/OurWork/Security/Documents/Resolution%20MSC.428(98).pdf>
- Cites: §3.6.

### S26 — DNV-CG-0264 + LR ShipRight Software

- DNV-CG-0264 URL: <https://www.dnv.com/maritime/publications/computer-based-systems-class-guideline.html>
- LR ShipRight URL: <https://www.lr.org/en/maritime/services-for-ships/marine-software-services/>
- Cites: §3.6 (alternative class anchors).

### S27 — Sauci/pya2l + christoph2/pyA2L

- Sauci URL: <https://github.com/Sauci/pya2l>
- christoph2 URL: <https://github.com/christoph2/pyA2L>
- Cites: parent §3.1.

### S28 — vectorgrp/XCPlite (reading reference)

- URL: <https://github.com/vectorgrp/XCPlite>
- Cites: parent §3.2.
- Notes: MIT-licensed reference for the Ethernet path; Tethys clean-rooms against ASAM XCP 1.4 (S1) for licensing cleanliness.

### S29 — ISO 11898-1:2024

- URL: <https://www.iso.org/standard/86384.html>
- Cites: §3.7, §5.3, §5.4.
- Notes: CAN-FD now part of ISO 11898-1.

### S30 — IACS UR E27

- URL: <https://www.iacs.org.uk/resolutions/unified-requirements/ur-e/>
- Cites: §3.6.

## 13. Implementation Reference

<!-- status-sync (sub-plan todo `status-sync`) appends the merged PR URL here once PR-0c is merged. -->

- PR: *to be filled at merge*
- Merged on: *to be filled at merge*
