#pragma once
// Offline deterministic admission only. This does not drive GPIO, load PT2001
// microcode or establish timing/power qualification. Run again at the actual
// scheduling boundary using the complete event set including in-flight events.
#include "gdi6_resource_map.h"
#include <cstddef>
#include <cstdint>

namespace power6gdi {
inline constexpr std::size_t MaxScheduleEvents = 32;
struct ScheduleQualification {
    bool enginePermission = ContractEnginePermission;
    bool guardQualified = ContractGuardQualified;
    std::uint32_t guardUs = ContractGuardUs;
};
struct DiEvent {
    std::uint8_t channel = 0; // Physical connector DI1..DI6, NOT firing-order index.
    // Absolute monotonic microseconds. Unwrap timer/cycle boundaries upstream;
    // never pass modulo-720 angles or wraparound hardware timer values here.
    std::uint64_t start = 0, boostEnd = 0, pickupEnd = 0, holdEnd = 0, demagEnd = 0;
};
enum class AdmissionFault : std::uint8_t {
    None, Unqualified, InvalidEventSet, InvalidEvent, TimeOverflow,
    SharedCurrentPath, SharedBoostSupply
};
struct ScheduleAdmission {
    AdmissionFault fault = AdmissionFault::Unqualified;
    std::size_t first = MaxScheduleEvents, second = MaxScheduleEvents;
    bool accepted() const noexcept { return fault == AdmissionFault::None; }
};
ScheduleAdmission admitDiSchedule(const ScheduleQualification& qualification,
                                 const DiEvent* events, std::size_t count) noexcept;
} // namespace power6gdi
