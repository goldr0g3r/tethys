/*
 * src/profiles/marine/marine_workload.c - placeholder synthetic engine
 * workload for the marine demo.
 *
 * Module: tethys::profiles::marine::workload
 * Profiles: marine.
 * Standards:
 *   - SAE J1939-71 (engine RPM + coolant temp pgn structure - documented
 *     reference for the placeholder signal set; full PGN mapping is Phase
 *     9's job).
 *   - IACS UR E22 Rev.3 §3 (marine SW process anchor).
 *   - ADR-0005 - no dynamic allocation: signals are file-scope volatile.
 *   - .cursor/rules/no-recursion-no-goto.mdc - all loops bounded.
 *
 * Three signals exposed to XCP (via the A2L MEASUREMENT block to be
 * generated in Phase 4):
 *
 *   engine_rpm_x100   - revolutions per minute * 100 (integer, 0..800000)
 *   coolant_temp_x100 - degrees Celsius * 100 (-4000..15000)
 *   injector_duty_x100- duty cycle percent * 100 (0..10000)
 *
 * The `_x100` suffix is per parent plan §3.3 "no float in flight" pattern.
 * The master tool's A2L COMPU_METHOD records the 1/100 scale so the GUI
 * shows engineering units.
 *
 * Real plant-model driven values come in Phase 9 (HIL + MATLAB Simulink);
 * this file emits a deterministic sinusoidal sweep so the demo has
 * something to plot on the Phase 1 simulator without the real plant.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include <stdint.h>

#if defined(TETHYS_PROFILE_MARINE) && (TETHYS_PROFILE_MARINE == 1)

/* ---- Public signals -------------------------------------------------------
 *
 * `volatile` so the optimiser cannot constant-fold the value across calls
 * (XCP UPLOAD will read these mid-loop). The A2L generator (Phase 4) reads
 * the addresses of these globals to compose its MEASUREMENT block.
 */
volatile int32_t tethys_marine_engine_rpm_x100;
volatile int32_t tethys_marine_coolant_temp_x100;
volatile int32_t tethys_marine_injector_duty_x100;

/* Tick counter (incremented per call to tethys_marine_workload_step). */
static uint32_t tethys_marine_workload_tick_;

/* ---- Small fixed-point sine ---------------------------------------------
 *
 * 6-point linear interpolation over a quarter-cycle: input `theta_x256` in
 * [0, 256] -> output sine_x4096 in [-4096, 4096]. Avoids pulling in libm
 * (which doubles the binary). The accuracy is ~3 % - good enough for a
 * demo-grade engine RPM ripple.
 */
static int32_t tethys_marine_sine_x4096_(uint32_t theta_x256)
{
    static int32_t const quarter[7] = {
        0, 1083, 2120, 3070, 3896, 4564, 4096,
    };
    /* Wrap theta into [0, 1024). 1024 = full period. */
    theta_x256 = theta_x256 & 0x3FFU;

    uint32_t const quad   = theta_x256 / 256U;
    uint32_t const offset = theta_x256 % 256U;
    uint32_t const idx    = offset / 43U; /* 6 segments per quadrant */
    uint32_t const frac   = (offset % 43U) * 256U / 43U;
    if (idx >= 6U)
    {
        return 0;
    }

    int32_t const a = quarter[idx];
    int32_t const b = quarter[idx + 1U];
    int32_t       v = a + (((b - a) * (int32_t)frac) / 256);

    /* Reflect / negate per quadrant. */
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
    /* quad == 0: leave as-is */

    return v;
}

void tethys_marine_workload_step(void);
void tethys_marine_workload_step(void)
{
    tethys_marine_workload_tick_ = tethys_marine_workload_tick_ + 1U;

    /* Engine RPM: 800 rpm idle + 1200 rpm sinusoidal ripple at ~0.5 Hz. */
    int32_t const rpm_sin = tethys_marine_sine_x4096_(
        tethys_marine_workload_tick_ * 1U);
    tethys_marine_engine_rpm_x100 =
        80000 + ((rpm_sin * 1200) / 4096);

    /* Coolant temp: 85.00 +/- 0.50 degC at ~0.1 Hz. */
    int32_t const temp_sin = tethys_marine_sine_x4096_(
        tethys_marine_workload_tick_ / 5U);
    tethys_marine_coolant_temp_x100 =
        8500 + ((temp_sin * 50) / 4096);

    /* Injector duty: 35.00 % +/- 5 % at ~1 Hz. */
    int32_t const duty_sin = tethys_marine_sine_x4096_(
        tethys_marine_workload_tick_ * 2U);
    tethys_marine_injector_duty_x100 =
        3500 + ((duty_sin * 500) / 4096);
}

#endif /* TETHYS_PROFILE_MARINE */
