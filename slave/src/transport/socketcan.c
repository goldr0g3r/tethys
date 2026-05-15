/*
 * src/transport/socketcan.c - Linux SocketCAN transport.
 *
 * Module: tethys::transport::socketcan
 * Profiles: marine (dev bench); posix-sim (when host is Linux)
 * Standards: ADR-0004; ADR-0005; ADR-0010 row 7; ISO 11898-1:2024
 * Trace: docs/traceability.csv (TETHYS-DES-0032 SocketCAN transport)
 *
 * Wraps a Linux `PF_CAN` `SOCK_RAW` socket bound to an interface (default
 * "can0"). Each XCP CTO/DTO frame is one `struct canfd_frame`. The kernel
 * driver handles arbitration, ACK, error frames, TEC/REC, and bus-off
 * automatically; we only need to observe its error reports.
 *
 * Bus-off detection: bind with `CAN_RAW_ERR_FILTER` set so we receive error
 * frames as if they were data frames; we then translate them into events.
 *
 * On non-Linux (Windows / macOS / bare-metal) the file compiles to a stub
 * whose vtable returns TETHYS_TR_DISCONNECTED for every call. The descriptor
 * is still exported so cross-platform unit tests can verify that the absence
 * of Linux is reported cleanly rather than as a link error.
 *
 * No dynamic allocation (ADR-0005). The interface name is held in a fixed
 * IFNAMSIZ-sized buffer. The recv buffer for canfd_frame is on the stack
 * (72 bytes, well under the 8 KiB ISR-free budget).
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/transport_socketcan.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(__linux__) && !defined(TETHYS_NO_SOCKETCAN)
#  define TETHYS_SOCKETCAN_LINUX 1
#else
#  define TETHYS_SOCKETCAN_LINUX 0
#endif

#if TETHYS_SOCKETCAN_LINUX
#  include <errno.h>
#  include <fcntl.h>
#  include <linux/can.h>
#  include <linux/can/error.h>
#  include <linux/can/raw.h>
#  include <net/if.h>
#  include <poll.h>
#  include <sys/ioctl.h>
#  include <sys/socket.h>
#  include <unistd.h>
#endif

/* ---- File-scope state (all profiles) ---------------------------------- */

static char g_ifname[TETHYS_SOCKETCAN_IFNAMSZ + 1U] = {'c', 'a', 'n', '0', '\0'};

/* ---- Linux implementation (real socket) ------------------------------- */

#if TETHYS_SOCKETCAN_LINUX

/* Socket file descriptor only exists in the Linux branch. The non-Linux
 * stub deliberately does not own a kernel resource, so leaving the variable
 * out keeps `-Wunused-variable` clean on Windows / macOS builds. */
static int g_socket_fd = -1;

static tethys_tr_status_t socketcan_connect(void)
{
    if (g_socket_fd >= 0) {
        return TETHYS_TR_OK;
    }
    int const fd = socket(PF_CAN, SOCK_RAW | SOCK_CLOEXEC, CAN_RAW);
    if (fd < 0) {
        return TETHYS_TR_DISCONNECTED;
    }

    /* Opt into CAN-FD frames. Kernel falls back to classic CAN if the
     * interface doesn't support FD; we honour the kernel's negotiation. */
    int const fd_on = 1;
    /* Return value intentionally ignored: non-FD interfaces simply use the
     * classic 8-byte frame layout, which is still legal under canfd_frame. */
    (void)setsockopt(fd, SOL_CAN_RAW, CAN_RAW_FD_FRAMES, &fd_on, sizeof fd_on);

    /* Subscribe to error frames so we can translate bus-off / arbitration
     * loss into transport events. */
    can_err_mask_t const err_mask = CAN_ERR_BUSOFF | CAN_ERR_BUSERROR | CAN_ERR_RESTARTED;
    (void)setsockopt(fd, SOL_CAN_RAW, CAN_RAW_ERR_FILTER, &err_mask, sizeof err_mask);

    /* Look up the interface index. */
    struct ifreq ifr;
    (void)memset(&ifr, 0, sizeof ifr);
    /* Bounded copy: g_ifname is NUL-terminated and bounded by IFNAMSZ+1. */
    for (size_t i = (size_t)0U;
         (i < (size_t)IFNAMSIZ - (size_t)1U) && (g_ifname[i] != '\0');
         ++i) {
        ifr.ifr_name[i] = g_ifname[i];
    }
    if (ioctl(fd, SIOCGIFINDEX, &ifr) < 0) {
        (void)close(fd);
        return TETHYS_TR_DISCONNECTED;
    }

    struct sockaddr_can addr;
    (void)memset(&addr, 0, sizeof addr);
    addr.can_family = (sa_family_t)AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;
    if (bind(fd, (const struct sockaddr *)&addr, sizeof addr) < 0) {
        (void)close(fd);
        return TETHYS_TR_DISCONNECTED;
    }

    g_socket_fd = fd;
    return TETHYS_TR_OK;
}

