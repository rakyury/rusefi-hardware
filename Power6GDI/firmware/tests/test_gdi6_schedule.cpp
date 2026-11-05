#include "../dual_gdi/gdi6_schedule_admission.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <iostream>
#include <limits>
using namespace power6gdi;
DiEvent event(std::uint8_t channel, std::uint64_t start) {
    return {channel, start, start+20, start+60, start+100, start+120};
}
int main() {
    // Synthetic time fixtures, NOT injector calibration or qualified guard.
    ScheduleQualification q{true, true, 10};
    std::array<DiEvent, 2> e{event(1, 100), event(2, 230)};
    assert(!ContractEnginePermission && !ContractGuardQualified);
    assert(admitDiSchedule({}, e.data(), e.size()).fault == AdmissionFault::Unqualified);
    assert(admitDiSchedule(q, e.data(), e.size()).accepted());
    for (std::uint64_t start : {105, 125, 165, 205, 225, 229}) {
        e[1] = event(2, start); // boost, pickup, hold, demag, guard all excluded.
        assert(admitDiSchedule(q, e.data(), 2).fault == AdmissionFault::SharedCurrentPath);
    }
    e[1] = event(1, 230); // repeated pulse on same physical channel
    assert(admitDiSchedule(q, e.data(), 2).accepted());
    e[1] = event(1, 229);
    assert(admitDiSchedule(q, e.data(), 2).fault == AdmissionFault::SharedCurrentPath);
    e = {event(4, 100), event(5, 229)};
    assert(admitDiSchedule(q, e.data(), 2).fault == AdmissionFault::SharedCurrentPath);
    e = {event(1, 100), event(3, 119)};
    assert(admitDiSchedule(q, e.data(), 2).fault == AdmissionFault::SharedBoostSupply);
    e[1] = event(3, 120);
    assert(admitDiSchedule(q, e.data(), 2).accepted());
    e = {event(4, 100), event(6, 119)};
    assert(admitDiSchedule(q, e.data(), 2).fault == AdmissionFault::SharedBoostSupply);
    e = {event(1, 100), event(4, 100)};
    assert(admitDiSchedule(q, e.data(), 2).accepted()); // Independent banks structurally.
    std::reverse(e.begin(), e.end());
    assert(admitDiSchedule(q, e.data(), 2).accepted());
    e = {event(2, 229), event(1, 100)}; // Input order must not affect overlap.
    assert(admitDiSchedule(q, e.data(), 2).fault == AdmissionFault::SharedCurrentPath);
    for (auto bad : {0, 7, 255}) {
        auto invalid = event(static_cast<std::uint8_t>(bad), 0);
        assert(admitDiSchedule(q, &invalid, 1).fault == AdmissionFault::InvalidEvent);
    }
    auto invalid = event(1, 0); invalid.pickupEnd = 19;
    assert(admitDiSchedule(q, &invalid, 1).fault == AdmissionFault::InvalidEvent);
    invalid = event(1, 0); invalid.boostEnd = 0;
    assert(admitDiSchedule(q, &invalid, 1).fault == AdmissionFault::InvalidEvent);
    invalid = event(1, 0); invalid.demagEnd = std::numeric_limits<std::uint64_t>::max()-5;
    assert(admitDiSchedule(q, &invalid, 1).fault == AdmissionFault::TimeOverflow);
    assert(admitDiSchedule(q, nullptr, 1).fault == AdmissionFault::InvalidEventSet);
    assert(admitDiSchedule(q, nullptr, 0).accepted());
    assert(admitDiSchedule(q, e.data(), MaxScheduleEvents+1).fault == AdmissionFault::InvalidEventSet);
    q.enginePermission = false;
    assert(admitDiSchedule(q, nullptr, 0).fault == AdmissionFault::Unqualified);
    q.enginePermission = true; q.guardQualified = false;
    assert(admitDiSchedule(q, e.data(), 2).fault == AdmissionFault::Unqualified);
    q.guardQualified = true; q.guardUs = 0;
    assert(admitDiSchedule(q, e.data(), 2).fault == AdmissionFault::Unqualified);
    std::cout << "GDI6 shared-path/boost scheduling admission: PASS (host only)\n";
}
