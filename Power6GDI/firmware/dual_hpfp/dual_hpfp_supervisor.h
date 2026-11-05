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

// Deterministic fail-closed demand allocator. Does not retain fault history or
// schedule electrical pulses. Use DualHpfpSafetySupervisor for re-arm policy.
SupervisorOutput evaluateDualHpfp(const SupervisorInput& request);

enum class SupervisorState : uint8_t { Disarmed, Armed, FaultLatched };

// Controller-independent policy layer, initially disarmed. A fault on either
// pump inhibits both pumps and GDI until an explicit, valid tryRearm() call.
// Calls must be serialized by one owner; this is not an ISR-safe hardware gate.
class DualHpfpSafetySupervisor {
public:
    SupervisorOutput update(const SupervisorInput& request);

    // An explicit re-arm event, not a level-triggered readiness flag. Validates
    // the supplied snapshot; a subsequent update revalidates before any enable.
    // A failed attempt preserves the first latched fault and keeps outputs off.
    bool tryRearm(const SupervisorInput& request);

    // Returns an inhibited output for immediate application by the caller;
    // stops a healthy armed session and never clears a latched fault.
    SupervisorOutput disarm();

    SupervisorState state() const { return state_; }
    PumpFault latchedFault() const { return latchedFault_; }

private:
    void latchFault(PumpFault fault);

    SupervisorState state_ = SupervisorState::Disarmed;
    PumpFault latchedFault_ = PumpFault::None;
};

} // namespace power8gdi
