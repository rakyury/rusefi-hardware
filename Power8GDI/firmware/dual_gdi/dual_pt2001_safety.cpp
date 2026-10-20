#include "dual_pt2001_safety.h"

namespace power8gdi {

std::uint8_t DualPt2001Safety::configKey(const GdiSafetySnapshot& s) noexcept {
    return (s.railTopology == GdiRailTopology::Independent ? 1u : 0u) |
        (s.pumpConfigured[0] ? 2u : 0u) |
        (s.pumpConfigured[1] ? 4u : 0u) |
        (s.railSensorConfigured[0] ? 8u : 0u) |
        (s.railSensorConfigured[1] ? 16u : 0u);
}

bool DualPt2001Safety::configurationValid(const GdiSafetySnapshot& s) noexcept {
    if (!s.pumpConfigured[0] && !s.pumpConfigured[1]) return false;
    if (!s.railSensorConfigured[0] && !s.railSensorConfigured[1]) return false;
    if (s.railTopology != GdiRailTopology::Shared &&
        s.railTopology != GdiRailTopology::Independent) return false;
    if (s.railTopology == GdiRailTopology::Independent) {
        // Each installed pump must have an independently validated feedback sensor.
        for (unsigned i = 0; i < 2; ++i) {
            if (s.pumpConfigured[i] && !s.railSensorConfigured[i]) return false;
        }
    }
    return true;
}

GdiFault DualPt2001Safety::prerequisiteFault(const GdiSafetySnapshot& s) noexcept {
    if (!configurationValid(s)) return GdiFault::ConfigurationInvalid;
    if (!s.emergencyStopReleased) return GdiFault::EmergencyStop;
    if (!s.supplyHealthy) return GdiFault::SupplyBad;
    if (s.railOverPressure) return GdiFault::OverPressure;
    for (unsigned i = 0; i < 2; ++i) {
        if (s.chip[i].fault) return i ? GdiFault::DriverB : GdiFault::DriverA;
    }
    for (unsigned i = 0; i < 2; ++i) {
        if (!s.chip[i].diagnosticsFresh) return GdiFault::DiagnosticsStale;
    }
    for (unsigned i = 0; i < 2; ++i) {
        if (!s.chip[i].ready) return i ? GdiFault::DriverB : GdiFault::DriverA;
    }
    for (unsigned i = 0; i < 2; ++i) {
        if (s.railSensorConfigured[i] && !s.railSensorValid[i])
            return i ? GdiFault::RailB : GdiFault::RailA;
    }
    return GdiFault::None;
}

bool DualPt2001Safety::inputsHealthy(const GdiSafetySnapshot& s) noexcept {
    return prerequisiteFault(s) == GdiFault::None;
}

void DualPt2001Safety::latchFault(GdiFault fault) noexcept {
    // An asynchronous notification without an identifiable fault is still
    // a failure. Never allow an unrecognized fault to clear a latched one.
    if (state_ != GdiState::FaultLatched) {
        fault_ = fault == GdiFault::None ? GdiFault::DiagnosticsStale : fault;
    }
    state_ = GdiState::FaultLatched;
}

GdiPermits DualPt2001Safety::update(const GdiSafetySnapshot& s) noexcept {
    GdiPermits result{}; // fail-closed defaults
    if (state_ != GdiState::FaultLatched) {
        const GdiFault prereq = prerequisiteFault(s);
        if (state_ == GdiState::Armed &&
            configKey(s) != armedConfigurationKey_) {
            latchFault(GdiFault::ConfigurationInvalid);
        } else if (prereq != GdiFault::None) {
            // Once operating, a disappearing prerequisite is a latched
            // fault. Before start it merely prevents arming, except for
            // E-stop or an active overpressure alarm.
            if (state_ == GdiState::Armed || s.railOverPressure ||
                !s.emergencyStopReleased || s.chip[0].fault || s.chip[1].fault) {
                latchFault(prereq);
            } else {
                state_ = GdiState::Disarmed;
            }
        } else if (state_ == GdiState::Armed && s.runRequested &&
                   !s.synchronizationValid) {
            latchFault(GdiFault::SynchronizationLost);
        } else if (s.runRequested && s.synchronizationValid) {
            if (state_ == GdiState::Disarmed)
                armedConfigurationKey_ = configKey(s);
            state_ = GdiState::Armed;
        } else {
            state_ = GdiState::Disarmed;
        }
    }

    result.state = state_;
    result.fault = fault_;
    if (state_ == GdiState::Armed) {
        result.requestHardwareKill = false;
        for (auto& enabled : result.injectorCommand) enabled = true;
        for (unsigned i = 0; i < 2; ++i) {
            result.hpfpCommand[i] = s.pumpConfigured[i];
        }
        for (auto& enabled : result.drvenAllowed) enabled = true;
    }
    return result;
}

bool DualPt2001Safety::acknowledgeStopped(const GdiSafetySnapshot& s) noexcept {
    if (state_ != GdiState::FaultLatched || s.runRequested ||
        s.synchronizationValid || !inputsHealthy(s)) return false;
    // Re-arming occurs only during a subsequent explicit synchronized run.
    state_ = GdiState::Disarmed;
    fault_ = GdiFault::None;
    armedConfigurationKey_ = 0;
    return true;
}

} // namespace power8gdi
