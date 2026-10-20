#include "dual_pt2001_safety.h"
#include <cassert>
using namespace power8gdi;

static GdiSafetySnapshot good() {
    GdiSafetySnapshot s;
    s.emergencyStopReleased = true;
    s.supplyHealthy = true;
    s.synchronizationValid = true;
    s.runRequested = true;
    s.railTopology = GdiRailTopology::Independent;
    for (int i = 0; i < 2; ++i) {
        s.pumpConfigured[i] = true;
        s.railSensorConfigured[i] = true;
        s.chip[i].ready = true;
        s.chip[i].diagnosticsFresh = true;
        s.railSensorValid[i] = true;
    }
    return s;
}
static bool allDisabled(const GdiPermits& p) {
    if (!p.requestHardwareKill) return false;
    for (bool x : p.injectorCommand) if (x) return false;
    for (bool x : p.hpfpCommand) if (x) return false;
    for (bool x : p.drvenAllowed) if (x) return false;
    return true;
}
static bool allAllowed(const GdiPermits& p) {
    if (p.requestHardwareKill || p.state != GdiState::Armed) return false;
    for (bool x : p.injectorCommand) if (!x) return false;
    for (bool x : p.hpfpCommand) if (!x) return false;
    for (bool x : p.drvenAllowed) if (!x) return false;
    return true;
}

