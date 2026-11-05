// Power8GDI ignition arbitration in the rusEFI simulator.
//
// rusEFI calls custom_board_getCylinderIgnitionTrim right after it computes
// the corrected advance of the cycle. On cylinder 0 this glue runs
// IgnitionArbiter on the same inputs.
//
// Modes (environment):
//   default         SHADOW: correctionsApplyMask covers every owner, which is
//                   rusEFI's semantics (engine2.cpp applies knock and limiter
//                   retard in all modes). The arbiter angle must equal rusEFI's;
//                   the stock trim is returned, rusEFI behaviour is unchanged.
//   P8_SIM_APPLY=1  APPLY: Power8GDI default config (strategy offsets for the
//                   table only, protective retard for every owner). The trim
//                   hook returns stock trim + (arbiter - rusEFI), so the arbiter
//                   drives the spark angle. Checked on the next cylinder against
//                   rusEFI's final timingAdvance[0].
//
// Scenarios (P8_SIM_SCENARIO):
//   knock   knock events through rusEFI's own knock controller.
//   owners  knock + soft limiter retard, and the engine is walked through the
//           angle owners: table, idle, overrun (coasting), anti-lag, launch.
//
// Owner mapping follows the order in rusEFI getRunningAdvance(): cranking,
// then launch (returns early), then the idle/coasting table (replaces the
// angle, ALS included), then the ALS correction. Every owner requests rusEFI's
// wrapped base advance with no ramp, so only the corrections are compared.
// Not mapped: flat-shift torque reduction (not enabled in any scenario).

#include "pch.h"

#include "board_overrides.h"
#include "idle_thread.h"
#include "ignition_arbiter.h"
#include "intervention_accumulator.h"

#include <cmath>
#include <cstdlib>
#include <cstring>

using namespace power8gdi;

