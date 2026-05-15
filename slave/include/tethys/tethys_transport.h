/*
 * tethys/tethys_transport.h - Transport Abstraction Layer (TAL) public interface.
 *
 * Module: tethys::transport (interface)
 * Profiles: all (marine, space, posix-sim)
 * Standards: ASAM XCP 1.4 Part 1 §1.1 (transport-layer agnosticism);
 *            MISRA C:2023; ECSS-E-ST-40C Rev.1 §5.4
 * Trace: docs/traceability.csv (rows TETHYS-DES-0030..0034 - transport interface)
 *
 * Implements ADR-0004 (transport-abstraction-layer interface). This header is
 * the frozen contract that every concrete transport descriptor must satisfy.
 *
 *   - Operational API: send / recv / connect / disconnect (return codes only).
 *   - Metadata API:    transport_id, mtu, capability flags, loss budgets.
 *                      Read once by the protocol layer at CONNECT time.
 *   - Event API:       structured out-of-band notifications (loss, latency,
 *                      bus-off, bus-recovered, reconnected).
 *
 * Each concrete transport (loopback, SocketCAN, UART/SxI, UDP, ...) lives in
 * `slave/src/transport/<name>.c` and exposes:
 *
 *   const tethys_tr_descriptor_t *tethys_tr_<name>_descriptor(void);
 *
 * The host process activates one transport via:
 *
 *   tethys_tr_register_transport(tethys_tr_loopback_descriptor());
 *   tethys_tr_connect();
 *
 * The XCP dispatcher (slave/src/core/xcp_dispatcher.c) is transport-agnostic
 * and only sees `tethys_tr_send` / `tethys_tr_recv`. The descriptor's metadata
 * is consumed elsewhere (ODT buffer sizing, CTO timeout selection, MDF4
 * header annotation).
 *
 * Memory model: no dynamic allocation (ADR-0005). Every transport descriptor
 * is a `static const` instance in its .c file; the active-transport pointer
 * lives in TAL state. No heap is used by the TAL itself.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_TETHYS_TRANSPORT_H
#define TETHYS_TETHYS_TRANSPORT_H

#pragma once

#include "tethys/tethys_export.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Wire-independent status codes (ADR-0004) ------------------------ */

/**
 * @brief Transport operation return code.
 *
 * One enum shared across every transport. The protocol layer maps these onto
 * XCP error responses where appropriate; the TAL never returns errno-style
 * negative ints.
 */
typedef enum {
    TETHYS_TR_OK = 0,           /**< operation completed normally */
    TETHYS_TR_TIMEOUT,          /**< recv timed out waiting for a frame */
    TETHYS_TR_DISCONNECTED,     /**< transport not connected (or disconnected mid-op) */
    TETHYS_TR_FRAME_ERR,        /**< framing or checksum error on inbound frame */
    TETHYS_TR_BUS_OFF,          /**< CAN bus-off detected; recovery required */
    TETHYS_TR_INVAL,            /**< argument error (null ptr, len overflow) */
    TETHYS_TR_OOM_STATIC,       /**< static buffer exhausted (ADR-0005 backstop) */
    TETHYS_TR_UNSUPPORTED       /**< transport refuses this op (e.g. recv on TX-only) */
} tethys_tr_status_t;

/* ---- Transport identity (ADR-0004 metadata API) ---------------------- */

/**
 * @brief Stable, build-independent identifier for a transport.
 *
 * MDF4 header records this so post-flight log readers can tell which
 * transport was active. New IDs append at the bottom; never renumber.
 */
typedef enum {
    TETHYS_TR_UNDEFINED = 0,
    TETHYS_TR_LOOPBACK,         /**< in-process loopback (posix-sim, test harness) */
    TETHYS_TR_UDP,              /**< XCP-on-Ethernet UDP (parent §3.1) */
    TETHYS_TR_TCP,              /**< XCP-on-Ethernet TCP (parent §3.1) */
    TETHYS_TR_CAN_FD,           /**< XCP-on-CAN-FD (marine production) */
    TETHYS_TR_SOCKETCAN,        /**< Linux SocketCAN (host bench via CANable 2.0) */
    TETHYS_TR_UART_SXI,         /**< Raw UART / SxI byte stream (space bench) */
    TETHYS_TR_CCSDS_COP1_AD,    /**< UART/SxI + CCSDS COP-1 AD wrap (Phase 8) */
    TETHYS_TR_CCSDS_TM,         /**< CCSDS TM telemetry (Phase 8) */
    TETHYS_TR_CAN_1WIRE         /**< Fault-tolerant 1-wire CAN (space bench) */
} tethys_tr_id_t;

