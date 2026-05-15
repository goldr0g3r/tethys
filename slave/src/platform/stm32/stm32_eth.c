/*
 * src/platform/stm32/stm32_eth.c - W5500 over SPI Ethernet shell for the
 * marine profile (STM32F4/F7 + W5500 module on Adafruit-style breakout).
 *
 * Module: tethys::platform::stm32::eth
 * Profiles: marine.
 * Standards:
 *   - WIZnet W5500 datasheet v1.1.0 (chip register map).
 *   - IEC 61162-450 Edition 2 (maritime UDP Ethernet payload framing).
 *   - ADR-0005 - no dynamic allocation: TX/RX scratch is file-scope.
 *   - .cursor/rules/no-recursion-no-goto.mdc - bounded loops; no goto.
 *
 * Compile-only stub: opens the path for the real driver in the hardware-
 * bring-up PR which will use the W5500 socket API (SOCK_UDP) to drive the
 * tethys_master <-> slave UDP transport on the marine bench.
 *
 * Why W5500 (vs LAN8742 onboard the Nucleo F767ZI)? The onboard LAN8742
 * needs a full LwIP stack; W5500 has hardware TCP/IP offload and exposes a
 * simple socket API. The runbook (docs/runbooks/hardware-setup-stm32.md
 * §3.1) lists both; this PR scaffolds the W5500 path (simpler bring-up).
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifndef TETHYS_ETH_MTU
#  define TETHYS_ETH_MTU (1500U)
#endif

/* Static scratch buffers (ADR-0005). */
static uint8_t  tethys_eth_tx_scratch_[TETHYS_ETH_MTU];
static uint8_t  tethys_eth_rx_scratch_[TETHYS_ETH_MTU];

/* MAC + IP are baked in via cache vars at cross-compile time so the master
 * tool's --transport udp connector knows where to connect. Default reflects
 * the runbook §7.1 example (192.168.1.10:60001). */
#ifndef TETHYS_ETH_DEFAULT_IP_A
#  define TETHYS_ETH_DEFAULT_IP_A (192U)
#endif
#ifndef TETHYS_ETH_DEFAULT_IP_B
#  define TETHYS_ETH_DEFAULT_IP_B (168U)
#endif
#ifndef TETHYS_ETH_DEFAULT_IP_C
#  define TETHYS_ETH_DEFAULT_IP_C (1U)
#endif
#ifndef TETHYS_ETH_DEFAULT_IP_D
#  define TETHYS_ETH_DEFAULT_IP_D (10U)
#endif
#ifndef TETHYS_ETH_DEFAULT_PORT
#  define TETHYS_ETH_DEFAULT_PORT (60001U)
#endif

/* Health counters. */
static volatile uint32_t tethys_eth_tx_packets_;
static volatile uint32_t tethys_eth_rx_packets_;
static volatile uint32_t tethys_eth_tx_dropped_;
static volatile uint32_t tethys_eth_link_up_;

#if defined(TETHYS_PLATFORM_STM32)
/* ---- W5500 SPI shell ----------------------------------------------------- */
/*
 * The W5500 sits behind an SPI master (SPI1 typical: PA5 SCK, PA6 MISO,
 * PA7 MOSI, PB6 CS). Configuration sequence:
 *   1. Pulse RST low for >= 500 us.
 *   2. Wait for PHYCFGR.LNK = 1 (link up).
 *   3. Open socket 0 in UDP mode (Sn_MR = 0x02), set Sn_PORT.
 *   4. Issue OPEN (Sn_CR = 0x01); poll Sn_SR = 0x22 (SOCK_UDP).
 *
 * The bring-up PR fills in real SPI register pokes; this shell exists so the
 * linker has a defined symbol for tethys_stm32_eth_init at cross-compile
 * time.
 */
#endif

/* ---- Public API --------------------------------------------------------- */

void tethys_stm32_eth_init(void);
void tethys_stm32_eth_init(void)
{
    tethys_eth_tx_packets_ = 0U;
    tethys_eth_rx_packets_ = 0U;
    tethys_eth_tx_dropped_ = 0U;
    tethys_eth_link_up_    = 0U;
}

bool tethys_stm32_eth_send_packet(uint8_t const* payload, size_t len);
bool tethys_stm32_eth_send_packet(uint8_t const* payload, size_t len)
{
    if ((payload == NULL) || (len == 0U) || (len > TETHYS_ETH_MTU))
    {
        tethys_eth_tx_dropped_ = tethys_eth_tx_dropped_ + 1U;
        return false;
    }
    /* Compile-only stub: copy into the scratch buffer; real impl writes
     * to W5500 socket TX FIFO via SPI. */
    for (size_t i = 0U; i < len; ++i)
    {
        tethys_eth_tx_scratch_[i] = payload[i];
    }
    tethys_eth_tx_packets_ = tethys_eth_tx_packets_ + 1U;
    return true;
}

size_t tethys_stm32_eth_recv_packet(uint8_t* buf, size_t cap);
size_t tethys_stm32_eth_recv_packet(uint8_t* buf, size_t cap)
{
    if ((buf == NULL) || (cap == 0U))
    {
        return 0U;
    }
    /* Compile-only stub: real impl polls W5500 socket RX size + DMAs into
     * tethys_eth_rx_scratch_, then memcpy into the caller's buffer. */
    (void)tethys_eth_rx_scratch_;
    return 0U;
}

bool tethys_stm32_eth_link_up(void);
bool tethys_stm32_eth_link_up(void)
{
    return tethys_eth_link_up_ != 0U;
}

uint32_t tethys_stm32_eth_tx_packets(void);
uint32_t tethys_stm32_eth_tx_packets(void) { return tethys_eth_tx_packets_; }

uint32_t tethys_stm32_eth_rx_packets(void);
uint32_t tethys_stm32_eth_rx_packets(void) { return tethys_eth_rx_packets_; }

uint32_t tethys_stm32_eth_tx_dropped(void);
uint32_t tethys_stm32_eth_tx_dropped(void) { return tethys_eth_tx_dropped_; }
