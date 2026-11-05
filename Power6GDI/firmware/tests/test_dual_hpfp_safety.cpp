#include "../dual_hpfp/dual_hpfp_supervisor.h"

#include <cstdlib>
#include <iostream>
#include <limits>
#include <vector>

using namespace power8gdi;

namespace {

void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(EXIT_FAILURE);
    }
}

SupervisorInput ready(RailTopology topology = RailTopology::Shared) {
    SupervisorInput request;
    request.topology = topology;
    request.engineSynchronized = true;
    request.sharedDemandPct = 40;
    request.pump[0] = PumpInput{true, true, 30, 0.32f};
    request.pump[1] = PumpInput{true, true, 55, 0.26f};
    return request;
}

void requireOff(const SupervisorOutput& output, PumpFault expected) {
    require(!output.allowPumpDrive && output.inhibitGdi, "both pumps and GDI inhibited");
    require(output.demandPct[0] == 0 && output.demandPct[1] == 0, "inhibited demands zero");
    require(output.fault == expected, "expected diagnostic fault");
}

void requireOn(const SupervisorOutput& output, const SupervisorInput& request) {
    require(output.allowPumpDrive && !output.inhibitGdi, "armed valid request enabled");
    require(output.fault == PumpFault::None, "armed valid request has no fault");
    for (int pump = 0; pump < 2; ++pump) {
        const auto expected = request.topology == RailTopology::Shared
            ? request.sharedDemandPct : request.pump[pump].demandPct;
        require(output.demandPct[pump] == expected, "allocator demand preserved");
    }
}

struct FaultCase {
    SupervisorInput request;
    PumpFault fault;
};

std::vector<FaultCase> faultCases() {
    std::vector<FaultCase> cases;
    const float nan = std::numeric_limits<float>::quiet_NaN();
    const float inf = std::numeric_limits<float>::infinity();
    for (auto topology : {RailTopology::Shared, RailTopology::Independent}) {
        auto request = ready(topology);
        request.engineSynchronized = false;
        cases.push_back({request, PumpFault::SynchronizationLost});
        request = ready(topology);
        request.topology = static_cast<RailTopology>(255);
        cases.push_back({request, PumpFault::ConfigurationInvalid});
        for (int pump = 0; pump < 2; ++pump) {
            request = ready(topology);
            request.pump[pump].driverReady = false;
            cases.push_back({request, PumpFault::DriverNotReady});
            for (float capacity : {0.0f, -1.0f, nan, inf, -inf}) {
                request = ready(topology);
                request.pump[pump].pumpCapacityPerCamLobe = capacity;
                cases.push_back({request, PumpFault::ConfigurationInvalid});
            }
            if (topology == RailTopology::Independent || pump == 0) {
                request = ready(topology);
                request.pump[pump].railPressureValid = false;
                cases.push_back({request, PumpFault::RailSensorInvalid});
                for (float demand : {-0.01f, 100.01f, nan, inf, -inf}) {
                    request = ready(topology);
                    if (topology == RailTopology::Shared) {
                        request.sharedDemandPct = demand;
                    } else {
                        request.pump[pump].demandPct = demand;
                    }
                    cases.push_back({request, PumpFault::DemandInvalid});
                }
            }
        }
    }
    return cases;
}

void testStartupAndManualDisarm() {
    for (auto topology : {RailTopology::Shared, RailTopology::Independent}) {
        const auto request = ready(topology);
        DualHpfpSafetySupervisor supervisor;
        require(supervisor.state() == SupervisorState::Disarmed, "startup disarmed");
        require(supervisor.latchedFault() == PumpFault::None, "startup has no invented fault");
        for (int cycle = 0; cycle < 3; ++cycle) {
            requireOff(supervisor.update(request), PumpFault::None);
        }
        require(supervisor.tryRearm(request), "valid explicit startup arm accepted");
        require(supervisor.state() == SupervisorState::Armed, "explicit arm changes state");
        requireOn(supervisor.update(request), request);
        requireOff(supervisor.disarm(), PumpFault::None);
        require(supervisor.state() == SupervisorState::Disarmed, "manual disarm changes state");
        requireOff(supervisor.update(request), PumpFault::None);
        requireOff(supervisor.disarm(), PumpFault::None);
        require(supervisor.tryRearm(request), "manual disarm requires explicit arm");
        requireOn(supervisor.update(request), request);
    }
}

