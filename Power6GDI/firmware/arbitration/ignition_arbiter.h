#pragma once

// Ignition angle source selection by fixed priority (host-testable).
//
// Several subsystems may want to OWN the ignition angle at the same time
// (cranking, launch control, anti-lag, idle, overrun). Exactly one source is
// selected each cycle by a configurable priority list; the table angle is the
// always-available fallback. All accumulator offsets (knock, temperature,
// limiters, traction...) are added for sources listed in correctionsApplyMask;
// every other source still gets the protective retard (knock, coolant and
// charge temperature), so launch, anti-lag, idle, overrun and cranking never
// run without knock protection. The owner's base angle is rate limited with
// the rate of the selected source; corrections are added after the ramp and
// therefore act immediately.
//
// Fail-safe behaviour: a non-finite request is treated as inactive; an invalid
// configuration or a non-finite table angle produces config.safeAdvance and
// sets `fault`.

#include <cstdint>

#include "intervention_accumulator.h"

namespace power8gdi {

enum class AngleSource : std::uint8_t {
    Table = 0, Overrun, Idle, AntiLag, LaunchControl, Cranking,
};
constexpr std::uint8_t kAngleSourceCount = 6;

struct AngleRequest {
    bool active = false;
    float advanceDeg = 0.0f;
    float rateDegPerSec = 0.0f;  // max |d angle / dt| while moving to this source; 0 = no limit
};

struct IgnitionConfig {
    // Highest priority first; must be a permutation of all sources.
    AngleSource priority[kAngleSourceCount] = {
        AngleSource::Cranking, AngleSource::LaunchControl, AngleSource::AntiLag,
        AngleSource::Idle, AngleSource::Overrun, AngleSource::Table,
    };
    std::uint8_t correctionsApplyMask = 1u << static_cast<unsigned>(AngleSource::Table);
    float minAdvance = -20.0f;
    float maxAdvance = 50.0f;
    float safeAdvance = 0.0f;    // used on fault; must lie within [min, max]
};

struct IgnitionInput {
    float tableAdvanceDeg = 0.0f;
    float tableRateDegPerSec = 0.0f;
    AngleRequest request[kAngleSourceCount] = {};  // index = AngleSource; Table entry ignored
};

struct IgnitionResult {
    float advanceDeg = 0.0f;
    float correctionDeg = 0.0f;  // accumulator offset actually applied
    bool protectiveOnly = false; // owner not in correctionsApplyMask: protective retard only
    AngleSource source = AngleSource::Table;
    bool ramping = false;
    bool fault = false;
};

bool validateIgnitionConfig(const IgnitionConfig& config);

class IgnitionArbiter {
public:
    explicit IgnitionArbiter(const IgnitionConfig& config);

    IgnitionResult update(const IgnitionInput& in, const InterventionAccumulator& acc, float dtSeconds);
    void resetState() { initialized_ = false; }

private:
    IgnitionConfig config_;
    bool configValid_;
    bool initialized_ = false;
    float lastBase_ = 0.0f;  // rate-limited owner angle, before corrections
};

} // namespace power8gdi
