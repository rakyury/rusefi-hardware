#pragma once

// Final fuel, lambda target and per-cylinder cut stage (host-testable).
//
// Reads the combined requests of one cycle from InterventionAccumulator and
// produces, for a configurable number of cylinders:
//   - a fuel multiplier per cylinder (accumulator fuel factor x stock trim,
//     0 for a fuel-cut cylinder or a full fuel cut);
//   - the cylinders whose fuel and whose spark are cut this cycle;
//   - the final lambda target;
//   - a closed-loop freeze flag.
//
// Rules (see docs/ARBITRATION.md and EMU_LESSONS.md):
//   - Fuel and spark cut percentages come from separate winners. A spark-only
//     request (ALS, launch) cannot hide a fuel-cut request (overboost, limiter):
//     the fuel cut still applies (L8).
//   - Direct injection: a spark-cut cylinder also gets its fuel cut, unless the
//     spark-cut winner is listed in sparkOnlyAllowedMask (ALS, launch: unburnt
//     fuel is the purpose there). Otherwise raw fuel would be injected into a
//     cylinder that does not fire. Such a spark cut is executed as a fuel+spark
//     cut at the larger of the fuel and spark percentages.
//   - Cut cylinders: an error accumulator gives the number k of cylinders to
//     cut this cycle, so the long-run cut fraction equals the request. Each
//     cylinder carries a debt (its share minus its cuts); the k largest debts
//     are cut, so every cylinder takes its share within one cut. Equal debts
//     prefer cylinders evenly spaced in firing order from a start position that
//     rotates every cycle. (A plain rotating walk aliases: 4 cylinders at
//     62.5 % cut two cylinders four times as often as the other two.)
//   - Lambda target = accumulator rule (offsets, then floors, then ceilings:
//     the richer limit wins), then clamped to [lambdaMin, lambdaMax]. A sweep or
//     test modulation is an offset, so it can never pass a protective ceiling
//     (L7: EMU replaces the final target with the sweep value).
//   - Closed-loop fuel correction is frozen while any fuel or spark cut is
//     active and for closedLoopHoldCycles afterwards: the sensor then sees air
//     from cut cylinders or unburnt mixture, not the mixture it controls.
//
// Fail-safe: an invalid configuration, a non-finite base lambda or a
// non-finite / non-positive trim sets `fault`. An invalid configuration cuts
// fuel on every cylinder; a bad lambda base gives safeLambda; a bad trim of one
// cylinder is replaced by 1.0 (no trim) for that cylinder.

#include <cstdint>

#include "intervention_accumulator.h"

namespace power8gdi {

constexpr std::uint8_t kMaxCylinders = 12;

struct FuelConfig {
    std::uint8_t cylinderCount = 6;  // active Power6GDI target
    // Cylinder indices (0-based) in firing order; first cylinderCount entries used.
    std::uint8_t firingOrder[kMaxCylinders] = {0, 4, 2, 5, 1, 3, 6, 7, 8, 9, 10, 11};
    // Spark-cut winners allowed to keep injecting into the cut cylinder.
    std::uint16_t sparkOnlyAllowedMask =
        (1u << static_cast<unsigned>(CylinderCutSource::AntiLag)) |
        (1u << static_cast<unsigned>(CylinderCutSource::LaunchControl)) |
        (1u << static_cast<unsigned>(CylinderCutSource::RollingLaunch));
    float lambdaMin = 0.65f;
    float lambdaMax = 1.30f;
    float safeLambda = 0.80f;        // used on a lambda fault; must lie within [min, max]
    std::uint16_t closedLoopHoldCycles = 20;
};

struct FuelInput {
    float baseLambda = 1.0f;                 // lambda table / cranking target
    // Stock per-cylinder multipliers (1.0 = no trim).
    float cylinderTrim[kMaxCylinders] = {1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1};
};

struct FuelResult {
    float fuelMultiplier[kMaxCylinders] = {};
    std::uint16_t fuelCutCylinders = 0;   // bit n = cylinder n
    std::uint16_t sparkCutCylinders = 0;
    float lambdaTarget = 1.0f;
    float fuelCutPercent = 0.0f;          // effective, after the DI rule
    float sparkCutPercent = 0.0f;
    CylinderCutSource fuelCutSource = CylinderCutSource::None;
    CylinderCutSource sparkCutSource = CylinderCutSource::None;
    bool fullFuelCut = false;             // accumulator fuel cut or invalid config
    bool closedLoopFreeze = false;
    bool fault = false;
};

bool validateFuelConfig(const FuelConfig& config);

// Picks which cylinders to cut for a percentage. Deterministic, stateful.
class CutDistributor {
public:
    std::uint16_t next(float percent, const FuelConfig& config);
    void reset();

private:
    float error_ = 0.0f;
    float debt_[kMaxCylinders] = {};  // index = firing-order position
    std::uint8_t start_ = 0;
};

class FuelArbiter {
public:
    explicit FuelArbiter(const FuelConfig& config);

    FuelResult update(const FuelInput& in, const InterventionAccumulator& acc);
    bool configValid() const { return configValid_; }

private:
    FuelConfig config_;
    bool configValid_;
    CutDistributor fuelDistributor_;
    CutDistributor sparkDistributor_;
    std::uint16_t holdLeft_ = 0;
};

} // namespace power8gdi
