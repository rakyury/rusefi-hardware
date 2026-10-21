#include "ignition_arbiter.h"

#include <cmath>

namespace power8gdi {
namespace {

float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

bool finite(float v) { return std::isfinite(v); }

} // namespace

bool validateIgnitionConfig(const IgnitionConfig& c) {
    bool seen[kAngleSourceCount] = {};
    for (const auto s : c.priority) {
        const auto i = static_cast<unsigned>(s);
        if (i >= kAngleSourceCount || seen[i]) {
            return false;
        }
        seen[i] = true;
    }
    if (!finite(c.minAdvance) || !finite(c.maxAdvance) || !finite(c.safeAdvance)) {
        return false;
    }
    return c.minAdvance < c.maxAdvance && c.safeAdvance >= c.minAdvance &&
           c.safeAdvance <= c.maxAdvance;
}

IgnitionArbiter::IgnitionArbiter(const IgnitionConfig& config)
    : config_(config), configValid_(validateIgnitionConfig(config)) {}

IgnitionResult IgnitionArbiter::update(const IgnitionInput& in, const InterventionAccumulator& acc,
                                       float dtSeconds) {
    IgnitionResult out;
    if (!configValid_ || !finite(in.tableAdvanceDeg) || !finite(dtSeconds) || dtSeconds < 0.0f) {
        out.fault = true;
        out.advanceDeg = configValid_ ? config_.safeAdvance : 0.0f;
        lastBase_ = out.advanceDeg;
        initialized_ = true;
        return out;
    }

    // Highest-priority active source; the table is always active.
    float target = in.tableAdvanceDeg;
    float rate = in.tableRateDegPerSec;
    for (const auto s : config_.priority) {
        if (s == AngleSource::Table) {
            break;
        }
        const AngleRequest& r = in.request[static_cast<unsigned>(s)];
        if (r.active && finite(r.advanceDeg) && finite(r.rateDegPerSec)) {
            out.source = s;
            target = r.advanceDeg;
            rate = r.rateDegPerSec;
            break;
        }
    }

    // Only the owner's base angle is rate limited; corrections are added after
    // the ramp so a knock retard is never delayed by a source change.
    target = clampf(target, config_.minAdvance, config_.maxAdvance);
    float base = target;
    if (initialized_ && rate > 0.0f) {
        const float step = rate * dtSeconds;
        const float delta = target - lastBase_;
        if (delta > step) {
            base = lastBase_ + step;
            out.ramping = true;
        } else if (delta < -step) {
            base = lastBase_ - step;
            out.ramping = true;
        }
    }
    lastBase_ = base;

    if ((config_.correctionsApplyMask >> static_cast<unsigned>(out.source)) & 1u) {
        out.correctionDeg = acc.ignitionOffset();
    } else {
        // Protective retard (knock, temperatures) applies to every owner.
        out.correctionDeg = acc.protectiveIgnitionOffset();
        out.protectiveOnly = true;
    }
    const float angle = clampf(base + out.correctionDeg, config_.minAdvance, config_.maxAdvance);

    out.advanceDeg = angle;
    initialized_ = true;
    return out;
}

} // namespace power8gdi