void testEveryFaultTransition(const std::vector<FaultCase>& cases) {
    for (const auto& faultCase : cases) {
        const auto healthy = ready(faultCase.request.topology == RailTopology::Independent
            ? RailTopology::Independent : RailTopology::Shared);
        DualHpfpSafetySupervisor supervisor;
        require(supervisor.tryRearm(healthy), "initial arm accepted");
        requireOn(supervisor.update(healthy), healthy);
        requireOff(supervisor.update(faultCase.request), faultCase.fault);
        require(supervisor.state() == SupervisorState::FaultLatched, "fault changes state");
        require(supervisor.latchedFault() == faultCase.fault, "fault is latched");
        // Restored readiness must not restart a stopped pump, regardless of time.
        for (int cycle = 0; cycle < 3; ++cycle) {
            requireOff(supervisor.update(healthy), faultCase.fault);
        }
        require(!supervisor.tryRearm(faultCase.request), "invalid re-arm rejected");
        requireOff(supervisor.update(healthy), faultCase.fault);
        requireOff(supervisor.disarm(), faultCase.fault);
        require(supervisor.state() == SupervisorState::FaultLatched, "disarm retains latch");
        require(supervisor.tryRearm(healthy), "healthy explicit re-arm accepted");
        require(supervisor.latchedFault() == PumpFault::None, "successful re-arm clears fault");
        requireOn(supervisor.update(healthy), healthy);

        // An invalid explicit arm must fail even before the first update call.
        DualHpfpSafetySupervisor startup;
        require(!startup.tryRearm(faultCase.request), "invalid initial arm rejected");
        requireOff(startup.update(healthy), faultCase.fault);
        // An already armed session cannot use a re-arm call to bypass a fault.
        require(!supervisor.tryRearm(faultCase.request), "invalid arm while armed trips");
        requireOff(supervisor.update(healthy), faultCase.fault);

        DualHpfpSafetySupervisor disarmed;
        requireOff(disarmed.update(faultCase.request), faultCase.fault);
        requireOff(disarmed.update(healthy), faultCase.fault);
    }
}

void testFirstFaultAndFreshSnapshot() {
    const auto healthy = ready();
    auto first = healthy;
    first.pump[1].driverReady = false;
    auto second = healthy;
    second.engineSynchronized = false;
    DualHpfpSafetySupervisor supervisor;
    require(supervisor.tryRearm(healthy), "initial arm accepted");
    requireOff(supervisor.update(first), PumpFault::DriverNotReady);
    requireOff(supervisor.update(second), PumpFault::DriverNotReady);
    require(!supervisor.tryRearm(second), "second fault blocks re-arm");
    require(supervisor.latchedFault() == PumpFault::DriverNotReady, "first fault retained");
    require(supervisor.tryRearm(healthy), "valid re-arm accepted after faults");
    // Conditions can change after tryRearm: the next update must revalidate.
    requireOff(supervisor.update(second), PumpFault::SynchronizationLost);
    requireOff(supervisor.update(healthy), PumpFault::SynchronizationLost);
    require(supervisor.tryRearm(healthy), "new fault needs another explicit re-arm");
    requireOn(supervisor.update(healthy), healthy);
}

void testAllocatorCompatibilityAndBoundaries() {
    for (auto topology : {RailTopology::Shared, RailTopology::Independent}) {
        for (float demand : {0.0f, 100.0f}) {
            auto request = ready(topology);
            request.sharedDemandPct = demand;
            request.pump[0].demandPct = demand;
            request.pump[1].demandPct = 100.0f - demand;
            if (topology == RailTopology::Shared) {
                // Shared mode deliberately uses only channel 0 pressure and
                // shared demand; do not silently change the allocator contract.
                request.pump[1].railPressureValid = false;
                request.pump[0].demandPct = std::numeric_limits<float>::quiet_NaN();
                request.pump[1].demandPct = std::numeric_limits<float>::quiet_NaN();
            } else {
                request.sharedDemandPct = std::numeric_limits<float>::quiet_NaN();
            }
            requireOn(evaluateDualHpfp(request), request);
            DualHpfpSafetySupervisor supervisor;
            require(supervisor.tryRearm(request), "boundary demand may be armed");
            requireOn(supervisor.update(request), request);
            auto invalid = request;
            invalid.engineSynchronized = false;
            requireOff(evaluateDualHpfp(invalid), PumpFault::SynchronizationLost);
            requireOn(evaluateDualHpfp(request), request); // Pure function remains pure.
        }
    }
}

} // namespace

int main() {
    testStartupAndManualDisarm();
    const auto cases = faultCases();
    testEveryFaultTransition(cases);
    testFirstFaultAndFreshSnapshot();
    testAllocatorCompatibilityAndBoundaries();
    std::cout << "dual HPFP latched safety transitions: PASS (" << cases.size()
              << " fault cases; startup, disarm, recovery, re-arm, first-fault, boundaries)\n";
}
