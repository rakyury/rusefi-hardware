#pragma once

// Controller-independent intervention arbitration for one engine control cycle.
// Host-testable reference logic: no GPIO, no rusEFI engine module calls yet.
//
// Every subsystem (limiters, launch, traction, protections, corrections...)
// writes its request into ONE accumulator; the final fuel/ignition/cut stages
// read the combined result. The combination rules are fixed and documented:
//
//   fuel factor        product of all factors; any fuel cut forces 0
//   ignition offset    sum of all offsets (degrees, + = advance)
//   lambda target      sum of offsets, then max(all floors), then min(all ceilings):
//                      on a conflict the richer (lower) limit wins, lean is the risky side
//   boost target       product of all factors
//   cylinder cut       the largest request wins; on a tie the EARLIER request wins
//
// Every request carries a source id; the set of active sources is kept as a
// bit mask for logging. Non-finite or out-of-range requests are rejected
// (not applied) and counted, so one broken subsystem cannot inject NaN into
// fuel or ignition.

#include <cstdint>

namespace power8gdi {

// Source ids are bit positions (0..15) in the corresponding mask.
enum class FuelSource : std::uint8_t {
    Cranking = 0, PrimePulse, Afterstart, Warmup, Overrun, ShortTermTrim, LongTermTrim,
    Ethanol, Knock, LaunchControl, AntiLag, Nitrous, Custom, RollingLaunch,
};

enum class FuelCutSource : std::uint8_t {
    Cranking = 0, Overrun, HardRpmLimit, BoostLimit, DbwSafety, StopSwitch,
    OilPressure, LambdaGuard, HpfpCranking, HpfpDiagnostics, GdiDriverFault,
};

enum class IgnitionSource : std::uint8_t {
    Ramping = 0, CoolantTemp, ChargeTemp, Knock, Nitrous, TractionControl, PitLimiter,
    SpeedLimiter, GearShift, DownshiftRpmMatch, RpmLimiter, Custom, RollingLaunch,
};

enum class LambdaSource : std::uint8_t {
    NitrousCeiling = 0, CoolantTemp, ChargeTemp, ExhaustTemp, Custom, Minimum,
};

enum class BoostSource : std::uint8_t {
    CoolantTemp = 0, Ethanol, Gear, VehicleSpeed, User, Knock,
};

enum class CylinderCutSource : std::uint8_t {
    None = 0, DownshiftRpmMatch, GearShift, TractionControl, PitLimiter, LaunchControl,
    AntiLag, SpeedLimiter, Cranking, RpmLimiter, Overboost, RollingLaunch, InjectorDuty, Overrun,
};

struct AccumulatorLimits {
    float fuelFactorMax = 4.0f;        // single request and final product
    float ignitionOffsetMin = -40.0f;  // final sum clamp, degrees
    float ignitionOffsetMax = 20.0f;
    float lambdaOffsetAbsMax = 0.5f;   // single request
    float boostFactorMax = 3.0f;
    // Sources whose RETARD protects the engine. It is applied whatever source
    // owns the angle (see IgnitionArbiter), unlike the comfort/strategy offsets.
    std::uint16_t protectiveIgnitionMask =
        (1u << static_cast<unsigned>(IgnitionSource::Knock)) |
        (1u << static_cast<unsigned>(IgnitionSource::CoolantTemp)) |
        (1u << static_cast<unsigned>(IgnitionSource::ChargeTemp));
};

struct CylinderCut {
    float percent = 0.0f;              // 0..100
    CylinderCutSource source = CylinderCutSource::None;
    std::uint8_t pattern = 0;          // subsystem-defined cut pattern / type
};

class InterventionAccumulator {
public:
    explicit InterventionAccumulator(const AccumulatorLimits& limits = AccumulatorLimits{});

    // Called once at the start of every cycle, before any contribution.
    void reset();

    // --- requests (return false and count a rejection when not applied) ---
    bool multiplyFuel(FuelSource src, float factor);           // factor >= 0
    void cutFuel(FuelCutSource src);
    bool addIgnition(IgnitionSource src, float degrees);
    bool addLambda(LambdaSource src, float offset);
    bool limitLambdaAbove(LambdaSource src, float ceiling);     // target <= ceiling
    bool limitLambdaBelow(LambdaSource src, float floor);       // target >= floor
    bool multiplyBoost(BoostSource src, float factor);
    bool requestCylinderCut(CylinderCutSource src, float percent, std::uint8_t pattern);

    // --- results ---
    float fuelFactor() const;                                  // 0 when any cut is active
    bool fuelCutActive() const { return fuelCutMask_ != 0; }
    float ignitionOffset() const;                              // clamped sum
    float protectiveIgnitionOffset() const;                    // retard-only part of protective sources, <= 0
    float applyLambda(float baseLambda) const;                 // base + offsets, floor, ceiling
    float boostFactor() const;
    CylinderCut cylinderCut() const { return cut_; }

    std::uint16_t fuelMask() const { return fuelMask_; }
    std::uint16_t fuelCutMask() const { return fuelCutMask_; }
    std::uint16_t ignitionMask() const { return ignitionMask_; }
    std::uint16_t lambdaMask() const { return lambdaMask_; }
    std::uint16_t boostMask() const { return boostMask_; }
    std::uint16_t cutCandidateMask() const { return cutCandidates_; }
    std::uint16_t rejectedRequests() const { return rejected_; }

private:
    bool reject();

    AccumulatorLimits limits_;
    float fuelFactor_ = 1.0f;
    float ignitionSum_ = 0.0f;
    float protectiveSum_ = 0.0f;
    float lambdaSum_ = 0.0f;
    float lambdaCeiling_ = 0.0f;
    float lambdaFloor_ = 0.0f;
    bool hasCeiling_ = false;
    bool hasFloor_ = false;
    float boostFactor_ = 1.0f;
    CylinderCut cut_{};
    std::uint16_t fuelMask_ = 0;
    std::uint16_t fuelCutMask_ = 0;
    std::uint16_t ignitionMask_ = 0;
    std::uint16_t lambdaMask_ = 0;
    std::uint16_t boostMask_ = 0;
    std::uint16_t cutCandidates_ = 0;
    std::uint16_t rejected_ = 0;
};

} // namespace power8gdi
