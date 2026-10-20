#pragma once

// Controller-independent planning layer; no MCU GPIO or engine scheduler calls.
// This is not yet connected to rusEFI's HpfpController or to a PT2001 driver.
#include <stdint.h>

namespace power8gdi {

enum class RailTopology : uint8_t { Shared = 0, Independent = 1 };
enum class PumpFault : uint8_t {
    None = 0,
    SynchronizationLost,
    DriverNotReady,
    RailSensorInvalid,
    ConfigurationInvalid,
    DemandInvalid,
};

struct PumpInput {
    bool driverReady = false;
    bool railPressureValid = false;
    float demandPct = 0.0f;  // Used in Independent mode.
    float pumpCapacityPerCamLobe = 0.0f; // Relative capacity (positive).
};

struct SupervisorInput {
    RailTopology topology = RailTopology::Shared;
    bool engineSynchronized = false;
    float sharedDemandPct = 0.0f; // % of combined calibrated pump capacity.
    PumpInput pump[2];
};

struct SupervisorOutput {
    float demandPct[2] = { 0.0f, 0.0f };
    bool allowPumpDrive = false;
    bool inhibitGdi = true;
    PumpFault fault = PumpFault::ConfigurationInvalid;
};

// Deterministic fail-closed demand allocator. Does not schedule electrical pulses.
SupervisorOutput evaluateDualHpfp(const SupervisorInput& request);

} // namespace power8gdi