/* ---- Out-of-band event API (ADR-0004) -------------------------------- */

/**
 * @brief Event kind reported via the registered callback.
 *
 * Out-of-band relative to the send/recv path. The XCP DAQ_GAP event
 * (system-requirements §7) is constructed from `TETHYS_TR_EVT_LOSS` combined
 * with the XCP CTR mismatch in the protocol layer.
 */
typedef enum {
    TETHYS_TR_EVT_LOSS = 0,         /**< one or more frames dropped */
    TETHYS_TR_EVT_LATENCY_HIGH,     /**< one-way latency exceeded SLA */
    TETHYS_TR_EVT_BUS_OFF,          /**< CAN bus-off declared */
    TETHYS_TR_EVT_BUS_RECOVERED,    /**< CAN recovered from bus-off */
    TETHYS_TR_EVT_RECONNECTED       /**< automatic reconnect succeeded */
} tethys_tr_evt_kind_t;

/**
 * @brief Structured event passed to the registered event callback.
 *
 * Packed-but-aligned shape: 16 bytes on every common architecture. No padding
 * on x86-64 / ARM Cortex-M / RISC-V because the largest member is 4-byte.
 */
typedef struct {
    tethys_tr_evt_kind_t kind;
    uint32_t             timestamp_us; /**< monotonic microseconds at event time */
    uint16_t             count;        /**< frames affected (e.g. burst-loss length) */
    uint16_t             reserved;     /**< MUST be zero in current revision */
} tethys_tr_event_t;

/**
 * @brief Signature of the transport-event callback.
 *
 * Invoked from the transport's own thread or the polling tick; MUST be
 * non-blocking and re-entrancy-safe. The caller does not retain ownership of
 * the event pointer beyond the call; copy if needed.
 */
typedef void (*tethys_tr_event_cb_t)(const tethys_tr_event_t *ev);

/* ---- Descriptor table (ADR-0004 metadata API) ------------------------ */

/**
 * @brief Per-transport descriptor: vtable + capability flags.
 *
 * Each concrete transport exports a `static const tethys_tr_descriptor_t`
 * via a `tethys_tr_<name>_descriptor()` accessor. The TAL stores the active
 * descriptor pointer and forwards `tethys_tr_send` / `tethys_tr_recv` /
 * `tethys_tr_connect` / `tethys_tr_disconnect` through it.
 *
 * `recv_timeout_us` < UINT32_MAX selects bounded waiting; pass 0 for
 * non-blocking polling. Transports without a real timeout (loopback)
 * MAY ignore this parameter and return immediately.
 */
typedef struct {
    /* ---- Identity / capability flags (read at CONNECT time) ---- */
    tethys_tr_id_t id;                  /**< stable identifier; never renumbered */
    const char    *name;                /**< short ASCII name for logs (NUL-term) */
    uint16_t       mtu;                 /**< max payload size in bytes */
    bool           supports_reliable;   /**< transport retransmits (TCP, COP-1 AD) */
    bool           supports_ordering;   /**< transport preserves frame order */
    uint16_t       max_burst_loss;      /**< expected max consecutive loss (ADR-0010) */
    uint32_t       typical_latency_us;  /**< expected one-way latency in microseconds */
    /* Loss rate is in parts-per-billion (PPB) to avoid float in the slave.
     * 1 PPB = 1e-9. ADR-0010 row 5 (CAN-FD CTO) = ~47 PPB ≈ 4.7e-11/frame;
     * we round to 1 PPB resolution because the slave's loss-detection
     * heuristic doesn't need finer than that. */
    uint32_t       typical_loss_ppb;

    /* ---- Operational vtable (each may be NULL only if UNSUPPORTED) ---- */
    tethys_tr_status_t (*connect)(void);
    tethys_tr_status_t (*disconnect)(void);
    tethys_tr_status_t (*send)(const uint8_t *frame, size_t len);
    tethys_tr_status_t (*recv)(uint8_t *buf, size_t buf_len, size_t *out_len, uint32_t timeout_us);
} tethys_tr_descriptor_t;

