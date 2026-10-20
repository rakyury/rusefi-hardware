#include "../dual_hpfp/dual_hpfp_supervisor.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>

using namespace power8gdi;

SupervisorInput makeReady(RailTopology mode) {
    SupervisorInput v;
    v.topology = mode;
    v.engineSynchronized = true;
    v.sharedDemandPct = 40;
    v.pump[0] = PumpInput{true, true, 40, 0.32f};
    v.pump[1] = PumpInput{true, true, 55, 0.26f};
    return v;
}

int main() {
    // Shared rail uses both pumps simultaneously and reports no fault.
    auto x = makeReady(RailTopology::Shared);
    auto y = evaluateDualHpfp(x);
    assert(y.allowPumpDrive && !y.inhibitGdi);
    assert(y.fault == PumpFault::None);
    assert(y.demandPct[0] == 40 && y.demandPct[1] == 40);

    // Split rail supports different per-pump demands and validates both sensors.
    x.topology = RailTopology::Independent;
    y = evaluateDualHpfp(x);
    assert(y.allowPumpDrive && y.demandPct[0] == 40 && y.demandPct[1] == 55);
    x.pump[1].railPressureValid = false;
    y = evaluateDualHpfp(x);
    assert(y.inhibitGdi && !y.allowPumpDrive && y.fault == PumpFault::RailSensorInvalid);
    assert(y.demandPct[0] == 0 && y.demandPct[1] == 0);

    x = makeReady(RailTopology::Shared);
    x.engineSynchronized = false;
    y = evaluateDualHpfp(x);
    assert(y.inhibitGdi && y.fault == PumpFault::SynchronizationLost);

    x = makeReady(RailTopology::Shared);
    x.pump[1].driverReady = false;
    y = evaluateDualHpfp(x);
    assert(y.inhibitGdi && y.fault == PumpFault::DriverNotReady);

    x = makeReady(RailTopology::Shared);
    x.pump[1].pumpCapacityPerCamLobe = 0;
    y = evaluateDualHpfp(x);
    assert(y.inhibitGdi && y.fault == PumpFault::ConfigurationInvalid);

    x = makeReady(RailTopology::Shared);
    x.sharedDemandPct = std::numeric_limits<float>::quiet_NaN();
    y = evaluateDualHpfp(x);
    assert(y.inhibitGdi && y.fault == PumpFault::DemandInvalid);

    x = makeReady(RailTopology::Shared);
    x.sharedDemandPct = 100;
    y = evaluateDualHpfp(x);
    assert(!y.inhibitGdi && y.demandPct[0] == 100 && y.demandPct[1] == 100);

    x = makeReady(RailTopology::Independent);
    x.pump[1].demandPct = std::numeric_limits<float>::infinity();
    y = evaluateDualHpfp(x);
    assert(y.inhibitGdi && y.fault == PumpFault::DemandInvalid);

    x = makeReady(RailTopology::Independent);
    x.topology = static_cast<RailTopology>(19);
    y = evaluateDualHpfp(x);
    assert(y.inhibitGdi && y.fault == PumpFault::ConfigurationInvalid);

    std::cout << "dual HPFP supervisor contract tests: PASS\n";
}
