/*
 * src/profiles/space/space_workload.c - placeholder satellite reaction-
 * wheel torque calibration workload.
 *
 * Module: tethys::profiles::space::workload
 * Profiles: space.
 * Standards:
 *   - ECSS-E-ST-60-10C (control performance verification - documented
 *     reference for the placeholder signal set; full closed-loop model
 *     is Phase 9's job).
 *   - .cursor/rules/space-profile-invariants.mdc - flight-mode default off;
 *     DAQ only via authenticated service-mode unlock.
 *   - ADR-0005 - no dynamic allocation: signals are file-scope volatile.
 *
 * Three signals exposed to XCP (gated by service-mode unlock per ADR-0006):
 *
 *   wheel_torque_x100      - reaction-wheel commanded torque * 100, milliNm
 *                            (signed int32; -50000 .. +50000)
 *   wheel_speed_x100       - reaction-wheel speed * 100, RPM
 *                            (signed int32; -1000000 .. +1000000)
 *   housekeeping_temp_x100 - panel temperature * 100, degC
 *                            (signed int32; -5500 .. +12500)
 *
 * The `_x100` suffix matches parent plan §3.3 (no float in flight).
 * Real plant comes in Phase 9 (HIL + Simulink).
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include <stdint.h>

#if defined(TETHYS_PROFILE_SPACE) && (TETHYS_PROFILE_SPACE == 1)

volatile int32_t tethys_space_wheel_torque_x100;
volatile int32_t tethys_space_wheel_speed_x100;
volatile int32_t tethys_space_housekeeping_temp_x100;

static uint32_t tethys_space_workload_tick_;

/* Same fixed-point sine as marine_workload.c; duplicated rather than
 * cross-profile shared to keep profile-source isolation per ADR-0002. */
static int32_t tethys_space_sine_x4096_(uint32_t theta_x256)
{
    static int32_t const quarter[7] = {
        0, 1083, 2120, 3070, 3896, 4564, 4096,
    };
    theta_x256 = theta_x256 & 0x3FFU;

    uint32_t const quad   = theta_x256 / 256U;
    uint32_t const offset = theta_x256 % 256U;
    uint32_t const idx    = offset / 43U;
    uint32_t const frac   = (offset % 43U) * 256U / 43U;
    if (idx >= 6U)
    {
        return 0;
    }

    int32_t const a = quarter[idx];
    int32_t const b = quarter[idx + 1U];
    int32_t       v = a + (((b - a) * (int32_t)frac) / 256);

    if (quad == 1U)
    {
        v = quarter[6] - v;
    }
    else if (quad == 2U)
    {
        v = -v;
    }
    else if (quad == 3U)
    {
        v = -(quarter[6] - v);
    }
    return v;
}

void tethys_space_workload_step(void);
void tethys_space_workload_step(void)
{
    tethys_space_workload_tick_ = tethys_space_workload_tick_ + 1U;

    /* Reaction-wheel commanded torque: 0 +/- 10 mNm at ~0.2 Hz. */
    int32_t const torque_sin = tethys_space_sine_x4096_(
        tethys_space_workload_tick_ / 2U);
    tethys_space_wheel_torque_x100 = (torque_sin * 1000) / 4096;

    /* Reaction-wheel speed: integrated torque (approximate; just for
     * demo). 1000 +/- 100 RPM at ~0.05 Hz. */
    int32_t const speed_sin = tethys_space_sine_x4096_(
        tethys_space_workload_tick_ / 10U);
    tethys_space_wheel_speed_x100 = 100000 + ((speed_sin * 10000) / 4096);

    /* Housekeeping panel temp: -20.00 +/- 5.00 degC at ~0.01 Hz (orbit
     * day/night cycle proxy). */
    int32_t const temp_sin = tethys_space_sine_x4096_(
        tethys_space_workload_tick_ / 50U);
    tethys_space_housekeeping_temp_x100 = -2000 + ((temp_sin * 500) / 4096);
}

#endif /* TETHYS_PROFILE_SPACE */
