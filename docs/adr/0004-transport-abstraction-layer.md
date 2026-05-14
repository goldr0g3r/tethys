# ADR-0004 - Transport-abstraction-layer interface

- **Status:** accepted
- **Date:** 2026-05-14
- **Deciders:** @goldr0g3r (project owner)
- **Consulted:** (solo decision; backed by [`docs/research/phase-0-system-requirements.md`](../research/phase-0-system-requirements.md) §4.6, §5)
- **Informed:** future transport authors; Phase-5 implementers
- **Supersedes:** —
- **Superseded by:** —
- **Accepted by:** PR-3 `docs(architecture)` (elevated from the draft seeded in PR-0c)
- **Freeze deadline:** PR-5 / Phase 5 `freeze TransportPort interface` (parent §8). Breaking changes after that point require a new ADR.

## Context and Problem Statement

Tethys supports multiple transports across two profiles (parent §5 toolchain, §3.3 profile table):

- UDP + TCP (master ↔ posix-sim, marine dev bench)
- CAN-FD via SocketCAN (CANable 2.0)
- UART / SxI wrapped in CCSDS COP-1 (space bench)
- 1-wire fault-tolerant CAN (space bench)
- Loopback (posix-sim)

The protocol layer (`tethys_core/`) must be transport-agnostic. Each transport has different reliability, latency, framing, and loss-detection semantics ([`phase-0-system-requirements.md` §5](../research/phase-0-system-requirements.md#5-per-transport-sla)). The transport interface must surface enough information for the protocol layer to apply the right loss-tolerance policy per [ADR-0010](0010-packet-loss-tolerance-budget.md).

## Decision Drivers

- Phase 5 acceptance criterion: one conformance suite reused across every transport (parent §8 Phase-5).
- Slave-side static memory map per [ADR-0005](0005-no-dynamic-allocation.md) requires `transport_max_burst_loss` at compile time.
- Per-profile invariants per [`marine-profile-invariants.mdc`](../../.cursor/rules/marine-profile-invariants.mdc) + [`space-profile-invariants.mdc`](../../.cursor/rules/space-profile-invariants.mdc) constrain which transports each profile selects.
- Future transports (SpaceWire, ARINC 664p7) should land without protocol-layer changes.

## Considered Options

1. **Hide transport capabilities; have protocol layer probe at runtime.** Slave issues a probe command at CONNECT; transport responds with its capability set.
2. **Single transport with compile-time `#ifdef` switching.** Pick one transport per build; reject the multi-transport scenario.
3. **Operational + Metadata + Event APIs declared statically by each transport.** Transports declare their capabilities through structured fields read by the protocol layer at init; the protocol layer never probes.

## Decision Outcome

Chose **Option 3** (statically-declared operational + metadata + event APIs).

### Operational API

```c
typedef enum {
    TETHYS_TR_OK = 0,
    TETHYS_TR_TIMEOUT,
    TETHYS_TR_DISCONNECTED,
    TETHYS_TR_FRAME_ERR,
    TETHYS_TR_BUS_OFF,
    TETHYS_TR_INVAL,
    TETHYS_TR_OOM_STATIC,
} tethys_tr_status_t;

tethys_tr_status_t tethys_tr_send(const uint8_t *frame, size_t len);
tethys_tr_status_t tethys_tr_recv(uint8_t *buf, size_t buf_len, size_t *out_len);
tethys_tr_status_t tethys_tr_connect(void);
tethys_tr_status_t tethys_tr_disconnect(void);
```

### Metadata API (capability flags read at init)

The protocol layer reads these once at CONNECT time:

| Field | Type | Meaning | Used by |
| --- | --- | --- | --- |
| `transport_id` | enum | UDP / TCP / CAN_FD / SOCKETCAN / UART_SXI / CCSDS_COP1_AD / CCSDS_TM / CAN_1WIRE / LOOPBACK | logging, MDF4 header |
| `transport_mtu` | uint16_t | max frame payload size in bytes | DAQ ODT sizing ([ADR-0005](0005-no-dynamic-allocation.md)); CTO MAX_CTO |
| `transport_supports_reliable` | bool | true if underlying transport retransmits (TCP, COP-1 AD) | choose recovery policy |
| `transport_max_burst_loss` | uint16_t | expected max consecutive packet loss in a burst | ODT buffer sizing ([ADR-0005](0005-no-dynamic-allocation.md)) |
| `transport_typical_latency_us` | uint32_t | expected one-way latency in microseconds | CTO timeout per command class |
| `transport_typical_loss_per_pkt` | float | expected packet-loss rate per [ADR-0010](0010-packet-loss-tolerance-budget.md) | `DAQ_GAP` alert threshold |
| `transport_supports_ordering` | bool | true if transport preserves order (TCP, CAN, COP-1 AD) | reorder detection policy |

### Event API (out-of-band loss notification)

In addition to the operational API, transports surface structured events:

```c
typedef enum {
    TETHYS_TR_EVT_LOSS,           /* one or more frames dropped */
    TETHYS_TR_EVT_LATENCY_HIGH,   /* one-way latency exceeded SLA */
    TETHYS_TR_EVT_BUS_OFF,        /* CAN bus-off */
    TETHYS_TR_EVT_BUS_RECOVERED,  /* CAN recovered from bus-off */
    TETHYS_TR_EVT_RECONNECTED,    /* automatic reconnect succeeded */
} tethys_tr_evt_kind_t;

typedef struct {
    tethys_tr_evt_kind_t kind;
    uint32_t timestamp_us;
    uint16_t count;              /* frames affected by this event */
    uint16_t reserved;
} tethys_tr_event_t;

void tethys_tr_set_event_cb(void (*cb)(const tethys_tr_event_t *));
```

The XCP protocol layer's `DAQ_GAP` event ([`phase-0-system-requirements.md` §7](../research/phase-0-system-requirements.md#7-daq-recovery-semantics)) is constructed by combining the transport's `TETHYS_TR_EVT_LOSS` event with the XCP CTR mismatch.

## Consequences

- **Positive:** Adding a new transport (SpaceWire, ARINC 664p7) requires implementing the operational + metadata + event APIs; no protocol-layer change.
- **Positive:** `transport_max_burst_loss` drives ODT buffer sizing in [ADR-0005](0005-no-dynamic-allocation.md), which in turn drives the static memory map.
- **Positive:** The metadata API is read-only — transports do not negotiate; they declare. Loss budgets in [ADR-0010](0010-packet-loss-tolerance-budget.md) are the contract.
- **Negative:** Interface freeze at Phase-5 closes the door on cheap iteration; subsequent breaking changes require a new ADR.
- **Risk:** Misdeclared capabilities (e.g. claiming `transport_supports_reliable: true` when TCP is misconfigured) silently corrupt loss accounting. **Mitigation:** Phase-5 conformance suite verifies declared vs observed behaviour for every transport.

## References

- [`docs/research/phase-0-system-requirements.md`](../research/phase-0-system-requirements.md) §4.6, §5, §6.
- Parent plan section 3.2 "Layered design"; section 8 Phase-5.
- [ADR-0005](0005-no-dynamic-allocation.md) - consumes `transport_max_burst_loss`.
- [ADR-0010](0010-packet-loss-tolerance-budget.md) - the loss-budget table this interface implements.
