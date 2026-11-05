// Power8GDI fuel / lambda / cylinder-cut arbitration in the rusEFI simulator.
//
// rusEFI calls custom_board_getCylinderFuelTrim once per cylinder in
// EngineState::periodicFastCallback (engine2.cpp) and multiplies the result
// with the untrimmed mass, the bank trim and the knock fuel trim. Setting the
// hook replaces rusEFI's own per-cylinder trim table lookup, so this glue
// computes that stock trim itself (same interpolate3d call as fuel_math.cpp).
//
// On cylinder 0 the glue runs FuelArbiter on the inputs of the cycle:
//   - knock fuel trim (protective enrichment)          -> multiplyFuel(Knock)
//   - rusEFI LimpManager fuel cut, by ClearReason       -> cutFuel / 100 % cylinder cut
//   - lambda target (fuelComputer.targetLambda)         -> base lambda
//
// Modes (environment):
//   default         SHADOW: no Power8GDI strategy requests. Arbiter per-cylinder
//                   multipliers must equal rusEFI's (stock trim x knock trim),
//                   the arbiter must cut every cylinder exactly when rusEFI cuts
//                   injection, and the lambda target must match. Stock trim is
//                   returned, rusEFI behaviour is unchanged.
//   P8_SIM_APPLY=1  APPLY: additionally a progressive soft rev-limit CYLINDER
//                   cut (Power8GDI strategy, fuel only, 0..100 % across the
//                   rusEFI soft window). The hook returns arbiter multiplier /
//                   knock trim, so the arbiter drives injectionMass[]. Checked on
//                   the next cycle: cut cylinders have mass 0, the others the
//                   arbiter ratio.
//
// Scenario P8_SIM_SCENARIO=fuelcut walks five phases of 300 cycles:
//   knock (fuel trim), soft window (limit 1300, hysteresis 200: 50 % at the
//   simulator's 1200 rpm), hard limit fuel cut (limit 1100), launch fuel cut,
//   table.
//
// Not covered: the lambda target and the closed-loop freeze are computed and
// reported, not applied (rusEFI has no hook for them); spark-cut masks are not
// applied. Cut by zero mass relies on getInjectionDuration(0) == 0 and on no
// wall-fuel compensation; the HPFP feed-forward reads injectionMass[0] only.

#include "pch.h"

#include "board_overrides.h"
#include "firing_order.h"
#include "fuel_arbiter.h"
#include "intervention_accumulator.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>

using namespace power8gdi;

// rusEFI global (engine_configuration.cpp), not declared in a header.
extern bool hasRememberedConfiguration;

