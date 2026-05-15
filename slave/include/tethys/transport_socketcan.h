/*
 * tethys/transport_socketcan.h - Linux SocketCAN transport (CANable 2.0 bench).
 *
 * Module: tethys::transport::socketcan
 * Profiles: marine (CAN-FD dev bench); not used in production embedded builds
 * Standards: ADR-0004 (transport-abstraction-layer interface);
 *            ADR-0010 row 7 (SocketCAN host-side budget);
 *            ISO 11898-1:2024 (CAN data-link layer);
 *            ISO 11898-2 (CAN-FD physical layer)
 * Trace: docs/traceability.csv (TETHYS-DES-0032 SocketCAN transport)
 *
 * Wraps a Linux `PF_CAN` / `SOCK_RAW` / `CAN_RAW` socket bound to a named
 * interface (default "can0" or "vcan0" for virtual CAN). Each XCP CTO/DTO
 * frame is sent as one `struct canfd_frame` (CAN-FD MTU 64 bytes per frame;
 * classic CAN 8 bytes is supported as a build option).
 *
 * On non-Linux builds the descriptor is still exported but every operational
 * function returns TETHYS_TR_DISCONNECTED so the test harness can be
 * compiled and run on Windows / macOS for portability checks.
 *
 * Bench wiring (parent §5 + docs/runbooks/hardware-setup-stm32.md):
 *   PC <-USB-> CANable 2.0 <-CAN-FD-> STM32 Nucleo
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_TRANSPORT_SOCKETCAN_H
#define TETHYS_TRANSPORT_SOCKETCAN_H

#pragma once

#include "tethys/tethys_export.h"
#include "tethys/tethys_transport.h"

#ifdef __cplusplus
extern "C" {
#endif

/** SocketCAN MTU - 64 bytes is the CAN-FD payload limit (ISO 11898-1:2024).
 *  Classic CAN truncates to 8 bytes at the link layer. We declare the FD MTU
 *  and let the host kernel reject FD frames if the interface is classic-only. */
#define TETHYS_SOCKETCAN_MTU   ((uint16_t)64U)

/** Maximum interface-name length (Linux IFNAMSIZ minus NUL). */
#define TETHYS_SOCKETCAN_IFNAMSZ ((size_t)15U)

/**
 * @brief Get the SocketCAN descriptor.
 *
 * @return Non-NULL descriptor pointer. On non-Linux builds the vtable returns
 *         TETHYS_TR_DISCONNECTED for every call.
 */
TETHYS_EXPORT const tethys_tr_descriptor_t *tethys_tr_socketcan_descriptor(void);

/**
 * @brief Configure the CAN interface name before connect().
 *
 * @param[in] ifname  NUL-terminated interface name (e.g. "can0", "vcan0").
 *                    Length MUST be <= TETHYS_SOCKETCAN_IFNAMSZ.
 *
 * @return TETHYS_TR_OK on success, TETHYS_TR_INVAL on length overflow / NULL.
 *
 * @note Defaults to "can0" if never called.
 */
TETHYS_EXPORT tethys_tr_status_t tethys_tr_socketcan_set_ifname(const char *ifname);

/**
 * @brief Read the currently configured interface name.
 *
 * @return Pointer to internal NUL-terminated buffer.
 */
TETHYS_EXPORT const char *tethys_tr_socketcan_ifname(void);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_TRANSPORT_SOCKETCAN_H */
