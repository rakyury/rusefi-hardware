#include "../arbitration/fuel_arbiter.h"
#include "../arbitration/intervention_accumulator.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>

using namespace power8gdi;

namespace {

const float kNaN = std::numeric_limits<float>::quiet_NaN();

bool near(float a, float b) { return std::fabs(a - b) < 1e-4f; }

unsigned popcount(std::uint16_t v) {
    unsigned n = 0;
    for (; v != 0; v &= static_cast<std::uint16_t>(v - 1)) {
        n++;
    }
    return n;
}

FuelConfig cylinders(unsigned n) {
    FuelConfig c;
    c.cylinderCount = static_cast<std::uint8_t>(n);
    for (unsigned i = 0; i < kMaxCylinders; i++) {
        c.firingOrder[i] = static_cast<std::uint8_t>(i);
    }
    return c;
}

void configValidation() {
    assert(validateFuelConfig(FuelConfig{}));  // Power6GDI default: 6 cylinders
    assert(validateFuelConfig(cylinders(4)));
    assert(validateFuelConfig(cylinders(8)));
    assert(validateFuelConfig(cylinders(12)));
    assert(!validateFuelConfig(cylinders(0)));
    assert(!validateFuelConfig(cylinders(13)));

    FuelConfig dup;
    dup.firingOrder[1] = dup.firingOrder[0];
    assert(!validateFuelConfig(dup));
    FuelConfig outside;
    outside.firingOrder[0] = 6;  // only cylinders 0..5 exist
    assert(!validateFuelConfig(outside));
    FuelConfig lambda;
    lambda.safeLambda = 1.5f;
    assert(!validateFuelConfig(lambda));
    lambda = FuelConfig{};
    lambda.lambdaMin = kNaN;
    assert(!validateFuelConfig(lambda));
}

void accumulatorKeepsFuelAndSparkWinners() {
    InterventionAccumulator acc;
    assert(acc.requestCylinderCut(CylinderCutSource::AntiLag, 60.0f, CutMode::Spark));
    assert(acc.requestCylinderCut(CylinderCutSource::Overboost, 30.0f, CutMode::Fuel));
    assert(acc.requestCylinderCut(CylinderCutSource::RpmLimiter, 30.0f, CutMode::FuelAndSpark));
    // The single overall winner is the spark-only ALS request ...
    assert(acc.cylinderCut().source == CylinderCutSource::AntiLag);
    // ... but the fuel winner is kept separately; on a tie the earlier wins.
    assert(acc.fuelCylinderCut().source == CylinderCutSource::Overboost);
    assert(acc.fuelCylinderCut().percent == 30.0f);
    assert(acc.sparkCylinderCut().source == CylinderCutSource::AntiLag);
    // Legacy pattern requests cut both.
    assert(acc.requestCylinderCut(CylinderCutSource::GearShift, 80.0f, std::uint8_t{7}));
    assert(acc.fuelCylinderCut().source == CylinderCutSource::GearShift);
    assert(acc.sparkCylinderCut().source == CylinderCutSource::GearShift);
    assert(acc.cylinderCut().pattern == 7);
    // Bad mode or percent is rejected and has no effect.
    assert(!acc.requestCylinderCut(CylinderCutSource::Overrun, 90.0f, static_cast<CutMode>(0)));
    assert(!acc.requestCylinderCut(CylinderCutSource::Overrun, kNaN, CutMode::Fuel));
    assert(acc.fuelCylinderCut().percent == 80.0f && acc.rejectedRequests() == 2);
    acc.reset();
    assert(acc.fuelCylinderCut().percent == 0.0f && acc.sparkCylinderCut().percent == 0.0f);
}

void multipliersAndFullCut() {
    FuelArbiter arb(FuelConfig{});
    InterventionAccumulator acc;
    FuelInput in;
    in.cylinderTrim[2] = 1.05f;
    acc.multiplyFuel(FuelSource::Warmup, 1.1f);
    FuelResult r = arb.update(in, acc);
    assert(!r.fault && !r.fullFuelCut && r.fuelCutCylinders == 0 && !r.closedLoopFreeze);
    assert(near(r.fuelMultiplier[0], 1.1f) && near(r.fuelMultiplier[2], 1.155f));
    assert(r.fuelMultiplier[6] == 0.0f);  // beyond cylinderCount: untouched

    acc.cutFuel(FuelCutSource::HardRpmLimit);
    r = arb.update(in, acc);
    assert(r.fullFuelCut && r.fuelCutCylinders == 0x3F && r.fuelCutPercent == 100.0f && r.closedLoopFreeze);
    for (unsigned i = 0; i < 6; i++) {
        assert(r.fuelMultiplier[i] == 0.0f);
    }
}

// Long-run cut fraction equals the request; every cylinder takes its share.
void cutDistributionExactAndRotating() {
    const unsigned counts[] = {4, 6, 8};
    const float percents[] = {5.0f, 10.0f, 25.0f, 100.0f / 3.0f, 50.0f, 62.5f, 90.0f, 100.0f};
    for (const unsigned n : counts) {
        for (const float pct : percents) {
            FuelArbiter arb(cylinders(n));
            InterventionAccumulator acc;
            const unsigned cycles = 1200;
            unsigned perCylinder[kMaxCylinders] = {};
            unsigned total = 0;
            for (unsigned c = 0; c < cycles; c++) {
                acc.reset();
                acc.requestCylinderCut(CylinderCutSource::RpmLimiter, pct, CutMode::Fuel);
                const FuelResult r = arb.update(FuelInput{}, acc);
                assert(r.sparkCutCylinders == 0 && r.fuelCutSource == CylinderCutSource::RpmLimiter);
                for (unsigned i = 0; i < n; i++) {
                    if ((r.fuelCutCylinders >> i) & 1u) {
                        perCylinder[i]++;
                        assert(r.fuelMultiplier[i] == 0.0f);
                    } else {
                        assert(r.fuelMultiplier[i] == 1.0f);
                    }
                }
                assert((r.fuelCutCylinders >> n) == 0);
                total += popcount(r.fuelCutCylinders);
            }
            const float expected = pct / 100.0f * static_cast<float>(n * cycles);
            assert(std::fabs(static_cast<float>(total) - expected) <= 1.0f);
            const float share = expected / static_cast<float>(n);
            for (unsigned i = 0; i < n; i++) {
                // Every cylinder takes its share within one cut: none is cut
                // permanently or skipped (a plain rotating walk aliases).
                assert(std::fabs(static_cast<float>(perCylinder[i]) - share) <= 1.0f);
            }
        }
    }
}

// Within one cycle, equal shares are spread in firing order, not bunched.
void cutSpreadInFiringOrder() {
    const FuelConfig cfg;  // 6 cylinders, firing order 0-4-2-5-1-3
    FuelArbiter arb(cfg);
    InterventionAccumulator acc;
    for (unsigned c = 0; c < 12; c++) {
        acc.reset();
        acc.requestCylinderCut(CylinderCutSource::RpmLimiter, 50.0f, CutMode::Fuel);
        const FuelResult r = arb.update(FuelInput{}, acc);
        std::uint16_t even = 0;
        std::uint16_t odd = 0;
        for (unsigned pos = 0; pos < 6; pos++) {
            const auto b = static_cast<std::uint16_t>(1u << cfg.firingOrder[pos]);
            (pos % 2 == 0 ? even : odd) |= b;
        }
        // Every other firing event, alternating between the two halves.
        assert(r.fuelCutCylinders == (c % 2 == 0 ? even : odd));
    }
}

// EMU_LESSONS.md L8: EMU keeps ONE cylinder-cut winner with its type, so a
// larger spark-only request (ALS) replaces a protective fuel cut (overboost).
void sparkOnlyCannotHideFuelCut() {
    FuelArbiter arb(FuelConfig{});
    InterventionAccumulator acc;
    unsigned fueledButSparkCut = 0;
    unsigned fuelCut = 0;
    for (unsigned c = 0; c < 600; c++) {
        acc.reset();
        acc.requestCylinderCut(CylinderCutSource::AntiLag, 60.0f, CutMode::Spark);
        acc.requestCylinderCut(CylinderCutSource::Overboost, 30.0f, CutMode::Fuel);
        const FuelResult r = arb.update(FuelInput{}, acc);
        assert(r.fuelCutSource == CylinderCutSource::Overboost && r.fuelCutPercent == 30.0f);
        assert(r.sparkCutSource == CylinderCutSource::AntiLag && r.sparkCutPercent == 60.0f);
        fuelCut += popcount(r.fuelCutCylinders);
        fueledButSparkCut += popcount(r.sparkCutCylinders & static_cast<std::uint16_t>(~r.fuelCutCylinders));
    }
    assert(std::fabs(static_cast<float>(fuelCut) - 0.3f * 6 * 600) <= 1.0f);  // protective fuel cut fully executed
    assert(fueledButSparkCut > 0);       // ALS keeps its spark-only cut on the other cylinders
}

// Direct injection: no raw fuel into a cylinder whose spark is cut, unless the
// spark-cut owner is allowed to do that (ALS / launch).
void diSparkCutAlsoCutsFuel() {
    FuelArbiter arb(FuelConfig{});
    InterventionAccumulator acc;
    for (unsigned c = 0; c < 300; c++) {
        acc.reset();
        acc.requestCylinderCut(CylinderCutSource::RpmLimiter, 50.0f, CutMode::Spark);
        const FuelResult r = arb.update(FuelInput{}, acc);
        assert(r.sparkCutCylinders != 0 && r.fuelCutCylinders == r.sparkCutCylinders);
        assert(r.fuelCutSource == CylinderCutSource::RpmLimiter && r.fuelCutPercent == 50.0f);
    }
    // Fuel request larger than the spark request: one fuel+spark cut at the larger percentage.
    unsigned total = 0;
    for (unsigned c = 0; c < 300; c++) {
        acc.reset();
        acc.requestCylinderCut(CylinderCutSource::TractionControl, 70.0f, CutMode::Fuel);
        acc.requestCylinderCut(CylinderCutSource::RpmLimiter, 40.0f, CutMode::Spark);
        const FuelResult r = arb.update(FuelInput{}, acc);
        assert(r.fuelCutCylinders == r.sparkCutCylinders);
        assert(r.fuelCutSource == CylinderCutSource::TractionControl && r.fuelCutPercent == 70.0f);
        total += popcount(r.fuelCutCylinders);
    }
    assert(std::fabs(static_cast<float>(total) - 0.7f * 6 * 300) <= 1.0f);
    // ALS is allowed to cut spark and keep injecting.
    acc.reset();
    acc.requestCylinderCut(CylinderCutSource::AntiLag, 50.0f, CutMode::Spark);
    const FuelResult r = arb.update(FuelInput{}, acc);
    assert(r.sparkCutCylinders != 0 && r.fuelCutCylinders == 0);
}

// Protective fuel enrichment (knock) applies whatever owns the cut.
void knockEnrichmentDuringLaunchCut() {
    FuelArbiter arb(FuelConfig{});
    InterventionAccumulator acc;
    acc.multiplyFuel(FuelSource::Knock, 1.08f);
    acc.requestCylinderCut(CylinderCutSource::LaunchControl, 50.0f, CutMode::Fuel);
    const FuelResult r = arb.update(FuelInput{}, acc);
    assert(popcount(r.fuelCutCylinders) == 3);
    for (unsigned i = 0; i < 6; i++) {
        assert(r.fuelMultiplier[i] == (((r.fuelCutCylinders >> i) & 1u) ? 0.0f : 1.08f));
    }
}

// EMU_LESSONS.md L7: EMU's lambda sweep REPLACES the final target after the
// nitrous ceiling and the minimum, so it can go lean on nitrous. Here a sweep
// is an offset; ceilings are applied last.
void lambdaSweepCannotPassCeilings() {
    FuelArbiter arb(FuelConfig{});
    InterventionAccumulator acc;
    FuelInput in;
    in.baseLambda = 1.0f;
    acc.limitLambdaAbove(LambdaSource::NitrousCeiling, 0.85f);
    acc.addLambda(LambdaSource::Sweep, 0.05f);
    assert(near(arb.update(in, acc).lambdaTarget, 0.85f));  // EMU-style replacement gives 1.05

    acc.reset();
    acc.limitLambdaAbove(LambdaSource::Knock, 0.88f);
    acc.addLambda(LambdaSource::Sweep, 0.05f);
    assert(near(arb.update(in, acc).lambdaTarget, 0.88f));

    acc.reset();
    acc.addLambda(LambdaSource::Sweep, -0.05f);
    assert(near(arb.update(in, acc).lambdaTarget, 0.95f));  // no ceiling: the sweep acts

    acc.reset();
    in.baseLambda = 2.0f;
    assert(near(arb.update(in, acc).lambdaTarget, FuelConfig{}.lambdaMax));
    in.baseLambda = kNaN;
    const FuelResult r = arb.update(in, acc);
    assert(r.fault && near(r.lambdaTarget, FuelConfig{}.safeLambda));
}

void closedLoopFreezeHold() {
    FuelConfig cfg;
    cfg.closedLoopHoldCycles = 3;
    FuelArbiter arb(cfg);
    InterventionAccumulator acc;
    assert(!arb.update(FuelInput{}, acc).closedLoopFreeze);
    acc.requestCylinderCut(CylinderCutSource::AntiLag, 20.0f, CutMode::Spark);  // spark-only cut freezes too
    assert(arb.update(FuelInput{}, acc).closedLoopFreeze);
    acc.reset();
    assert(arb.update(FuelInput{}, acc).closedLoopFreeze);
    assert(arb.update(FuelInput{}, acc).closedLoopFreeze);
    assert(arb.update(FuelInput{}, acc).closedLoopFreeze);
    assert(!arb.update(FuelInput{}, acc).closedLoopFreeze);
}

void faults() {
    FuelConfig bad;
    bad.cylinderCount = 0;
    FuelArbiter invalid(bad);
    assert(!invalid.configValid());
    InterventionAccumulator acc;
    acc.multiplyFuel(FuelSource::Warmup, 1.2f);
    FuelResult r = invalid.update(FuelInput{}, acc);
    assert(r.fault && r.fullFuelCut && r.closedLoopFreeze);
    for (const float m : r.fuelMultiplier) {
        assert(m == 0.0f);
    }

    FuelArbiter arb(FuelConfig{});
    FuelInput in;
    in.cylinderTrim[3] = kNaN;
    in.cylinderTrim[4] = -1.0f;
    r = arb.update(in, acc);
    assert(r.fault && near(r.fuelMultiplier[3], 1.2f) && near(r.fuelMultiplier[4], 1.2f));
    assert(near(r.fuelMultiplier[0], 1.2f));
}

} // namespace

int main() {
    configValidation();
    accumulatorKeepsFuelAndSparkWinners();
    multipliersAndFullCut();
    cutDistributionExactAndRotating();
    cutSpreadInFiringOrder();
    sparkOnlyCannotHideFuelCut();
    diSparkCutAlsoCutsFuel();
    knockEnrichmentDuringLaunchCut();
    lambdaSweepCannotPassCeilings();
    closedLoopFreezeHold();
    faults();
    std::cout << "fuel arbitration (fuel, lambda, cylinder cut) tests: PASS\n";
}