namespace {

enum class Scenario { None, Knock, Owners };

const char* env(const char* name) {
    const char* v = getenv(name);
    return v != nullptr ? v : "";
}

Scenario scenario() {
    static const Scenario s = [] {
        const char* v = env("P8_SIM_SCENARIO");
        if (strcmp(v, "knock") == 0) return Scenario::Knock;
        if (strcmp(v, "owners") == 0) return Scenario::Owners;
        return Scenario::None;
    }();
    return s;
}

bool applyMode() {
    static const bool apply = strcmp(env("P8_SIM_APPLY"), "1") == 0;
    return apply;
}

IgnitionConfig makeConfig() {
    IgnitionConfig c;  // Power8GDI default: strategy offsets for the table only
    if (!applyMode()) {
        c.correctionsApplyMask = 0x3F;
    }
    c.minAdvance = -180.0f;
    c.maxAdvance = 180.0f;
    return c;
}

IgnitionArbiter arbiter(makeConfig());
InterventionAccumulator acc;

constexpr float kTolerance = 0.1f;  // scaled channels, 0.02 deg resolution each

struct Stats {
    uint32_t cycles = 0;
    uint32_t mismatches = 0;          // arbiter angle/correction not as expected
    float maxAbsDelta = 0.0f;         // shadow: |arbiter - rusEFI|
    uint32_t ownerCycles[kAngleSourceCount] = {};
    uint32_t knockCycles = 0;
    unsigned knockOwnerMask = 0;      // owners seen with knock retard > 0
    unsigned limiterOwnerMask = 0;    // owners seen with limiter retard > 0
    float maxKnockRetard = 0.0f;
    uint32_t differentCycles = 0;     // apply: arbiter != rusEFI by more than tolerance
    uint32_t appliedChecks = 0;       // apply: final angle checked
    uint32_t applyErrors = 0;         // apply: final angle != arbiter angle
    float maxApplyError = 0.0f;
    efitick_t lastReportNt = 0;
} stats;

// Per-cycle result shared between the cylinder calls of one cycle.
struct CycleResult {
    bool valid = false;
    float delta = 0.0f;         // arbiter - rusEFI corrected advance
    float expectedFinal0 = 0.0f;
} cycle;

float unwrap(float angle) {
    return angle > 360.0f ? angle - 720.0f : angle;
}

float angleDistance(float a, float b) {
    float d = std::fmod(std::fabs(a - b), 720.0f);
    return d > 360.0f ? 720.0f - d : d;
}

AngleSource currentOwner() {
    if (engine->rpmCalculator.isCranking()) {
        return AngleSource::Cranking;
    }
#if EFI_LAUNCH_CONTROL
    if (engineConfiguration->launchControlEnabled && engineConfiguration->enableLaunchRetard) {
        const auto& lc = engine->launchController;
        const float rpm = Sensor::getOrZero(SensorType::Rpm);
        const int start = engineConfiguration->launchRpm - engineConfiguration->launchRpmWindow;
        if (lc.isLaunchCondition || (lc.isPreLaunchCondition && rpm >= start)) {
            return AngleSource::LaunchControl;
        }
    }
#endif
#if EFI_IDLE_CONTROL
    if (engineConfiguration->useSeparateAdvanceForIdle) {
        auto& idle = engine->module<IdleController>();
        if (idle->isIdlingOrTaper()) {
            return AngleSource::Idle;
        }
        if (idle->isCoastingAdvance()) {
            return AngleSource::Overrun;
        }
    }
#endif
#if EFI_ANTILAG_SYSTEM
    if (engine->antilagController.isAntilagCondition) {
        return AngleSource::AntiLag;
    }
#endif
    return AngleSource::Table;
}

// ---- scenarios (driven after the comparison of the cycle) ----

void setThrottle(float percent) {
    Sensor::setMockValue(SensorType::Tps1, percent);
    Sensor::setMockValue(SensorType::DriverThrottleIntent, percent);
}

void setupKnock() {
    engineConfiguration->knockRetardAggression = 10;
    engineConfiguration->knockSuppressMinTps = 0;
    for (auto& row : config->maxKnockRetardTable) {
        for (auto& cell : row) {
            cell = 8;
        }
    }
}

void injectKnock(uint32_t n) {
    if (n >= 10 && n % 5 == 0) {
        engine->module<KnockController>()->onKnockSenseCompleted(0, 1000.0f, getTimeNowNt());
    }
}

void setupLimiter() {
    // Simulator runs at 1200 rpm: soft window 1050..1250 gives about 3 deg retard.
    engineConfiguration->useCltBasedRpmLimit = false;
    engineConfiguration->rpmHardLimit = 1250;
    engineConfiguration->rpmHardLimitHyst = 200;
    engineConfiguration->rpmSoftLimitTimingRetard = 4;
}

enum class Phase { Table, Idle, Overrun, AntiLag, Launch, Done };

Phase phaseFor(uint32_t n) {
    if (n < 300) return Phase::Table;
    if (n < 600) return Phase::Idle;
    if (n < 900) return Phase::Overrun;
    if (n < 1200) return Phase::AntiLag;
    if (n < 1500) return Phase::Launch;
    return Phase::Done;
}

void enterPhase(Phase p) {
    engineConfiguration->useSeparateAdvanceForIdle = false;
    engineConfiguration->useIdleAdvanceWhileCoasting = false;
    engineConfiguration->antiLagEnabled = false;
    engineConfiguration->launchControlEnabled = false;
    setThrottle(50);
    switch (p) {
    case Phase::Idle:
    case Phase::Overrun:
        engineConfiguration->useSeparateAdvanceForIdle = true;
        engineConfiguration->useIdleAdvanceWhileCoasting = true;
        // Idle target at engine speed -> idling; far below it -> coasting.
        for (auto& rpm : config->cltIdleRpm) {
            rpm = p == Phase::Idle ? 1200 : 700;
        }
        setThrottle(0);
        break;
    case Phase::AntiLag:
        engineConfiguration->antiLagEnabled = true;
        engineConfiguration->antiLagActivationMode = ALWAYS_ON_ANTILAG;
        engineConfiguration->ALSMinRPM = 500;
        engineConfiguration->ALSMaxRPM = 6000;
        engineConfiguration->ALSMinCLT = -40;
        engineConfiguration->ALSMaxCLT = 120;
        engineConfiguration->ALSMaxTPS = 100;
        engineConfiguration->ALSMaxDuration = 0;
        break;
    case Phase::Launch:
        engineConfiguration->launchControlEnabled = true;
        engineConfiguration->enableLaunchRetard = true;
        engineConfiguration->launchTimingRetard = 5;
        engineConfiguration->launchActivationMode = ALWAYS_ACTIVE_LAUNCH;
        engineConfiguration->launchSpeedThreshold = 0;
        engineConfiguration->launchTpsThreshold = 10;
        engineConfiguration->launchRpm = 1000;
        engineConfiguration->launchRpmThreshold = 0;
        break;
    default:
        break;
    }
}

void driveScenario(uint32_t n) {
    static bool configured = false;
    if (scenario() == Scenario::None) {
        return;
    }
    if (!configured) {
        configured = true;
        setupKnock();
        if (scenario() == Scenario::Owners) {
            setupLimiter();
            // Default crank-to-idle taper outlasts the run; idle needs it finished.
            for (auto& revs : config->afterCrankingIACtaperDuration) {
                revs = 10;
            }
        }
        printf("P8SHADOW scenario=%s apply=%d\n", env("P8_SIM_SCENARIO"), applyMode() ? 1 : 0);
    }
    injectKnock(n);
    if (scenario() == Scenario::Owners) {
        static Phase current = Phase::Done;
        const Phase p = phaseFor(n);
        if (p != current || n == 0) {
            current = p;
            enterPhase(p);
        }
    }
}

// ---- comparison ----

void report(const IgnitionResult& r, float base, float rusefi) {
    const efitick_t nowNt = getTimeNowNt();
    if (nowNt - stats.lastReportNt < NT_PER_SECOND) {
        return;
    }
    stats.lastReportNt = nowNt;
    // efiPrintf is not echoed to stdout after simulator init.
    printf("P8SHADOW cycles=%lu mismatches=%lu maxDelta=%.3f owner=%d base=%.2f rusefi=%.2f p8=%.2f corr=%.2f "
           "knockCycles=%lu maxKnock=%.2f knockOwners=0x%x limiterOwners=0x%x "
           "differentCycles=%lu appliedChecks=%lu applyErrors=%lu maxApplyError=%.3f "
           "owners[T,O,I,A,L,C]=%lu,%lu,%lu,%lu,%lu,%lu\n",
           (unsigned long)stats.cycles, (unsigned long)stats.mismatches, stats.maxAbsDelta,
           (int)r.source, base, rusefi, r.advanceDeg, r.correctionDeg,
           (unsigned long)stats.knockCycles, stats.maxKnockRetard, stats.knockOwnerMask,
           stats.limiterOwnerMask,
           (unsigned long)stats.differentCycles, (unsigned long)stats.appliedChecks,
           (unsigned long)stats.applyErrors, stats.maxApplyError,
           (unsigned long)stats.ownerCycles[0], (unsigned long)stats.ownerCycles[1],
           (unsigned long)stats.ownerCycles[2], (unsigned long)stats.ownerCycles[3],
           (unsigned long)stats.ownerCycles[4], (unsigned long)stats.ownerCycles[5]);
}

void runCycle(float stockTrim0) {
    cycle.valid = false;
    if (engineConfiguration->timingMode != TM_DYNAMIC) {
        return;
    }
    const float base = unwrap(engine->ignitionState.baseIgnitionAdvance);
    const float rusefi = unwrap(engine->ignitionState.correctedIgnitionAdvance);
    const float knockRetard = engine->module<KnockController>()->getKnockRetard();
    const float limiterRetard = getLimpManager()->getLimitingTimingRetard();

    acc.reset();
    acc.addIgnition(IgnitionSource::Knock, -knockRetard);
    acc.addIgnition(IgnitionSource::RpmLimiter, -limiterRetard);

    IgnitionInput in;
    in.tableAdvanceDeg = base;
    const AngleSource owner = currentOwner();
    if (owner != AngleSource::Table) {
        in.request[static_cast<unsigned>(owner)] = {true, base, 0.0f};
    }
    const IgnitionResult r = arbiter.update(in, acc, 0.0f);
    const unsigned ownerBit = 1u << static_cast<unsigned>(r.source);

    // Expected correction: everything in shadow mode; in apply mode the
    // strategy (limiter) retard only for the table, knock for every owner.
    const bool allCorrections = !applyMode() || r.source == AngleSource::Table;
    const float expected = allCorrections ? -knockRetard - limiterRetard : -knockRetard;
    const float delta = r.advanceDeg - rusefi;

    stats.cycles++;
    stats.ownerCycles[static_cast<unsigned>(r.source)]++;
    if (r.fault || std::fabs(r.correctionDeg - expected) > 1e-3f ||
        std::fabs(r.advanceDeg - (base + expected)) > kTolerance ||
        (!applyMode() && std::fabs(delta) > kTolerance)) {
        stats.mismatches++;
    }
    if (!applyMode() && std::fabs(delta) > stats.maxAbsDelta) {
        stats.maxAbsDelta = std::fabs(delta);
    }
    if (applyMode() && std::fabs(delta) > kTolerance) {
        stats.differentCycles++;
    }
    if (knockRetard > 0.0f) {
        stats.knockCycles++;
        stats.knockOwnerMask |= ownerBit;
        if (knockRetard > stats.maxKnockRetard) {
            stats.maxKnockRetard = knockRetard;
        }
    }
    if (limiterRetard > 0.0f) {
        stats.limiterOwnerMask |= ownerBit;
    }

    if (applyMode() && !r.fault) {
        cycle.valid = true;
        cycle.delta = delta;
        cycle.expectedFinal0 = r.advanceDeg + stockTrim0 +
                               engine->ignitionState.getSparkHardwareLatencyCorrection();
    }

    report(r, base, rusefi);
    if (getenv("P8_SIM_DEBUG") != nullptr && stats.cycles % 100 == 50) {
        auto tps = Sensor::get(SensorType::DriverThrottleIntent);
        printf("P8DBG n=%lu phase=%d tpsValid=%d tps=%.1f rpm=%.0f sepIdle=%d\n", (unsigned long)stats.cycles,
               (int)engine->module<IdleController>()->getCurrentPhase(), tps.Valid ? 1 : 0, tps.Value,
               Sensor::getOrZero(SensorType::Rpm), engineConfiguration->useSeparateAdvanceForIdle ? 1 : 0);
    }
    // Scenario changes act from the next cycle on: this cycle is already computed.
    driveScenario(stats.cycles);
}

angle_t ignitionTrimHook(size_t cylinderNumber, float rpm, float ignitionLoad) {
    const float stock = IgnitionState::getInterpolatedIgnitionTrim(cylinderNumber, rpm, ignitionLoad);
    if (cylinderNumber == 0) {
        runCycle(stock);
    } else if (cylinderNumber == 1 && cycle.valid) {
        // rusEFI stored cylinder 0's final angle right after the previous call.
        const float err = angleDistance(engine->engineState.timingAdvance[0], cycle.expectedFinal0);
        stats.appliedChecks++;
        if (err > kTolerance) {
            stats.applyErrors++;
        }
        if (err > stats.maxApplyError) {
            stats.maxApplyError = err;
        }
    }
    return cycle.valid ? stock + cycle.delta : stock;
}

// The simulator's setup_custom_board_overrides() is fixed upstream, so the
// hook is installed by a static initializer. The optional holds a function
// pointer and is constant-initialized, so the order of static init is safe.
struct InstallHook {
    InstallHook() { custom_board_getCylinderIgnitionTrim = ignitionTrimHook; }
} installHook;

} // namespace