static tethys_tr_status_t socketcan_disconnect(void)
{
    if (g_socket_fd < 0) {
        return TETHYS_TR_OK;
    }
    (void)close(g_socket_fd);
    g_socket_fd = -1;
    return TETHYS_TR_OK;
}

static tethys_tr_status_t socketcan_send(const uint8_t *frame, size_t len)
{
    if (g_socket_fd < 0) {
        return TETHYS_TR_DISCONNECTED;
    }
    if (len > (size_t)TETHYS_SOCKETCAN_MTU) {
        return TETHYS_TR_INVAL;
    }
    struct canfd_frame cfd;
    (void)memset(&cfd, 0, sizeof cfd);
    cfd.can_id = (canid_t)0x123U; /* default XCP-on-CAN ID; A2L IF_DATA overrides at Phase 7 */
    cfd.len = (uint8_t)len;
    for (size_t i = (size_t)0U; i < len; ++i) {
        cfd.data[i] = frame[i];
    }
    ssize_t const written = write(g_socket_fd, &cfd, sizeof cfd);
    if (written < 0) {
        return TETHYS_TR_DISCONNECTED;
    }
    if ((size_t)written != sizeof cfd) {
        return TETHYS_TR_FRAME_ERR;
    }
    return TETHYS_TR_OK;
}

static tethys_tr_status_t socketcan_recv(
    uint8_t *buf, size_t buf_len, size_t *out_len, uint32_t timeout_us)
{
    if (g_socket_fd < 0) {
        return TETHYS_TR_DISCONNECTED;
    }

    /* Use poll() so timeout_us is honoured without blocking the slave tick.
     * Convert microseconds to milliseconds for poll(); cap at INT_MAX/2 to
     * avoid overflow. */
    int timeout_ms;
    if (timeout_us == (uint32_t)0U) {
        timeout_ms = 0;
    }
    else if (timeout_us == UINT32_MAX) {
        timeout_ms = -1;
    }
    else {
        timeout_ms = (int)(timeout_us / (uint32_t)1000U);
        if (timeout_ms == 0) {
            timeout_ms = 1; /* round-up so sub-ms timeouts wait at least 1ms */
        }
    }

    struct pollfd pfd = { .fd = g_socket_fd, .events = (short)POLLIN, .revents = (short)0 };
    int const ready = poll(&pfd, (nfds_t)1U, timeout_ms);
    if (ready == 0) {
        return TETHYS_TR_TIMEOUT;
    }
    if (ready < 0) {
        return TETHYS_TR_DISCONNECTED;
    }

    struct canfd_frame cfd;
    ssize_t const got = read(g_socket_fd, &cfd, sizeof cfd);
    if (got < 0) {
        return TETHYS_TR_DISCONNECTED;
    }
    if ((size_t)got < sizeof(struct can_frame)) {
        return TETHYS_TR_FRAME_ERR;
    }

    /* Error frame? Translate to an event and report up. */
    if ((cfd.can_id & CAN_ERR_FLAG) != (canid_t)0U) {
        tethys_tr_event_t ev = {
            .kind = TETHYS_TR_EVT_LOSS,
            .timestamp_us = (uint32_t)0U,
            .count = (uint16_t)1U,
            .reserved = (uint16_t)0U,
        };
        if ((cfd.can_id & CAN_ERR_BUSOFF) != (canid_t)0U) {
            ev.kind = TETHYS_TR_EVT_BUS_OFF;
        }
        else if ((cfd.can_id & CAN_ERR_RESTARTED) != (canid_t)0U) {
            ev.kind = TETHYS_TR_EVT_BUS_RECOVERED;
        }
        tethys_tr_emit_event(&ev);
        return TETHYS_TR_FRAME_ERR;
    }

    size_t const payload_len = (size_t)cfd.len;
    if (payload_len > buf_len) {
        return TETHYS_TR_INVAL;
    }
    for (size_t i = (size_t)0U; i < payload_len; ++i) {
        buf[i] = cfd.data[i];
    }
    *out_len = payload_len;
    return TETHYS_TR_OK;
}

