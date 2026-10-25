#include "allocation_gdi6.h"

#include <cmath>
#include <limits>

namespace power6gdi {
namespace {

bool nonnegative(float value) noexcept {
    return std::isfinite(value) && value >= 0.0f;
}

CycleFuelPlan6 reject(FuelFault fault, std::uint8_t cylinder = 0xff) noexcept {
    CycleFuelPlan6 result{};
    result.fault = fault;
    result.faultCylinder = cylinder;
    return result;
}

bool fitsFloat(double value) noexcept {
    return std::isfinite(value) && value <= std::numeric_limits<float>::max();
}

} // namespace

CycleFuelPlan6 allocateFuelCycle(const FuelConfig6& config,
                               const CycleFuelRequest6& request) noexcept {
    if (config.cylinders != CylinderCount ||
        (config.railTopology != RailTopology::Shared &&
         config.railTopology != RailTopology::Independent)) {
        return reject(FuelFault::ConfigurationInvalid);
    }
    bool assigned[2] = {false, false};
    for (unsigned cylinder = 0; cylinder < CylinderCount; ++cylinder) {
        const auto rail = config.diRail[cylinder];
        if (rail > 1 || (config.railTopology == RailTopology::Shared && rail != 0)) {
            return reject(FuelFault::ConfigurationInvalid,
                          static_cast<std::uint8_t>(cylinder));
        }
        assigned[rail] = true;
    }
    if ((!config.pumpConfigured[0] && !config.pumpConfigured[1]) ||
        (config.railTopology == RailTopology::Independent &&
         (!config.pumpConfigured[0] || !config.pumpConfigured[1] ||
          !assigned[0] || !assigned[1]))) {
        return reject(FuelFault::ConfigurationInvalid);
    }
    for (unsigned pump = 0; pump < 2; ++pump) {
        const float capacity = request.pumpCapacityMgPerCycle[pump];
        if (!nonnegative(capacity) ||
            (config.pumpConfigured[pump] ? capacity <= 0.0f : capacity != 0.0f)) {
            return reject(FuelFault::ConfigurationInvalid);
        }
    }
    for (unsigned cylinder = 0; cylinder < CylinderCount; ++cylinder) {
        const auto& demand = request.cylinder[cylinder];
        if (!nonnegative(demand.totalMassMg) || !nonnegative(demand.diFraction) ||
            demand.diFraction > 1.0f || !nonnegative(demand.diCapacityMg) ||
            !nonnegative(demand.piCapacityMg)) {
            return reject(FuelFault::DemandInvalid,
                          static_cast<std::uint8_t>(cylinder));
        }
        if (!config.piInstalled && demand.diFraction != 1.0f) {
            return reject(FuelFault::ConfigurationInvalid,
                          static_cast<std::uint8_t>(cylinder));
        }
    }
    if (!request.fuelAllowed) {
        CycleFuelPlan6 result{};
        result.disposition = FuelDisposition::Inhibited;
        result.fault = FuelFault::None;
        return result;
    }

    CycleFuelPlan6 candidate{};
    double railMass[2] = {0.0, 0.0};
    double piTotal = 0.0;
    for (unsigned cylinder = 0; cylinder < CylinderCount; ++cylinder) {
        const auto& demand = request.cylinder[cylinder];
        if (demand.fuelCut || demand.totalMassMg == 0.0f) continue;
        const double total = demand.totalMassMg;
        // The injector interface consumes binary32 doses. Compare those same
        // rounded doses with its binary32 capacity (70 * 0.1f must not reject a
        // representable 7 mg dose against a 7 mg capacity).
        const float di = static_cast<float>(total * demand.diFraction);
        const float pi = static_cast<float>(total - di);
        if (di > demand.diCapacityMg) {
            return reject(FuelFault::DiCapacityExceeded,
                          static_cast<std::uint8_t>(cylinder));
        }
        if (pi > demand.piCapacityMg) {
            return reject(FuelFault::PiCapacityExceeded,
                          static_cast<std::uint8_t>(cylinder));
        }
        auto& output = candidate.cylinder[cylinder];
        output.diMassMg = di;
        output.piMassMg = pi;
        output.diEventRequired = output.diMassMg > 0.0f;
        output.piEventRequired = output.piMassMg > 0.0f;
        // Sum the actual rounded output doses, not cylinder 1 * cylinder count.
        railMass[config.diRail[cylinder]] += output.diMassMg;
        piTotal += output.piMassMg;
    }
    if (!fitsFloat(railMass[0]) || !fitsFloat(railMass[1]) || !fitsFloat(piTotal)) {
        return reject(FuelFault::NumericOverflow);
    }

    if (config.railTopology == RailTopology::Shared) {
        const double combinedCapacity = static_cast<double>(request.pumpCapacityMgPerCycle[0]) +
                                        request.pumpCapacityMgPerCycle[1];
        if (railMass[0] > combinedCapacity) {
            return reject(FuelFault::PumpCapacityExceeded);
        }
        const double fraction = railMass[0] / combinedCapacity;
        for (unsigned pump = 0; pump < 2; ++pump) {
            if (!config.pumpConfigured[pump]) continue;
            candidate.pumpFeedForwardMassMg[pump] =
                static_cast<float>(request.pumpCapacityMgPerCycle[pump] * fraction);
            candidate.pumpFeedForwardPct[pump] = static_cast<float>(100.0 * fraction);
        }
    } else {
        for (unsigned pump = 0; pump < 2; ++pump) {
            const double capacity = request.pumpCapacityMgPerCycle[pump];
            if (railMass[pump] > capacity) {
                return reject(FuelFault::PumpCapacityExceeded);
            }
            candidate.pumpFeedForwardMassMg[pump] = static_cast<float>(railMass[pump]);
            candidate.pumpFeedForwardPct[pump] = static_cast<float>(100.0 * railMass[pump] / capacity);
        }
    }
    candidate.diRailMassMg[0] = static_cast<float>(railMass[0]);
    candidate.diRailMassMg[1] = static_cast<float>(railMass[1]);
    candidate.piTotalMassMg = static_cast<float>(piTotal);
    candidate.disposition = FuelDisposition::Accepted;
    candidate.fault = FuelFault::None;
    return candidate;
}

} // namespace power6gdi
