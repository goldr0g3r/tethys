# ADR-0004 — Transport-abstraction-layer interface (draft)

- **Status:** proposed
- **Date:** 2026-05-14
- **Deciders:** project owner
- **Source PR:** PR-0c `docs(research): system requirements + packet-loss tolerance budget`
- **Promoted by:** PR-3 `docs(architecture)`; frozen by PR-5 / Phase-5 `freeze TransportPort interface`
- **Supersedes:** —
- **Superseded by:** —

> Draft seeded by [`docs/research/phase-0-system-requirements.md`](../../research/phase-0-system-requirements.md) §4.6, §5.

## Context

Tethys supports multiple transports across two profiles (parent §5 toolchain, §3.3 profile table):

- UDP + TCP (master ↔ posix-sim, marine dev bench)
- CAN-FD via SocketCAN (CANable 2.0)
- UART / SxI wrapped in CCSDS COP-1 (space bench)
- 1-wire fault-tolerant CAN (space bench)
- Loopback (posix-sim)

The protocol layer (`tethys_core/`) must be transport-agnostic. Each transport has different reliability, latency, framing, and loss-detection semantics ([`phase-0-system-requirements.md §5`](../../research/phase-0-system-requirements.md#5-per-transport-sla)). The transport interface must surface enough information for the protocol layer to apply the right loss-tolerance policy per [ADR-0010 draft](adr-0010-packet-loss-tolerance-budget.md).

## Decision

The transport-abstraction layer is a C-language interface (`include/tethys/transport.h`) that every concrete transport implements. The interface exposes both an **operational API** (send / receive / connect / disconnect) and a **metadata API** (capabilities the protocol layer reads to apply correct policy).

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
| `transport_mtu` | uint16_t | max frame payload size in bytes | DAQ ODT sizing (ADR-0005); CTO MAX_CTO |
| `transport_supports_reliable` | bool | true if underlying transport retransmits (TCP, COP-1 AD) | choose recovery policy |
| `transport_max_burst_loss` | uint16_t | expected max consecutive packet loss in a burst (per §5 SLA) | ODT buffer sizing (ADR-0005) |
| `transport_typical_latency_us` | uint32_t | expected one-way latency in microseconds | CTO timeout per command class |
| `transport_typical_loss_per_pkt` | float | expected packet-loss rate per [ADR-0010 draft](adr-0010-packet-loss-tolerance-budget.md) | DAQ_GAP alert threshold |
| `transport_supports_ordering` | bool | true if transport preserves order (TCP, CAN, COP-1 AD) | reorder detection policy |

### Event API (out-of-band loss notification)

In addition to the operational API the transport surfaces structured events:

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

/* Protocol layer registers a callback at init. */
void tethys_tr_set_event_cb(void (*cb)(const tethys_tr_event_t *));
```

The XCP protocol layer's `DAQ_GAP` event ([`phase-0-system-requirements.md §7`](../../research/phase-0-system-requirements.md#7-daq-recovery-semantics)) is constructed by combining the transport's `TETHYS_TR_EVT_LOSS` event with the XCP CTR mismatch.

## Consequences

- Adding a new transport (e.g. SpaceWire) requires implementing the operational + metadata + event APIs; no protocol-layer change.
- The `transport_max_burst_loss` field drives ODT buffer sizing in [ADR-0005 draft](adr-0005-no-dynamic-allocation.md), which in turn drives the static memory map.
- The interface is frozen by Phase-5 (parent §8 Phase-5 "freeze TransportPort interface"); breaking changes after that point require a new ADR.
- The metadata API is read-only — transports do not negotiate; they declare. Loss budgets in [ADR-0010 draft](adr-0010-packet-loss-tolerance-budget.md) are the contract.

## Alternatives considered

- **Hide capabilities; have protocol layer probe.** Rejected — probing adds startup latency and can race with actual traffic.
- **One transport, switch via #ifdef.** Rejected — Phase 5 requires the conformance suite to run unmodified across three transports.

## References

- [`docs/research/phase-0-system-requirements.md`](../../research/phase-0-system-requirements.md) §4.6, §5, §6.
- Parent plan section 3.2 "Layered design"; section 8 Phase-5.
