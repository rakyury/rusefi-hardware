#pragma once

// Host-tested mass-domain planning, NOT an injector or HPFP electrical driver.
// The caller supplies a coherent snapshot and applies scheduling, driver, rail
// pressure and engine-synchronization gates again at the actual output boundary.
#include <array>
#include <cstdint>

namespace power6gdi {

inline constexpr unsigned CylinderCount = 6;
inline constexpr const char* ProfileId = "sport-gdi6";

enum class RailTopology : std::uint8_t { Shared = 0, Independent = 1 };
enum class FuelDisposition : std::uint8_t { Rejected = 0, Inhibited, Accepted };
enum class FuelFault : std::uint8_t {
    None = 0,
    ConfigurationInvalid,
    DemandInvalid,
    DiCapacityExceeded,
    PiCapacityExceeded,
    PumpCapacityExceeded,
    NumericOverflow,
};

struct FuelConfig6 {
    // Deliberately unconfigured on construction. An imported 8-cylinder
    // calibration must be rejected, never truncated to six cylinders.
    std::uint8_t cylinders = 0;
    bool piInstalled = false;
    RailTopology railTopology = RailTopology::Shared;
    // Hydraulic rail assignment, independent of which PT2001 drives a coil.
    // Shared: every entry must be 0. Independent: both 0 and 1 must be used.
    std::array<std::uint8_t, CylinderCount> diRail{};
    std::array<bool, 2> pumpConfigured{};
};

struct CylinderFuelRequest {
    // Base total mass, mg/cylinder per 720 crank degrees. Only corrections
    // shared by both injector groups (e.g. STFT) belong here. Group-specific
    // transient/PI wall-film corrections are applied AFTER partition below.
    float totalMassMg = 0.0f;
    float diFraction = 1.0f;
    bool fuelCut = false; // Cuts BOTH DI and PI for this cylinder this cycle.
    // Available mass from the separate injector models and final angular
    // windows at the CURRENT pressure/voltage/RPM, not catalog flow ratings.
    float diCapacityMg = 0.0f;
    float piCapacityMg = 0.0f;
    // Signed finite group corrections, mg, applied after the base DI/PI split
    // and before capacity checks/rail aggregation. PI film must affect only PI.
    // A negative resulting group dose is rejected, never silently clipped.
    float diTransientDeltaMg = 0.0f;
    float piTransientDeltaMg = 0.0f;
};

struct CycleFuelRequest6 {
    bool fuelAllowed = false;
    std::array<CylinderFuelRequest, CylinderCount> cylinder{};
    // Available delivery mass per complete 720-degree ENGINE cycle. These
    // inputs must account for the configured lobes, RPM and pump model upstream.
    // A disabled pump must have zero capacity; configured capacity is > 0.
    std::array<float, 2> pumpCapacityMgPerCycle{};
};

struct CylinderFuelPlan {
    float diMassMg = 0.0f;
    float piMassMg = 0.0f;
    bool diEventRequired = false;
    bool piEventRequired = false;
};

struct CycleFuelPlan6 {
    FuelDisposition disposition = FuelDisposition::Rejected;
    FuelFault fault = FuelFault::ConfigurationInvalid;
    // 0..5 for cylinder-specific failures, 0xff for whole-cycle failures.
    std::uint8_t faultCylinder = 0xff;
    std::array<CylinderFuelPlan, CylinderCount> cylinder{};
    std::array<float, 2> diRailMassMg{};
    float piTotalMassMg = 0.0f;
    std::array<float, 2> pumpFeedForwardMassMg{};
    // Capacity fraction only: not valve duty, command duration or final closed-
    // loop request. Zero consumed DI does not imply zero pressure-holding demand.
    std::array<float, 2> pumpFeedForwardPct{};
};

// Atomic result: ANY invalid input, unavailable requested injector mass or pump
// over-capacity returns a rejected plan with EVERY mass/event zero. No clipping,
// DI/PI redistribution or single-cylinder partial result is silently performed.
// Recompute the whole plan after any cut, split or capability change.
// This pure function owns no film state: the caller must commit film/integrator
// state using the ACTUAL scheduled group masses after downstream gates/cuts.
CycleFuelPlan6 allocateFuelCycle(const FuelConfig6& config,
                               const CycleFuelRequest6& request) noexcept;

} // namespace power6gdi