int main() {
    {
        DualPt2001Safety onBoot;
        assert(onBoot.state() == GdiState::Disarmed);
        assert(allDisabled(onBoot.update(GdiSafetySnapshot{})));
        // Missing E-stop permission at boot requires explicit recovery; a
        // different supervisor instance models a correctly initialized boot.
        assert(onBoot.state() == GdiState::FaultLatched);
        DualPt2001Safety safety;
        auto s = good();
        assert(allAllowed(safety.update(s)));
        s.chip[0].fault = true;
        auto p = safety.update(s);
        assert(allDisabled(p) && p.fault == GdiFault::DriverA);
        s.chip[0].fault = false;
        assert(allDisabled(safety.update(s))); // latched; no automatic recovery
        assert(!safety.acknowledgeStopped(s)); // engine running
        s.runRequested = false;
        s.synchronizationValid = false;
        assert(!safety.acknowledgeStopped(s)); // no independent standstill evidence
        s.engineStoppedConfirmed = true;
        assert(safety.acknowledgeStopped(s));
        assert(safety.state() == GdiState::Disarmed);
        assert(allDisabled(safety.update(s)));
        s.runRequested = true;
        s.synchronizationValid = true;
        s.engineStoppedConfirmed = false;
        assert(allAllowed(safety.update(s)));
    }
    // Every prerequisite must safely kill BOTH PTs and all injector/pump commands.
    for (int faultCase = 0; faultCase < 11; ++faultCase) {
        DualPt2001Safety safety;
        auto s = good();
        assert(allAllowed(safety.update(s)));
        switch (faultCase) {
            case 0: s.emergencyStopReleased = false; break;
            case 1: s.supplyHealthy = false; break;
            case 2: s.railOverPressure = true; break;
            case 3: s.chip[0].fault = true; break;
            case 4: s.chip[1].fault = true; break;
            case 5: s.chip[0].diagnosticsFresh = false; break;
            case 6: s.chip[1].diagnosticsFresh = false; break;
            case 7: s.chip[0].ready = false; break;
            case 8: s.chip[1].ready = false; break;
            case 9: s.railSensorValid[0] = false; break;
            case 10: s.railSensorValid[1] = false; break;
        }
        auto p = safety.update(s);
        assert(allDisabled(p));
        assert(p.state == GdiState::FaultLatched);
        assert(p.fault != GdiFault::None);
        // Resetting the measured fault without explicit acknowledge does nothing.
        assert(allDisabled(safety.update(good())));
    }
    {
        DualPt2001Safety safety;
        auto s = good();
        assert(allAllowed(safety.update(s)));
        s.synchronizationValid = false;
        const auto p = safety.update(s);
        assert(allDisabled(p) && p.fault == GdiFault::SynchronizationLost);
        s.runRequested = false;
        // A rotating engine with a failed crank sensor is also unsynchronized.
        // Clearing the run request must not turn that into a stopped engine.
        assert(!s.engineStoppedConfirmed);
        assert(!safety.acknowledgeStopped(s));
        assert(safety.fault() == GdiFault::SynchronizationLost);
        assert(allDisabled(safety.update(good()))); // restored sync cannot re-arm
        // Even confirmed standstill cannot bypass the other recovery gates.
        s.engineStoppedConfirmed = true;
        s.runRequested = true;
        assert(!safety.acknowledgeStopped(s));
        s.runRequested = false;
        s.synchronizationValid = true;
        assert(!safety.acknowledgeStopped(s));
        s.synchronizationValid = false;
        s.chip[1].diagnosticsFresh = false;
        assert(!safety.acknowledgeStopped(s));
        s.chip[1].diagnosticsFresh = true;
        assert(safety.acknowledgeStopped(s));
        assert(allDisabled(safety.update(s)));
        s.runRequested = true;
        s.synchronizationValid = true;
        s.engineStoppedConfirmed = false;
        assert(allAllowed(safety.update(s)));
    }
    {
        DualPt2001Safety safety;
        auto s = good();
        s.runRequested = false;
        s.chip[1].diagnosticsFresh = false;
        assert(allDisabled(safety.update(s)));
        assert(safety.state() == GdiState::Disarmed);
        s.chip[1].diagnosticsFresh = true;
        assert(allDisabled(safety.update(s)));
        s.runRequested = true;
        assert(allAllowed(safety.update(s)));
    }
    {
        DualPt2001Safety safety;
        safety.latchFault(GdiFault::None);
        const auto p = safety.update(good());
        assert(allDisabled(p) && p.fault == GdiFault::DiagnosticsStale);
        auto s = good();
        s.runRequested = false;
        s.synchronizationValid = false;
        s.engineStoppedConfirmed = true;
        assert(safety.acknowledgeStopped(s));
        assert(allDisabled(safety.update(s)));
    }
    // Common-rail and single-pump engines require only ONE configured
    // physical rail sensor, even though both PT2001 ICs serve 8 DI.
    {
        DualPt2001Safety safety;
        auto s = good();
        s.railTopology = GdiRailTopology::Shared;
        s.pumpConfigured[1] = false;
        s.railSensorConfigured[1] = false;
        s.railSensorValid[1] = false;
        const auto p = safety.update(s);
        assert(!p.requestHardwareKill);
        assert(p.drvenAllowed[0] && p.drvenAllowed[1]);
        assert(p.hpfpCommand[0] && !p.hpfpCommand[1]);
        for (bool enabled : p.injectorCommand) assert(enabled);
        s.railSensorValid[0] = false;
        assert(safety.update(s).fault == GdiFault::RailA);
    }
    // Default topology with no pumps or pressure transducers is fail closed.
    {
        DualPt2001Safety safety;
        auto s = good();
        s.pumpConfigured[0] = false;
        s.pumpConfigured[1] = false;
        assert(allDisabled(safety.update(s)));
        assert(safety.state() == GdiState::Disarmed);
        s.pumpConfigured[0] = true;
        s.railTopology = GdiRailTopology::Independent;
        s.railSensorConfigured[0] = false;
        assert(allDisabled(safety.update(s)));
        assert(safety.state() == GdiState::Disarmed);
    }
    // Independent rails serve all eight DI channels. Every combination that
    // omits either pump or pressure sensor must keep BOTH driver banks disabled,
    // including a complete pump/sensor pair on just one side.
    for (unsigned configuration = 0; configuration < 16; ++configuration) {
        DualPt2001Safety safety;
        auto s = good();
        s.pumpConfigured[0] = (configuration & 1u) != 0;
        s.pumpConfigured[1] = (configuration & 2u) != 0;
        s.railSensorConfigured[0] = (configuration & 4u) != 0;
        s.railSensorConfigured[1] = (configuration & 8u) != 0;
        const auto p = safety.update(s);
        if (configuration == 15) {
            assert(allAllowed(p));
        } else {
            assert(allDisabled(p));
            assert(p.state == GdiState::Disarmed);
            // The same incomplete configuration must not clear a fault latch.
            safety.latchFault(GdiFault::DriverA);
            s.runRequested = false;
            s.synchronizationValid = false;
            s.engineStoppedConfirmed = true;
            assert(!safety.acknowledgeStopped(s));
            assert(safety.fault() == GdiFault::DriverA);
        }
    }
    // Rail topology and installed pump configuration are immutable while armed.
    {
        DualPt2001Safety safety;
        auto s = good();
        assert(allAllowed(safety.update(s)));
        s.railTopology = GdiRailTopology::Shared;
        auto p = safety.update(s);
        assert(allDisabled(p) && p.fault == GdiFault::ConfigurationInvalid);
        assert(allDisabled(safety.update(good())));
    }
    {
        DualPt2001Safety safety;
        auto s = good();
        assert(allAllowed(safety.update(s)));
        s.pumpConfigured[1] = false;
        auto p = safety.update(s);
        assert(allDisabled(p) && p.fault == GdiFault::ConfigurationInvalid);
    }
    // Emergency stop while never armed still latches.
    {
        DualPt2001Safety safety;
        auto s = good();
        s.runRequested = false;
        s.emergencyStopReleased = false;
        assert(allDisabled(safety.update(s)));
        assert(safety.state() == GdiState::FaultLatched);
    }
}
