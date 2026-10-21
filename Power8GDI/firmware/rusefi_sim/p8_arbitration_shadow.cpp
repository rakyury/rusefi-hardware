// Power8GDI arbitration in the rusEFI simulator, SHADOW mode.
//
// Runs IgnitionArbiter on the same inputs rusEFI uses in the same engine
// cycle and compares its angle with rusEFI's corrected advance. rusEFI's
// behaviour is not changed: the per-cylinder trim hook returns the stock trim.
//
// Owner mapping (rusEFI already folds the owner angle into baseAdvance):
//   cranking -> Cranking, anti-lag condition -> AntiLag,
//   launch spark retard condition -> LaunchControl, idle/taper -> Idle,
//   otherwise Table. Every owner requests baseAdvance with no ramp.
// Corrections: knock retard (protective) and limp/soft-limiter retard.
// correctionsApplyMask covers every owner, which is rusEFI's semantics
// (engine2.cpp applies both to the wrapped advance in all modes), so the
// expected difference is the scaled-channel quantization only.

#include "pch.h"

#include "board_overrides.h"
#include "idle_thread.h"
#include "ignition_arbiter.h"
#include "intervention_accumulator.h"

#include <cmath>

using namespace power8gdi;

namespace {

IgnitionConfig shadowConfig() {
    IgnitionConfig c;
    c.correctionsApplyMask = 0x3F;
    c.minAdvance = -180.0f;
    c.maxAdvance = 180.0f;
    return c;
}

IgnitionArbiter arbiter(shadowConfig());
InterventionAccumulator acc;

struct ShadowStats {
    uint32_t cycles = 0;
    uint32_t mismatches = 0;
    float maxAbsDelta = 0.0f;
    uint32_t ownerCycles[kAngleSourceCount] = {};
    uint32_t knockCycles = 0;      // cycles with knock retard > 0
    unsigned knockOwnerMask = 0;   // owners seen while knock retard > 0
    float maxKnockRetard = 0.0f;
    efitick_t lastReportNt = 0;
} stats;

constexpr float kTolerance = 0.1f;  // scaled channels, 0.02 deg resolution each

float unwrap(float angle) {
    return angle > 360.0f ? angle - 720.0f : angle;
}

AngleSource currentOwner() {
    if (engine->rpmCalculator.isCranking()) {
        return AngleSource::Cranking;
    }
#if EFI_ANTILAG_SYSTEM
    if (engine->antilagController.isAntilagCondition) {
        return AngleSource::AntiLag;
    }
#endif
#if EFI_LAUNCH_CONTROL
    if (engine->launchController.isLaunchSparkRpmRetardCondition()) {
        return AngleSource::LaunchControl;
    }
#endif
#if EFI_IDLE_CONTROL
    if (engine->module<IdleController>()->isIdlingOrTaper()) {
        return AngleSource::Idle;
    }
#endif
    return AngleSource::Table;
}

// Optional test scenario, P8_SIM_SCENARIO=knock: knock events on cylinder 1
// through rusEFI's own knock path, so knock retard is non-zero and the
// comparison covers it. Cycles 10..49 (cranking) and 600..999 (running). Without the variable nothing is injected.
bool knockScenario() {
    static const bool enabled = [] {
        const char* s = getenv("P8_SIM_SCENARIO");
        return s != nullptr && strcmp(s, "knock") == 0;
    }();
    return enabled;
}

void injectKnock(uint32_t cycle) {
    static bool configured = false;
    if (!configured) {
        configured = true;
        engineConfiguration->knockRetardAggression = 10;
        engineConfiguration->knockSuppressMinTps = 0;
        for (auto& row : config->maxKnockRetardTable) {
            for (auto& cell : row) {
                cell = 8;
            }
        }
        printf("P8SHADOW scenario=knock\n");
    }
    const bool window = (cycle >= 10 && cycle < 50) || (cycle >= 600 && cycle < 1000);
    if (window && cycle % 5 == 0) {
        engine->module<KnockController>()->onKnockSenseCompleted(0, 1000.0f, getTimeNowNt());
    }
}

void runShadow() {
    if (engineConfiguration->timingMode != TM_DYNAMIC) {
        return;
    }
    const float base = unwrap(engine->ignitionState.baseIgnitionAdvance);
    const float rusefi = unwrap(engine->ignitionState.correctedIgnitionAdvance);

    acc.reset();
    const float knockRetard = engine->module<KnockController>()->getKnockRetard();
    acc.addIgnition(IgnitionSource::Knock, -knockRetard);
    acc.addIgnition(IgnitionSource::RpmLimiter, -getLimpManager()->getLimitingTimingRetard());

    IgnitionInput in;
    in.tableAdvanceDeg = base;
    const AngleSource owner = currentOwner();
    if (owner != AngleSource::Table) {
        in.request[static_cast<unsigned>(owner)] = {true, base, 0.0f};
    }
    const IgnitionResult r = arbiter.update(in, acc, 0.0f);

    const float delta = r.advanceDeg - rusefi;
    stats.cycles++;
    stats.ownerCycles[static_cast<unsigned>(r.source)]++;
    if (r.fault || std::fabs(delta) > kTolerance) {
        stats.mismatches++;
    }
    if (std::fabs(delta) > stats.maxAbsDelta) {
        stats.maxAbsDelta = std::fabs(delta);
    }
    if (knockRetard > 0.0f) {
        stats.knockCycles++;
        stats.knockOwnerMask |= 1u << static_cast<unsigned>(r.source);
        if (knockRetard > stats.maxKnockRetard) {
            stats.maxKnockRetard = knockRetard;
        }
    }

    // Inject only after the comparison: this cycle's rusEFI angle was computed
    // before the injected event.
    if (knockScenario()) {
        injectKnock(stats.cycles);
    }

    const efitick_t nowNt = getTimeNowNt();
    if (nowNt - stats.lastReportNt >= NT_PER_SECOND) {
        stats.lastReportNt = nowNt;
        // efiPrintf is not echoed to stdout after simulator init.
        printf("P8SHADOW cycles=%lu mismatches=%lu maxDelta=%.3f owner=%d base=%.2f rusefi=%.2f p8=%.2f corr=%.2f "
                  "knockCycles=%lu maxKnock=%.2f knockOwners=0x%x owners[T,O,I,A,L,C]=%lu,%lu,%lu,%lu,%lu,%lu\n",
                  (unsigned long)stats.cycles, (unsigned long)stats.mismatches, stats.maxAbsDelta,
                  (int)r.source, base, rusefi, r.advanceDeg, r.correctionDeg,
                  (unsigned long)stats.knockCycles, stats.maxKnockRetard, stats.knockOwnerMask,
                  (unsigned long)stats.ownerCycles[0], (unsigned long)stats.ownerCycles[1],
                  (unsigned long)stats.ownerCycles[2], (unsigned long)stats.ownerCycles[3],
                  (unsigned long)stats.ownerCycles[4], (unsigned long)stats.ownerCycles[5]);
    }
}

angle_t shadowIgnitionTrim(size_t cylinderNumber, float rpm, float ignitionLoad) {
    // Called right after correctedIgnitionAdvance is computed for this cycle.
    if (cylinderNumber == 0) {
        runShadow();
    }
    return IgnitionState::getInterpolatedIgnitionTrim(cylinderNumber, rpm, ignitionLoad);
}

// The simulator's setup_custom_board_overrides() is fixed upstream, so the
// hook is installed by a static initializer. The optional holds a function
// pointer and is constant-initialized, so the order of static init is safe.
struct InstallHook {
    InstallHook() { custom_board_getCylinderIgnitionTrim = shadowIgnitionTrim; }
} installHook;

} // namespace
