#include "gdi6_schedule_admission.h"
#include <array>
#include <limits>

namespace power6gdi {
namespace {
bool overlaps(std::uint64_t a, std::uint64_t b, std::uint64_t c, std::uint64_t d) noexcept {
    return a < d && c < b; // Half-open intervals; touching boundaries are allowed.
}
}
ScheduleAdmission admitDiSchedule(const ScheduleQualification& q, const DiEvent* events,
                                 std::size_t count) noexcept {
    if (!q.enginePermission || !q.guardQualified || q.guardUs == 0)
        return {AdmissionFault::Unqualified};
    if (count > MaxScheduleEvents || (count && !events))
        return {AdmissionFault::InvalidEventSet};
    std::array<std::uint64_t, MaxScheduleEvents> release{};
    for (std::size_t i = 0; i < count; ++i) {
        const auto& e = events[i];
        if (e.channel < 1 || e.channel > 6 || !(e.start < e.boostEnd &&
            e.boostEnd <= e.pickupEnd && e.pickupEnd <= e.holdEnd && e.holdEnd <= e.demagEnd))
            return {AdmissionFault::InvalidEvent, i};
        if (e.demagEnd > std::numeric_limits<std::uint64_t>::max() - q.guardUs)
            return {AdmissionFault::TimeOverflow, i};
        release[i] = e.demagEnd + q.guardUs;
    }
    for (std::size_t i = 0; i < count; ++i) {
        for (std::size_t j = i + 1; j < count; ++j) {
            const auto& a = events[i]; const auto& b = events[j];
            if (CurrentPath[a.channel-1] == CurrentPath[b.channel-1] &&
                overlaps(a.start, release[i], b.start, release[j]))
                return {AdmissionFault::SharedCurrentPath, i, j};
            if (BoostSupply[a.channel-1] == BoostSupply[b.channel-1] &&
                overlaps(a.start, a.boostEnd, b.start, b.boostEnd))
                return {AdmissionFault::SharedBoostSupply, i, j};
        }
    }
    return {AdmissionFault::None};
}
} // namespace power6gdi