#else  /* TETHYS_SOCKETCAN_LINUX == 0 - non-Linux stub */

static tethys_tr_status_t socketcan_connect(void)
{
    /* Compile-time fence: SocketCAN only exists on Linux. The stub returns a
     * predictable status so cross-platform conformance tests can assert
     * "transport is unavailable on this host" without crashing. */
    return TETHYS_TR_DISCONNECTED;
}

static tethys_tr_status_t socketcan_disconnect(void)
{
    return TETHYS_TR_OK;
}

static tethys_tr_status_t socketcan_send(const uint8_t *frame, size_t len)
{
    (void)frame;
    (void)len;
    return TETHYS_TR_DISCONNECTED;
}

static tethys_tr_status_t socketcan_recv(
    uint8_t *buf, size_t buf_len, size_t *out_len, uint32_t timeout_us)
{
    (void)buf;
    (void)buf_len;
    (void)out_len;
    (void)timeout_us;
    return TETHYS_TR_DISCONNECTED;
}

#endif /* TETHYS_SOCKETCAN_LINUX */

/* ---- Descriptor (single static const instance) ----------------------- */

/* ADR-0010 row 7: SocketCAN budget inherits row 5 (CAN-FD) ≤ 4.7e-11/frame
 * residual; raw loss depends on host scheduling. We declare a small burst-
 * loss tolerance for host-side schedule jitter. */
static const tethys_tr_descriptor_t g_socketcan_descriptor = {
    .id = TETHYS_TR_SOCKETCAN,
    .name = "socketcan",
    .mtu = TETHYS_SOCKETCAN_MTU,
    .supports_reliable = false,
    .supports_ordering = true,
    .max_burst_loss = (uint16_t)4U,
    .typical_latency_us = (uint32_t)500U,
    .typical_loss_ppb = (uint32_t)1000U, /* ~1e-6/frame conservative host-jitter budget */
    .connect = socketcan_connect,
    .disconnect = socketcan_disconnect,
    .send = socketcan_send,
    .recv = socketcan_recv,
};

const tethys_tr_descriptor_t *tethys_tr_socketcan_descriptor(void)
{
    return &g_socketcan_descriptor;
}

tethys_tr_status_t tethys_tr_socketcan_set_ifname(const char *ifname)
{
    if (ifname == NULL) {
        return TETHYS_TR_INVAL;
    }
    /* Bounded length check up to IFNAMSZ. */
    size_t len = (size_t)0U;
    for (size_t i = (size_t)0U; i <= TETHYS_SOCKETCAN_IFNAMSZ; ++i) {
        if (ifname[i] == '\0') {
            len = i;
            break;
        }
        if (i == TETHYS_SOCKETCAN_IFNAMSZ) {
            return TETHYS_TR_INVAL;
        }
    }
    if (len == (size_t)0U) {
        return TETHYS_TR_INVAL;
    }
    for (size_t i = (size_t)0U; i < len; ++i) {
        g_ifname[i] = ifname[i];
    }
    g_ifname[len] = '\0';
    return TETHYS_TR_OK;
}

const char *tethys_tr_socketcan_ifname(void)
{
    return g_ifname;
}
