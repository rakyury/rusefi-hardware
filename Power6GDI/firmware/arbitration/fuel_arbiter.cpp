#include "fuel_arbiter.h"

#include <cmath>

namespace power8gdi {
namespace {

float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

bool finite(float v) { return std::isfinite(v); }

std::uint16_t allCylinders(unsigned n) { return static_cast<std::uint16_t>((1u << n) - 1u); }

} // namespace

bool validateFuelConfig(const FuelConfig& c) {
    if (c.cylinderCount == 0 || c.cylinderCount > kMaxCylinders) {
        return false;
    }
    bool seen[kMaxCylinders] = {};
    for (unsigned i = 0; i < c.cylinderCount; i++) {
        const unsigned cyl = c.firingOrder[i];
        if (cyl >= c.cylinderCount || seen[cyl]) {
            return false;
        }
        seen[cyl] = true;
    }
    if (!finite(c.lambdaMin) || !finite(c.lambdaMax) || !finite(c.safeLambda)) {
        return false;
    }
    return c.lambdaMin > 0.0f && c.lambdaMin < c.lambdaMax && c.safeLambda >= c.lambdaMin &&
           c.safeLambda <= c.lambdaMax;
}

void CutDistributor::reset() {
    error_ = 0.0f;
    for (auto& d : debt_) {
        d = 0.0f;
    }
    start_ = 0;
}

std::uint16_t CutDistributor::next(float percent, const FuelConfig& config) {
    if (!(percent > 0.0f)) {
        reset();  // no cut: start the next cut from a clean state
        return 0;
    }
    const float share = clampf(percent, 0.0f, 100.0f) / 100.0f;
    const unsigned n = config.cylinderCount;

    // How many cylinders this cycle: the long-run total follows the request.
    error_ += share * static_cast<float>(n);
    unsigned k = static_cast<unsigned>(error_ + 1e-4f);
    if (k > n) {
        k = n;
    }
    error_ -= static_cast<float>(k);

    // Which cylinders: largest debt first; on equal debt the evenly spaced
    // positions from the rotating start, then the nearest to the start.
    bool ideal[kMaxCylinders] = {};
    for (unsigned i = 0; i < k; i++) {
        ideal[(start_ + i * n / k) % n] = true;
    }
    for (unsigned pos = 0; pos < n; pos++) {
        debt_[pos] += share;
    }
    bool picked[kMaxCylinders] = {};
    std::uint16_t mask = 0;
    for (unsigned i = 0; i < k; i++) {
        int best = -1;
        long bestDebt = 0;
        for (unsigned j = 0; j < n; j++) {
            const unsigned pos = (start_ + j) % n;
            if (picked[pos]) {
                continue;
            }
            const long debt = std::lround(debt_[pos] * 1000.0f);  // float noise counts as a tie
            if (best < 0 || debt > bestDebt ||
                (debt == bestDebt && ideal[pos] && !ideal[static_cast<unsigned>(best)])) {
                best = static_cast<int>(pos);
                bestDebt = debt;
            }
        }
        picked[best] = true;
        debt_[best] -= 1.0f;
        mask |= static_cast<std::uint16_t>(1u << config.firingOrder[best]);
    }
    start_ = static_cast<std::uint8_t>((start_ + 1) % n);
    return mask;
}

FuelArbiter::FuelArbiter(const FuelConfig& config)
    : config_(config), configValid_(validateFuelConfig(config)) {}

FuelResult FuelArbiter::update(const FuelInput& in, const InterventionAccumulator& acc) {
    FuelResult out;
    if (!configValid_) {
        out.fault = true;
        out.fullFuelCut = true;
        out.fuelCutCylinders = allCylinders(kMaxCylinders);
        out.fuelCutPercent = 100.0f;
        out.lambdaTarget = FuelConfig{}.safeLambda;
        out.closedLoopFreeze = true;
        return out;
    }
    const unsigned n = config_.cylinderCount;

    // Lambda: offsets, floors, ceilings (richer wins), then the absolute clamp.
    float lambda = acc.applyLambda(in.baseLambda);
    if (!finite(in.baseLambda) || !finite(lambda)) {
        lambda = config_.safeLambda;
        out.fault = true;
    }
    out.lambdaTarget = clampf(lambda, config_.lambdaMin, config_.lambdaMax);

    // Cylinder cuts: separate fuel and spark winners.
    const CylinderCut fuelWin = acc.fuelCylinderCut();
    const CylinderCut sparkWin = acc.sparkCylinderCut();
    const bool sparkOnlyAllowed =
        (config_.sparkOnlyAllowedMask >> static_cast<unsigned>(sparkWin.source)) & 1u;
    if (sparkWin.percent > 0.0f && !sparkOnlyAllowed) {
        // A cylinder that does not fire must not be injected (DI).
        const bool sparkLarger = sparkWin.percent > fuelWin.percent;
        const CylinderCut& win = sparkLarger ? sparkWin : fuelWin;
        const std::uint16_t mask = fuelDistributor_.next(win.percent, config_);
        sparkDistributor_.reset();
        out.fuelCutCylinders = out.sparkCutCylinders = mask;
        out.fuelCutPercent = out.sparkCutPercent = win.percent;
        out.fuelCutSource = out.sparkCutSource = win.source;
    } else {
        out.fuelCutCylinders = fuelDistributor_.next(fuelWin.percent, config_);
        out.sparkCutCylinders = sparkDistributor_.next(sparkWin.percent, config_);
        out.fuelCutPercent = fuelWin.percent;
        out.sparkCutPercent = sparkWin.percent;
        out.fuelCutSource = fuelWin.source;
        out.sparkCutSource = sparkWin.source;
    }

    out.fullFuelCut = acc.fuelCutActive();
    if (out.fullFuelCut) {
        out.fuelCutCylinders = allCylinders(n);
        out.fuelCutPercent = 100.0f;
    }

    const float factor = acc.fuelFactor();  // 0 on a full cut
    for (unsigned i = 0; i < n; i++) {
        float trim = in.cylinderTrim[i];
        if (!finite(trim) || trim <= 0.0f) {
            trim = 1.0f;
            out.fault = true;
        }
        out.fuelMultiplier[i] = ((out.fuelCutCylinders >> i) & 1u) ? 0.0f : factor * trim;
    }

    const bool cutActive = out.fullFuelCut || out.fuelCutCylinders != 0 || out.sparkCutCylinders != 0;
    if (cutActive) {
        holdLeft_ = config_.closedLoopHoldCycles;
        out.closedLoopFreeze = true;
    } else if (holdLeft_ > 0) {
        holdLeft_--;
        out.closedLoopFreeze = true;
    }
    return out;
}

} // namespace power8gdi
