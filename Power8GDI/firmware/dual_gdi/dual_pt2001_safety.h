#pragma once
// Power8GDI controller-independent global gate for TWO PT2001 devices.
// Host-testable reference logic. Not connected to any actual GPIO/interrupt.
// H/W DRVEN must fail low even if CPU locks up. Update MUST be integrated in
// real-time output path with robust, fresh, atomically captured sensor states.
// No solenoid current/timing logic is implemented in this file.

#include <cstdint>

namespace power8gdi {

enum class GdiFault : std::uint8_t {
    None = 0,
    EmergencyStop,
    SupplyBad,
    DriverA,
    DriverB,
    DiagnosticsStale,
    RailA,
    RailB,
    OverPressure,
    SynchronizationLost,
    ConfigurationInvalid,
};

enum class GdiState : std::uint8_t {
    Disarmed = 0,
    Armed,
    FaultLatched,
};

enum class GdiRailTopology : std::uint8_t { Shared = 0, Independent = 1 };
enum class GdiInjectorProfile : std::uint8_t {
    Unconfigured = 0,
    SportGdi6 = 6,
    LegacyGdi8 = 8,
};

struct PtChipSnapshot {
    bool ready = false;             // fully initialized/calibrated; current profile verified
    bool fault = false;             // normalized fault polarity, NOT raw PT2001 FLAG pin
    bool diagnosticsFresh = false;  // age must be checked by platform independently
};

struct GdiSafetySnapshot {
    PtChipSnapshot chip[2];
    // Immutable, validated calibration for duration of engine operation.
    // Both PT2001 ICs are required by either supported board profile.
    // Shared rails may use one pump/sensor; independent rails require both.
    GdiInjectorProfile injectorProfile = GdiInjectorProfile::Unconfigured;
    GdiRailTopology railTopology = GdiRailTopology::Shared;
    bool pumpConfigured[2] = {false, false};
    bool railSensorConfigured[2] = {false, false};
    bool railSensorValid[2] = {false, false};
    bool railOverPressure = false;
    bool supplyHealthy = false;
    bool synchronizationValid = false;
    bool runRequested = false;
    bool emergencyStopReleased = false;
    // Fresh, independently established standstill evidence for recovery.
    // False for rotating/unknown/stale state; never infer from loss of sync.
    bool engineStoppedConfirmed = false;
};

struct GdiPermits {
    // Logical cylinders, NOT raw START pins. SportGdi6 never permits 7 or 8.
    // The board adapter must map logical 1..3 to PT A and 4..6 to PT B.
    bool injectorCommand[8] = {false, false, false, false,
                               false, false, false, false};
    bool hpfpCommand[2] = {false, false};
    bool drvenAllowed[2] = {false, false};
    bool requestHardwareKill = true;
    GdiState state = GdiState::Disarmed;
    GdiFault fault = GdiFault::None;
};

class DualPt2001Safety final {
public:
    // Mutable state is not atomic. Serialize every call (including getters)
    // through one owner or a shared platform critical section.
    // Safe by default: no outputs are enabled until both drivers and rails
    // are valid, and the synchronized engine has explicitly requested a run.
    GdiPermits update(const GdiSafetySnapshot& snapshot) noexcept;

    // Explicit recovery ONLY with engineStoppedConfirmed, no run request, E-stop
    // released, supply good, valid sensors, fresh diagnostics and both PTs
    // ready/fault free. This resets the software latch, not the external
    // hardwired fault/enable latch.
    bool acknowledgeStopped(const GdiSafetySnapshot& snapshot) noexcept;

    GdiState state() const noexcept { return state_; }
    GdiFault fault() const noexcept { return fault_; }

    // A fault interrupt MUST physically assert hardware disable immediately.
    // Publish its event to the serialized owner for this software latch, or
    // use the same platform critical section as update/acknowledgeStopped.
    // Direct unsynchronized ISR access is not supported.
    void latchFault(GdiFault fault) noexcept;

private:
    static GdiFault prerequisiteFault(const GdiSafetySnapshot& s) noexcept;
    static bool inputsHealthy(const GdiSafetySnapshot& s) noexcept;
    static bool configurationValid(const GdiSafetySnapshot& s) noexcept;
    static std::uint8_t configKey(const GdiSafetySnapshot& s) noexcept;
    std::uint8_t armedConfigurationKey_ = 0;
    GdiState state_ = GdiState::Disarmed;
    GdiFault fault_ = GdiFault::None;
};

}  // namespace power8gdi
