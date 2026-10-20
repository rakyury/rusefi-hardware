#include "dual_hpfp_supervisor.h"

#include <cmath>

namespace power8gdi {
namespace {

bool validPercent(float v) { return std::isfinite(v) && v >= 0.0f && v <= 100.0f; }
bool validCapacity(float v) { return std::isfinite(v) && v > 0.0f; }

SupervisorOutput reject(PumpFault fault) {
    SupervisorOutput out{};
    out.fault = fault;
    return out;
}

} // namespace

SupervisorOutput evaluateDualHpfp(const SupervisorInput& request) {
    if (!request.engineSynchronized) {
        return reject(PumpFault::SynchronizationLost);
    }

    if (request.topology != RailTopology::Shared &&
        request.topology != RailTopology::Independent) {
        return reject(PumpFault::ConfigurationInvalid);
    }

    for (const auto& pump : request.pump) {
        if (!validCapacity(pump.pumpCapacityPerCamLobe)) {
            return reject(PumpFault::ConfigurationInvalid);
        }
        if (!pump.driverReady) {
            return reject(PumpFault::DriverNotReady);
        }
    }

    if (request.topology == RailTopology::Shared) {
        // Two pumps share one pressure sensor, required on channel 0.
        if (!request.pump[0].railPressureValid) {
            return reject(PumpFault::RailSensorInvalid);
        }
        if (!validPercent(request.sharedDemandPct)) {
            return reject(PumpFault::DemandInvalid);
        }
        // Equal *capacity fraction*, not equal mass: relative pump capacities are
        // already accounted for in the calibrated combined 100% demand reference.
        return SupervisorOutput{{request.sharedDemandPct, request.sharedDemandPct},
                                true, false, PumpFault::None};
    }

    if (!request.pump[0].railPressureValid || !request.pump[1].railPressureValid) {
        return reject(PumpFault::RailSensorInvalid);
    }
    if (!validPercent(request.pump[0].demandPct) ||
        !validPercent(request.pump[1].demandPct)) {
        return reject(PumpFault::DemandInvalid);
    }

    return SupervisorOutput{{request.pump[0].demandPct, request.pump[1].demandPct},
                            true, false, PumpFault::None};
}

} // namespace power8gdi