namespace {

const char* env(const char* name) {
    const char* v = getenv(name);
    return v != nullptr ? v : "";
}

bool applyMode() {
    static const bool apply = strcmp(env("P8_SIM_APPLY"), "1") == 0;
    return apply;
}

bool fuelScenario() {
    static const bool on = strcmp(env("P8_SIM_SCENARIO"), "fuelcut") == 0;
    return on;
}

enum class Phase { Knock, SoftWindow, HardCut, Launch, Table, Done };

Phase phaseFor(uint32_t n) {
    if (n < 300) return Phase::Knock;
    if (n < 600) return Phase::SoftWindow;
    if (n < 900) return Phase::HardCut;
    if (n < 1200) return Phase::Launch;
    if (n < 1500) return Phase::Table;
    return Phase::Done;
}

struct Stats {
    uint32_t cycles = 0;
    uint32_t mismatches = 0;       // shadow: arbiter != rusEFI (trim, cut state, lambda)
    uint32_t massChecks = 0;
    uint32_t massErrors = 0;       // injectionMass[] != arbiter result
    uint32_t knockFuelCycles = 0;  // knock fuel trim > 1
    float maxKnockTrim = 1.0f;
    uint32_t rusefiCutCycles = 0;
    unsigned cutReasons = 0;       // bit = rusEFI ClearReason
    uint32_t allCutCycles = 0;     // arbiter cut every cylinder
    uint32_t zeroMassCycles = 0;   // apply: every cylinder had mass 0
    uint32_t softCycles = 0;       // apply: soft cylinder cut active
    uint32_t softCuts = 0;         // cut cylinder-events in soft cycles
    float softPercentSum = 0.0f;   // sum of requested percent in soft cycles
    uint32_t perCylinderSoft[kMaxCylinders] = {};
    uint32_t freezeCycles = 0;
    efitick_t lastReportNt = 0;
} stats;

// What this glue returned in the previous cycle, checked against rusEFI's
// injectionMass[] at the start of the next one.
struct Previous {
    bool valid = false;
    unsigned n = 0;
    float returned[kMaxCylinders] = {};
    float bankTrim[kMaxCylinders] = {};
    float knock = 1.0f;
} prev;

float cycleReturn[kMaxCylinders] = {};
FuelResult lastResult;

FuelConfig makeConfig() {
    FuelConfig c;
    c.cylinderCount = static_cast<uint8_t>(std::min<size_t>(engineConfiguration->cylindersCount, kMaxCylinders));
    for (size_t i = 0; i < c.cylinderCount; i++) {
        c.firingOrder[i] = static_cast<uint8_t>(getCylinderNumberAtIndex(i));
    }
    return c;
}

// P8_SIM_CYLINDERS=6 runs the simulator as the Power6GDI target (firing order
// 1-5-3-6-2-4) instead of its default four-cylinder engine, through rusEFI's
// normal configuration-change path. rusEFI refuses that path until its
// configuration is remembered at the end of init, so the change waits for it.
void applyCylinderCount() {
    static bool done = false;
    if (done || strcmp(env("P8_SIM_CYLINDERS"), "6") != 0 || !hasRememberedConfiguration) {
        return;
    }
    done = true;
    engineConfiguration->cylindersCount = 6;
    engineConfiguration->firingOrder = FO_1_5_3_6_2_4;
    incrementGlobalConfigurationVersion("p8 six cylinders");
}

// Rebuilt whenever rusEFI's cylinder count or firing order changes.
FuelArbiter& arbiter() {
    static FuelArbiter instance(makeConfig());
    static unsigned builtFor = 0;
    const unsigned key = engineConfiguration->cylindersCount * 256u + engineConfiguration->firingOrder;
    if (key != builtFor) {
        instance = FuelArbiter(makeConfig());
        builtFor = key;
        prev.valid = false;  // the previous cycle had another cylinder layout
    }
    return instance;
}

InterventionAccumulator acc;

float stockTrim(size_t cylinder, float rpm, float fuelLoad) {
    const float trimPercent = interpolate3d(config->fuelTrims[cylinder].table, config->fuelTrimLoadBins, fuelLoad,
                                            config->fuelTrimRpmBins, rpm);
    return (100 + trimPercent) / 100;
}

void mapRusefiCut(ClearReason reason) {
    switch (reason) {
    case ClearReason::HardLimit: acc.cutFuel(FuelCutSource::HardRpmLimit); break;
    case ClearReason::BoostCut: acc.cutFuel(FuelCutSource::BoostLimit); break;
    case ClearReason::OilPressure: acc.cutFuel(FuelCutSource::OilPressure); break;
    case ClearReason::LambdaProtection: acc.cutFuel(FuelCutSource::LambdaGuard); break;
    case ClearReason::StopRequested: acc.cutFuel(FuelCutSource::StopSwitch); break;
    case ClearReason::EtbProblem: acc.cutFuel(FuelCutSource::DbwSafety); break;
    case ClearReason::GdiComms:
    case ClearReason::GdiLimits:
    case ClearReason::GdiPumpLimit: acc.cutFuel(FuelCutSource::GdiDriverFault); break;
    case ClearReason::LaunchCut:
        acc.requestCylinderCut(CylinderCutSource::LaunchControl, 100.0f, CutMode::Fuel);
        break;
    case ClearReason::InjectorDutyCycle:
        acc.requestCylinderCut(CylinderCutSource::InjectorDuty, 100.0f, CutMode::Fuel);
        break;
    default: acc.cutFuel(FuelCutSource::External); break;
    }
}

void setThrottle(float percent) {
    Sensor::setMockValue(SensorType::Tps1, percent);
    Sensor::setMockValue(SensorType::DriverThrottleIntent, percent);
}

void enterPhase(Phase p) {
    engineConfiguration->launchControlEnabled = false;
    engineConfiguration->cutFuelOnHardLimit = true;
    engineConfiguration->cutSparkOnHardLimit = false;
    engineConfiguration->useCltBasedRpmLimit = false;
    engineConfiguration->rpmHardLimit = 7000;
    engineConfiguration->rpmHardLimitHyst = 50;
    setThrottle(50);
    switch (p) {
    case Phase::SoftWindow:
        engineConfiguration->rpmHardLimit = 1300;
        engineConfiguration->rpmHardLimitHyst = 200;
        break;
    case Phase::HardCut:
        engineConfiguration->rpmHardLimit = 1100;
        break;
    case Phase::Launch:
        engineConfiguration->launchControlEnabled = true;
        engineConfiguration->launchFuelCutEnable = true;
        engineConfiguration->launchSparkCutEnable = false;
        engineConfiguration->enableLaunchRetard = false;
        engineConfiguration->launchActivationMode = ALWAYS_ACTIVE_LAUNCH;
        engineConfiguration->launchSpeedThreshold = 0;
        engineConfiguration->launchTpsThreshold = 10;
        engineConfiguration->launchRpm = 1000;
        engineConfiguration->launchRpmWindow = 0;
        break;
    default:
        break;
    }
}

void driveScenario(uint32_t n) {
    if (!fuelScenario()) {
        return;
    }
    static bool configured = false;
    if (!configured) {
        configured = true;
        engineConfiguration->knockRetardAggression = 0;
        engineConfiguration->knockSuppressMinTps = 0;
        engineConfiguration->knockFuelTrim = 10;
        engineConfiguration->knockFuelTrimAggression = 20;
        printf("P8FUEL scenario=fuelcut apply=%d cylinders=%d\n", applyMode() ? 1 : 0,
               (int)engineConfiguration->cylindersCount);
    }
    if (n >= 10 && n < 300 && n % 5 == 0) {
        engine->module<KnockController>()->onKnockSenseCompleted(0, 1000.0f, getTimeNowNt());
    }
    static Phase current = Phase::Done;
    const Phase p = phaseFor(n);
    if (p != current || n == 0) {
        current = p;
        enterPhase(p);
    }
}

// Previous cycle: rusEFI's injectionMass[] against what this glue returned.
void checkPreviousCycle() {
    if (!prev.valid) {
        return;
    }
    const auto& mass = engine->engineState.injectionMass;
    int ref = -1;
    for (unsigned i = 0; i < prev.n; i++) {
        if (prev.returned[i] > 0.0f) {
            ref = static_cast<int>(i);
            break;
        }
    }
    stats.massChecks++;
    bool ok = true;
    bool allZero = true;
    const float unit = ref >= 0 ? mass[ref] / (prev.returned[ref] * prev.knock * prev.bankTrim[ref]) : 0.0f;
    for (unsigned i = 0; i < prev.n; i++) {
        if (mass[i] != 0.0f) {
            allZero = false;
        }
        if (prev.returned[i] == 0.0f) {
            ok = ok && mass[i] == 0.0f;
        } else {
            const float expected = unit * prev.returned[i] * prev.knock * prev.bankTrim[i];
            ok = ok && std::fabs(mass[i] - expected) <= 1e-4f * std::fabs(expected);
        }
    }
    if (!ok) {
        stats.massErrors++;
    }
    if (allZero && ref < 0) {
        stats.zeroMassCycles++;
    }
}

void report() {
    const efitick_t nowNt = getTimeNowNt();
    if (nowNt - stats.lastReportNt < NT_PER_SECOND) {
        return;
    }
    stats.lastReportNt = nowNt;
    const unsigned n = arbiter().configValid() ? std::min<size_t>(engineConfiguration->cylindersCount, kMaxCylinders) : 0;
    unsigned minCyl = 0xFFFFFFFFu;
    unsigned maxCyl = 0;
    for (unsigned i = 0; i < n; i++) {
        minCyl = std::min<unsigned>(minCyl, stats.perCylinderSoft[i]);
        maxCyl = std::max<unsigned>(maxCyl, stats.perCylinderSoft[i]);
    }
    // efiPrintf is not echoed to stdout after simulator init.
    printf("P8FUEL cycles=%lu cylinders=%u mismatches=%lu massChecks=%lu massErrors=%lu knockFuelCycles=%lu "
           "maxKnockTrim=%.3f rusefiCutCycles=%lu cutReasons=0x%x allCutCycles=%lu zeroMassCycles=%lu "
           "softCycles=%lu softCuts=%lu softExpected=%.1f softPerCylMin=%u softPerCylMax=%u freezeCycles=%lu "
           "lambda=%.3f\n",
           (unsigned long)stats.cycles, n, (unsigned long)stats.mismatches, (unsigned long)stats.massChecks,
           (unsigned long)stats.massErrors, (unsigned long)stats.knockFuelCycles, stats.maxKnockTrim,
           (unsigned long)stats.rusefiCutCycles, stats.cutReasons, (unsigned long)stats.allCutCycles,
           (unsigned long)stats.zeroMassCycles, (unsigned long)stats.softCycles, (unsigned long)stats.softCuts,
           stats.softPercentSum / 100.0f * (float)n, n > 0 ? minCyl : 0, maxCyl,
           (unsigned long)stats.freezeCycles, lastResult.lambdaTarget);
}

void runCycle(float rpm, float fuelLoad) {
    checkPreviousCycle();
    applyCylinderCount();
    FuelArbiter& arb = arbiter();
    const unsigned n = std::min<size_t>(engineConfiguration->cylindersCount, kMaxCylinders);

    FuelInput in;
    for (unsigned i = 0; i < n; i++) {
        in.cylinderTrim[i] = stockTrim(i, rpm, fuelLoad);
    }
    in.baseLambda = engine->fuelComputer.targetLambda;
    const float knock = engine->module<KnockController>()->getFuelTrimMultiplier();
    const LimpState injection = getLimpManager()->allowInjection();

    acc.reset();
    acc.multiplyFuel(FuelSource::Knock, knock);
    if (!injection.value) {
        mapRusefiCut(injection.reason);
    }
    float softPercent = 0.0f;
    if (applyMode() && fuelScenario()) {
        // Power8GDI strategy: progressive fuel cylinder cut across the soft window.
        // Only in the fuel scenario, so the ignition scenarios run unchanged.
        const float limit = engineConfiguration->rpmHardLimit;
        const float resume = limit - engineConfiguration->rpmHardLimitHyst;
        if (rpm > resume && rpm < limit) {
            softPercent = 100.0f * (rpm - resume) / (limit - resume);
            acc.requestCylinderCut(CylinderCutSource::RpmLimiter, softPercent, CutMode::Fuel);
        }
    }
    const FuelResult r = arb.update(in, acc);
    lastResult = r;
    const uint16_t all = static_cast<uint16_t>((1u << n) - 1u);
    const bool arbiterAllCut = (r.fuelCutCylinders & all) == all;

    stats.cycles++;
    bool mismatch = r.fault || arbiterAllCut != !injection.value;
    if (std::fabs(r.lambdaTarget - std::clamp(in.baseLambda, 0.65f, 1.30f)) > 1e-3f) {
        mismatch = true;
    }
    for (unsigned i = 0; i < n; i++) {
        const bool cut = (r.fuelCutCylinders >> i) & 1u;
        const float expected = cut ? 0.0f : in.cylinderTrim[i] * knock;
        if (std::fabs(r.fuelMultiplier[i] - expected) > 1e-5f) {
            mismatch = true;
        }
        cycleReturn[i] = applyMode() ? (cut ? 0.0f : r.fuelMultiplier[i] / knock) : in.cylinderTrim[i];
        prev.returned[i] = cycleReturn[i];
        prev.bankTrim[i] = engine->engineState.stftCorrection[engineConfiguration->cylinderBankSelect[i]];
    }
    if (!applyMode() && r.fuelCutCylinders != 0 && !arbiterAllCut) {
        mismatch = true;  // shadow: rusEFI has no partial cylinder cut
    }
    if (mismatch) {
        stats.mismatches++;
    }
    prev.n = n;
    prev.knock = knock;
    prev.valid = knock > 0.0f && std::isfinite(knock);

    if (knock > 1.0f) {
        stats.knockFuelCycles++;
        stats.maxKnockTrim = std::max(stats.maxKnockTrim, knock);
    }
    if (!injection.value) {
        stats.rusefiCutCycles++;
        stats.cutReasons |= 1u << static_cast<unsigned>(injection.reason);
    }
    if (arbiterAllCut) {
        stats.allCutCycles++;
    }
    if (r.closedLoopFreeze) {
        stats.freezeCycles++;
    }
    if (softPercent > 0.0f && r.fuelCutSource == CylinderCutSource::RpmLimiter && !arbiterAllCut) {
        stats.softCycles++;
        stats.softPercentSum += softPercent;
        for (unsigned i = 0; i < n; i++) {
            if ((r.fuelCutCylinders >> i) & 1u) {
                stats.softCuts++;
                stats.perCylinderSoft[i]++;
            }
        }
    }
    report();
    // Scenario changes act from the next cycle on: this cycle is already computed.
    driveScenario(stats.cycles);
}

float fuelTrimHook(size_t cylinderNumber, float rpm, float fuelLoad) {
    if (cylinderNumber == 0) {
        runCycle(rpm, fuelLoad);
    }
    return cylinderNumber < kMaxCylinders ? cycleReturn[cylinderNumber] : stockTrim(cylinderNumber, rpm, fuelLoad);
}

// Installed by a static initializer, like the ignition hook (p8_arbitration_sim.cpp).
struct InstallHook {
    InstallHook() { custom_board_getCylinderFuelTrim = fuelTrimHook; }
} installHook;

} // namespace