/* ---- Operational API (forwards to active descriptor) ----------------- */

/**
 * @brief Install a transport descriptor as the active TAL backend.
 *
 * Idempotent if the same descriptor is registered twice. Switching to a
 * different descriptor implicitly disconnects the previous one if it is
 * connected.
 *
 * @param[in] desc Descriptor pointer (typically returned by a
 *                 `tethys_tr_<name>_descriptor()` accessor). MUST outlive
 *                 the TAL (a `static const` in a transport .c file).
 *
 * @return TETHYS_TR_OK on success, TETHYS_TR_INVAL on NULL or malformed
 *         descriptor (missing vtable entries, id == UNDEFINED, mtu == 0).
 */
TETHYS_EXPORT tethys_tr_status_t tethys_tr_register_transport(const tethys_tr_descriptor_t *desc);

/**
 * @brief Detach the active transport (without invoking its `disconnect`).
 *
 * Used by tests to reset TAL state between cases. After this call,
 * `tethys_tr_active_descriptor()` returns NULL and all operational calls
 * return TETHYS_TR_DISCONNECTED.
 */
TETHYS_EXPORT void tethys_tr_reset(void);

/**
 * @brief Read the current active descriptor.
 *
 * @return Pointer to the active descriptor, or NULL if none is registered.
 *         The pointer is read-only and owned by the transport module.
 */
TETHYS_EXPORT const tethys_tr_descriptor_t *tethys_tr_active_descriptor(void);

/**
 * @brief Open the transport (forwarded to active descriptor's `connect`).
 */
TETHYS_EXPORT tethys_tr_status_t tethys_tr_connect(void);

/**
 * @brief Close the transport (forwarded to active descriptor's `disconnect`).
 */
TETHYS_EXPORT tethys_tr_status_t tethys_tr_disconnect(void);

/**
 * @brief Transmit one frame.
 *
 * @param[in] frame  Pointer to payload bytes (caller-owned).
 * @param[in] len    Number of bytes to send; MUST be <= descriptor->mtu.
 *
 * @return TETHYS_TR_OK on success.
 * @return TETHYS_TR_INVAL if frame == NULL, len == 0, or len > mtu.
 * @return TETHYS_TR_DISCONNECTED if no descriptor is registered or transport
 *         was not connected.
 * @return TETHYS_TR_FRAME_ERR / TETHYS_TR_BUS_OFF on transport-specific
 *         failures.
 */
TETHYS_EXPORT tethys_tr_status_t tethys_tr_send(const uint8_t *frame, size_t len);

/**
 * @brief Receive one frame (bounded wait).
 *
 * @param[out] buf         Caller-owned buffer; MUST be at least descriptor->mtu.
 * @param[in]  buf_len     Capacity of @p buf in bytes.
 * @param[out] out_len     Receives the number of bytes written to @p buf on
 *                         TETHYS_TR_OK. Untouched on any other return.
 * @param[in]  timeout_us  Max time to wait in microseconds. UINT32_MAX means
 *                         "block until something arrives or transport
 *                         disconnects". 0 means "poll: return immediately if
 *                         nothing pending".
 *
 * @return TETHYS_TR_OK if a frame was received.
 * @return TETHYS_TR_TIMEOUT if the deadline elapsed with no frame.
 * @return TETHYS_TR_INVAL / TETHYS_TR_DISCONNECTED as for send.
 */
TETHYS_EXPORT tethys_tr_status_t tethys_tr_recv(
    uint8_t *buf, size_t buf_len, size_t *out_len, uint32_t timeout_us);

/**
 * @brief Register the event-callback sink.
 *
 * @param[in] cb  Callback function pointer or NULL to detach. Replaces any
 *                previously-registered callback.
 *
 * @note Thread-safety: the callback is invoked from whichever context the
 *       transport polls / receives in. Callbacks MUST be non-blocking and
 *       MUST NOT call back into the TAL.
 */
TETHYS_EXPORT void tethys_tr_set_event_cb(tethys_tr_event_cb_t cb);

/**
 * @brief Dispatch an event to the registered callback (internal helper).
 *
 * Transport implementations call this when they observe loss, latency, or
 * bus-off. No-op if no callback is registered.
 */
TETHYS_EXPORT void tethys_tr_emit_event(const tethys_tr_event_t *ev);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_TETHYS_TRANSPORT_H */
