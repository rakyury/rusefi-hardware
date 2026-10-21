#include "intervention_accumulator.h"

#include <cmath>

namespace power8gdi {
namespace {

template <typename E>
std::uint16_t bit(E e) {
    const auto n = static_cast<unsigned>(e);
    return n < 16 ? static_cast<std::uint16_t>(1u << n) : 0;
}

float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

} // namespace

InterventionAccumulator::InterventionAccumulator(const AccumulatorLimits& limits)
    : limits_(limits) {
    reset();
}

void InterventionAccumulator::reset() {
    fuelFactor_ = 1.0f;
    ignitionSum_ = 0.0f;
    lambdaSum_ = 0.0f;
    lambdaCeiling_ = 0.0f;
    lambdaFloor_ = 0.0f;
    hasCeiling_ = false;
    hasFloor_ = false;
    boostFactor_ = 1.0f;
    cut_ = CylinderCut{};
    fuelMask_ = fuelCutMask_ = ignitionMask_ = lambdaMask_ = boostMask_ = 0;
    cutCandidates_ = 0;
    rejected_ = 0;
}

bool InterventionAccumulator::reject() {
    if (rejected_ != 0xFFFF) {
        rejected_++;
    }
    return false;
}

bool InterventionAccumulator::multiplyFuel(FuelSource src, float factor) {
    if (!std::isfinite(factor) || factor < 0.0f || factor > limits_.fuelFactorMax) {
        return reject();
    }
    fuelFactor_ *= factor;
    if (factor != 1.0f) {
        fuelMask_ |= bit(src);
    }
    return true;
}

void InterventionAccumulator::cutFuel(FuelCutSource src) {
    fuelCutMask_ |= bit(src);
}

bool InterventionAccumulator::addIgnition(IgnitionSource src, float degrees) {
    if (!std::isfinite(degrees)) {
        return reject();
    }
    ignitionSum_ += degrees;
    if (degrees != 0.0f) {
        ignitionMask_ |= bit(src);
    }
    return true;
}

bool InterventionAccumulator::addLambda(LambdaSource src, float offset) {
    if (!std::isfinite(offset) || std::fabs(offset) > limits_.lambdaOffsetAbsMax) {
        return reject();
    }
    lambdaSum_ += offset;
    if (offset != 0.0f) {
        lambdaMask_ |= bit(src);
    }
    return true;
}

bool InterventionAccumulator::limitLambdaAbove(LambdaSource src, float ceiling) {
    if (!std::isfinite(ceiling) || ceiling <= 0.0f) {
        return reject();
    }
    if (!hasCeiling_ || ceiling < lambdaCeiling_) {
        lambdaCeiling_ = ceiling;
        hasCeiling_ = true;
    }
    lambdaMask_ |= bit(src);
    return true;
}

bool InterventionAccumulator::limitLambdaBelow(LambdaSource src, float floor) {
    if (!std::isfinite(floor) || floor <= 0.0f) {
        return reject();
    }
    if (!hasFloor_ || floor > lambdaFloor_) {
        lambdaFloor_ = floor;
        hasFloor_ = true;
    }
    lambdaMask_ |= bit(src);
    return true;
}

bool InterventionAccumulator::multiplyBoost(BoostSource src, float factor) {
    if (!std::isfinite(factor) || factor < 0.0f || factor > limits_.boostFactorMax) {
        return reject();
    }
    boostFactor_ *= factor;
    if (factor != 1.0f) {
        boostMask_ |= bit(src);
    }
    return true;
}

bool InterventionAccumulator::requestCylinderCut(CylinderCutSource src, float percent,
                                                 std::uint8_t pattern) {
    if (!std::isfinite(percent)) {
        return reject();
    }
    percent = clampf(percent, 0.0f, 100.0f);
    if (percent <= 0.0f) {
        return true;  // valid "no cut" request
    }
    cutCandidates_ |= bit(src);
    if (percent > cut_.percent) {  // strict: on a tie the earlier request keeps priority
        cut_ = CylinderCut{percent, src, pattern};
    }
    return true;
}

float InterventionAccumulator::fuelFactor() const {
    if (fuelCutMask_ != 0) {
        return 0.0f;
    }
    return clampf(fuelFactor_, 0.0f, limits_.fuelFactorMax);
}

float InterventionAccumulator::ignitionOffset() const {
    return clampf(ignitionSum_, limits_.ignitionOffsetMin, limits_.ignitionOffsetMax);
}

float InterventionAccumulator::applyLambda(float baseLambda) const {
    float target = baseLambda + lambdaSum_;
    if (hasFloor_ && target < lambdaFloor_) {
        target = lambdaFloor_;
    }
    if (hasCeiling_ && target > lambdaCeiling_) {
        target = lambdaCeiling_;  // applied last: on a floor/ceiling conflict the richer limit wins
    }
    return target;
}

float InterventionAccumulator::boostFactor() const {
    return clampf(boostFactor_, 0.0f, limits_.boostFactorMax);
}

} // namespace power8gdi
