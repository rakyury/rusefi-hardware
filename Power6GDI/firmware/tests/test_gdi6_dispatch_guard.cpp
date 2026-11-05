#include "../dual_gdi/gdi6_dispatch_guard.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <limits>
#include <type_traits>

using namespace power6gdi;
using power8gdi::GdiState;
constexpr ScheduleQualification Qualified{true, true, 10}; // Synthetic host data ONLY.
constexpr DispatchGuardConfig Config{50, 1};
constexpr auto U64Max = std::numeric_limits<std::uint64_t>::max();

static TimedSafetySnapshot running(std::uint64_t at) {
    TimedSafetySnapshot s;
    s.capturedAtUs = at;
    s.configurationRevision = 1;
    s.safety.injectorProfile = power8gdi::GdiInjectorProfile::SportGdi6;
    s.safety.chip[0] = {true, false, true};
    s.safety.chip[1] = {true, false, true};
    s.safety.pumpConfigured[0] = s.safety.pumpConfigured[1] = true;
    s.safety.railSensorConfigured[0] = s.safety.railSensorValid[0] = true;
    s.safety.supplyHealthy = s.safety.synchronizationValid = true;
    s.safety.runRequested = s.safety.emergencyStopReleased = true;
    return s;
}

static TimedSafetySnapshot stopped(std::uint64_t at, bool confirmed = true) {
    auto s = running(at);
    s.safety.runRequested = false;
    s.safety.synchronizationValid = !confirmed;
    s.safety.engineStoppedConfirmed = confirmed;
    return s;
}

static DiEvent event(std::uint8_t channel, std::uint64_t at) {
    return {channel, at, at + 20, at + 60, at + 100, at + 120};
}

static SubmitResult submit(Gdi6DispatchGuard& guard, const DiEvent& e, std::uint64_t now) {
    return guard.submit(&e, 1, running(now), now);
}

static DispatchResult dispatch(Gdi6DispatchGuard& guard, const EventTicket& ticket, std::uint64_t now) {
    return guard.dispatch(&ticket, 1, running(now), now);
}

static void denied(const DispatchGuardResult& r, DispatchFault fault) {
    assert(!r.accepted());
    assert(r.diagnostic.fault == fault);
}

static void permitted(const DispatchResult& r, std::size_t count = 1) {
    assert(r.status.accepted() && !r.status.requirePhysicalKill && r.count == count);
}

static void default_inhibit_and_bad_configuration() {
    Gdi6DispatchGuard guard(Config); // Generated hardware qualification remains false.
    const auto out = submit(guard, event(1, 100), 90);
    denied(out.status, DispatchFault::Unqualified);
    assert(out.count == 0 && out.status.requirePhysicalKill);
    assert(guard.queuedCount() == 0);
    Gdi6DispatchGuard noAge({0, 1}, Qualified);
    denied(submit(noAge, event(1, 100), 90).status, DispatchFault::InvalidConfiguration);
    Gdi6DispatchGuard zeroId({50, 0}, Qualified);
    denied(submit(zeroId, event(1, 100), 90).status, DispatchFault::InvalidConfiguration);
    for (auto q : {ScheduleQualification{false, true, 10}, ScheduleQualification{true, false, 10},
                   ScheduleQualification{true, true, 0}}) {
        Gdi6DispatchGuard unqualified(Config, q);
        denied(submit(unqualified, event(1, 100), 90).status, DispatchFault::Unqualified);
    }
    Gdi6DispatchGuard noRevision(Config, Qualified);
    auto s = running(90);
    s.configurationRevision = 0;
    const auto e = event(1, 100);
    denied(noRevision.submit(&e, 1, s, 90).status, DispatchFault::InvalidConfiguration);
}

static void crossing_batches_current_paths() {
    // Same path includes the complete boost/pickup/hold/demag/guard interval.
    for (const auto channels : {std::array<std::uint8_t, 2>{1, 2},
                                std::array<std::uint8_t, 2>{4, 5},
                                std::array<std::uint8_t, 2>{1, 1}}) {
        for (bool inFlight : {false, true}) {
            for (std::uint64_t at : {100u, 119u, 120u, 160u, 200u, 220u, 229u, 230u}) {
                Gdi6DispatchGuard guard(Config, Qualified);
                const auto a = submit(guard, event(channels[0], 100), 90);
                assert(a.status.accepted() && a.count == 1);
                if (inFlight) permitted(dispatch(guard, a.tickets[0], 100));
                const auto b = submit(guard, event(channels[1], at), inFlight ? 100 : 90);
                if (at < 230) {
                    denied(b.status, DispatchFault::ScheduleRejected);
                    assert(b.status.diagnostic.admission == AdmissionFault::SharedCurrentPath);
                    assert(b.count == 0 && guard.queuedCount() == (inFlight ? 0u : 1u));
                } else {
                    assert(b.status.accepted() && b.count == 1);
                }
                assert(guard.startedCount() == (inFlight ? 1u : 0u));
            }
        }
    }
}

static void boost_supply_and_independent_banks() {
    for (const auto channels : {std::array<std::uint8_t, 2>{1, 3},
                                std::array<std::uint8_t, 2>{4, 6}}) {
        Gdi6DispatchGuard guard(Config, Qualified);
        const auto a = submit(guard, event(channels[0], 100), 90);
        permitted(dispatch(guard, a.tickets[0], 100));
        const auto collision = submit(guard, event(channels[1], 119), 100);
        denied(collision.status, DispatchFault::ScheduleRejected);
        assert(collision.status.diagnostic.admission == AdmissionFault::SharedBoostSupply);
        const auto b = submit(guard, event(channels[1], 120), 100);
        assert(b.status.accepted());
        permitted(dispatch(guard, b.tickets[0], 120));
        assert(guard.startedCount() == 2); // First event still retained at second boost start.
    }
    for (bool atomicDispatch : {false, true}) {
        Gdi6DispatchGuard guard(Config, Qualified);
        const std::array<DiEvent, 2> pair{event(1, 100), event(4, 100)};
        const auto s = running(90);
        const auto batch = guard.submit(pair.data(), pair.size(), s, 90);
        assert(batch.status.accepted() && batch.count == 2);
        const auto coherent = running(100);
        if (atomicDispatch) {
            const auto out = guard.dispatch(batch.tickets.data(), 2, coherent, 100);
            permitted(out, 2);
            assert(out.events[0].channel == 1 && out.events[1].channel == 4);
        } else {
            permitted(guard.dispatch(&batch.tickets[0], 1, coherent, 100));
            permitted(guard.dispatch(&batch.tickets[1], 1, coherent, 100));
        }
        assert(guard.startedCount() == 2 && guard.queuedCount() == 0);
        const auto replay = dispatch(guard, batch.tickets[0], 100);
        denied(replay.status, DispatchFault::TicketConsumed);
        assert(replay.count == 0);
    }
}

static void release_boundary() {
    Gdi6DispatchGuard guard(Config, Qualified);
    const auto first = submit(guard, event(1, 100), 90);
    permitted(dispatch(guard, first.tickets[0], 100));
    denied(submit(guard, event(2, 229), 229).status, DispatchFault::ScheduleRejected);
    assert(guard.startedCount() == 1);
    const auto next = submit(guard, event(2, 230), 230);
    assert(next.status.accepted() && guard.startedCount() == 0 && guard.queuedCount() == 1);
    permitted(dispatch(guard, next.tickets[0], 230));
    assert(guard.startedCount() == 1);
    denied(dispatch(guard, first.tickets[0], 230).status, DispatchFault::InvalidTicket);
}

static void no_early_or_late_pulses() {
    Gdi6DispatchGuard guard(Config, Qualified);
    const auto a = submit(guard, event(1, 100), 90);
    auto early = dispatch(guard, a.tickets[0], 99);
    denied(early.status, DispatchFault::TooEarly);
    assert(early.count == 0 && guard.queuedCount() == 1 && guard.startedCount() == 0);
    permitted(dispatch(guard, a.tickets[0], 100));

    for (bool fromDispatch : {false, true}) {
        Gdi6DispatchGuard late(Config, Qualified);
        const auto b = submit(late, event(1, 100), 90);
        const auto status = fromDispatch ? dispatch(late, b.tickets[0], 101).status :
            late.observe(running(101), 101);
        denied(status, DispatchFault::MissedDispatch);
        assert(status.requirePhysicalKill && status.state == GdiState::FaultLatched);
        assert(status.diagnostic.ticketId == b.tickets[0].id());
        assert(late.queuedCount() == 0 && late.startedCount() == 0);
    }
    Gdi6DispatchGuard past(Config, Qualified);
    const auto rejected = submit(past, event(1, 99), 100);
    denied(rejected.status, DispatchFault::StartInPast);
    assert(rejected.count == 0 && past.firstFault().fault == DispatchFault::None);
}

static void submit_batches_are_atomic() {
    Gdi6DispatchGuard guard(Config, Qualified);
    const auto a = submit(guard, event(1, 100), 90);
    const std::array<DiEvent, 2> invalidBatch{event(4, 100), event(2, 110)};
    const auto conflict = guard.submit(invalidBatch.data(), 2, running(90), 90);
    denied(conflict.status, DispatchFault::ScheduleRejected);
    assert(conflict.count == 0 && guard.queuedCount() == 1);
    assert(conflict.tickets[0].id() == 0 && conflict.tickets[1].id() == 0);
    const auto accepted = submit(guard, invalidBatch[0], 90);
    assert(accepted.status.accepted() && accepted.tickets[0].id() == a.tickets[0].id() + 1);
    const std::array<EventTicket, 2> tickets{a.tickets[0], accepted.tickets[0]};
    permitted(guard.dispatch(tickets.data(), 2, running(100), 100), 2);

    Gdi6DispatchGuard invalid(Config, Qualified);
    auto bad = event(4, 100);
    bad.holdEnd = bad.boostEnd - 1;
    const std::array<DiEvent, 2> malformed{event(1, 100), bad};
    const auto out = invalid.submit(malformed.data(), 2, running(90), 90);
    denied(out.status, DispatchFault::ScheduleRejected);
    assert(out.status.diagnostic.admission == AdmissionFault::InvalidEvent);
    assert(invalid.queuedCount() == 0);
    assert(submit(invalid, malformed[0], 90).tickets[0].id() == 1);
}

static void dispatch_batches_are_atomic() {
    Gdi6DispatchGuard guard(Config, Qualified);
    const std::array<DiEvent, 2> pair{event(1, 100), event(4, 100)};
    const auto batch = guard.submit(pair.data(), 2, running(90), 90);
    const std::array<EventTicket, 2> duplicate{batch.tickets[0], batch.tickets[0]};
    auto out = guard.dispatch(duplicate.data(), 2, running(100), 100);
    denied(out.status, DispatchFault::DuplicateTicket);
    assert(out.count == 0 && guard.startedCount() == 0 && guard.queuedCount() == 2);
    const std::array<EventTicket, 2> invalid{batch.tickets[0], EventTicket{}};
    out = guard.dispatch(invalid.data(), 2, running(100), 100);
    denied(out.status, DispatchFault::InvalidTicket);
    assert(out.count == 0 && guard.startedCount() == 0 && guard.queuedCount() == 2);
    permitted(guard.dispatch(batch.tickets.data(), 2, running(100), 100), 2);

    Gdi6DispatchGuard early(Config, Qualified);
    const std::array<DiEvent, 2> staggered{event(1, 100), event(4, 110)};
    const auto batch2 = early.submit(staggered.data(), 2, running(90), 90);
    out = early.dispatch(batch2.tickets.data(), 2, running(100), 100);
    denied(out.status, DispatchFault::TooEarly);
    assert(out.count == 0 && early.startedCount() == 0 && early.queuedCount() == 2);
    permitted(dispatch(early, batch2.tickets[0], 100));
    permitted(dispatch(early, batch2.tickets[1], 110));
}

static void bounded_capacity_and_bad_batch_sizes() {
    Gdi6DispatchGuard guard(Config, Qualified);
    std::array<DiEvent, MaxScheduleEvents> events{};
    for (std::size_t i = 0; i < events.size(); ++i) events[i] = event(1, 100 + i * 130);
    const auto first = guard.submit(events.data(), 31, running(90), 90);
    assert(first.count == 31);
    const std::array<DiEvent, 2> tooMany{events[31], event(1, 5000)};
    const auto rejected = guard.submit(tooMany.data(), 2, running(90), 90);
    denied(rejected.status, DispatchFault::CapacityExceeded);
    assert(rejected.count == 0 && guard.queuedCount() == 31);
    const auto final = submit(guard, events[31], 90);
    assert(final.count == 1 && final.tickets[0].id() == 32 && guard.queuedCount() == 32);
    permitted(dispatch(guard, first.tickets[0], 100));
    denied(submit(guard, event(4, 100), 100).status, DispatchFault::CapacityExceeded);
    assert(guard.startedCount() == 1 && guard.queuedCount() == 31);
    for (const auto n : {std::size_t{0}, std::size_t{33}, std::numeric_limits<std::size_t>::max()}) {
        denied(guard.submit(events.data(), n, running(100), 100).status, DispatchFault::InvalidBatch);
        denied(guard.dispatch(first.tickets.data(), n, running(100), 100).status, DispatchFault::InvalidBatch);
    }
    denied(guard.submit(nullptr, 1, running(100), 100).status, DispatchFault::InvalidBatch);
    denied(guard.dispatch(nullptr, 1, running(100), 100).status, DispatchFault::InvalidBatch);
}

static void integer_and_id_overflow() {
    Gdi6DispatchGuard guard(Config, Qualified);
    const DiEvent overflow{1, 1, 2, 3, 4, U64Max - 9};
    const auto invalid = submit(guard, overflow, 0);
    denied(invalid.status, DispatchFault::ScheduleRejected);
    assert(invalid.status.diagnostic.admission == AdmissionFault::TimeOverflow);
    const DiEvent exact{1, 1, 2, 3, 4, U64Max - 10};
    const auto valid = submit(guard, exact, 0);
    permitted(dispatch(guard, valid.tickets[0], 1));
    assert(guard.observe(running(U64Max - 1), U64Max - 1).accepted());
    assert(guard.startedCount() == 1);
    assert(guard.observe(running(U64Max), U64Max).accepted());
    assert(guard.startedCount() == 0);

    Gdi6DispatchGuard lastIds({50, U64Max - 1}, Qualified);
    const std::array<DiEvent, 3> three{event(1, 100), event(4, 100), event(3, 120)};
    const auto tooMany = lastIds.submit(three.data(), 3, running(90), 90);
    denied(tooMany.status, DispatchFault::TicketExhausted);
    assert(tooMany.count == 0 && lastIds.queuedCount() == 0);
    const auto two = lastIds.submit(three.data(), 2, running(90), 90);
    assert(two.count == 2 && two.tickets[0].id() == U64Max - 1 && two.tickets[1].id() == U64Max);
    assert(lastIds.stop(stopped(91), 91).accepted());
    const auto exhausted = submit(lastIds, event(1, 100), 92);
    denied(exhausted.status, DispatchFault::TicketExhausted);
    assert(exhausted.count == 0 && lastIds.queuedCount() == 0); // Stop did not reset IDs.
}

static void stop_rearm_preserves_active_paths() {
    Gdi6DispatchGuard guard(Config, Qualified);
    const std::array<DiEvent, 2> pair{event(1, 100), event(4, 120)};
    const auto batch = guard.submit(pair.data(), 2, running(90), 90);
    permitted(dispatch(guard, batch.tickets[0], 100));
    const auto stop = guard.stop(stopped(110, false), 110);
    assert(stop.accepted() && stop.requirePhysicalKill && stop.state == GdiState::Disarmed);
    assert(guard.startedCount() == 1 && guard.queuedCount() == 0);
    denied(submit(guard, event(2, 112), 112).status, DispatchFault::ScheduleRejected);
    denied(dispatch(guard, batch.tickets[1], 112).status, DispatchFault::InvalidTicket);
    const auto next = submit(guard, event(2, 230), 112);
    assert(next.status.accepted() && next.tickets[0].id() > batch.tickets[1].id());
    permitted(dispatch(guard, next.tickets[0], 230));
}

static void safety_fault_recovery_and_first_cause() {
    Gdi6DispatchGuard guard(Config, Qualified);
    const std::array<DiEvent, 2> pair{event(1, 100), event(4, 120)};
    const auto batch = guard.submit(pair.data(), 2, running(90), 90);
    permitted(dispatch(guard, batch.tickets[0], 100));
    auto bad = running(120);
    bad.safety.chip[1].fault = true;
    const auto blocked = guard.dispatch(&batch.tickets[1], 1, bad, 120);
    denied(blocked.status, DispatchFault::SafetyDenied);
    assert(blocked.status.diagnostic.safety == power8gdi::GdiFault::DriverB);
    assert(blocked.count == 0 && blocked.status.requirePhysicalKill);
    assert(guard.queuedCount() == 0 && guard.startedCount() == 1);
    auto secondary = running(121);
    secondary.safety.emergencyStopReleased = false;
    const auto stillBlocked = guard.observe(secondary, 121);
    assert(stillBlocked.diagnostic.safety == power8gdi::GdiFault::DriverB);
    denied(guard.acknowledgeStopped(running(122), 122), DispatchFault::RecoveryDenied);
    auto notHealthy = stopped(123);
    notHealthy.safety.supplyHealthy = false;
    denied(guard.acknowledgeStopped(notHealthy, 123), DispatchFault::RecoveryDenied);
    auto changed = stopped(124);
    changed.configurationRevision = 2;
    denied(guard.acknowledgeStopped(changed, 124), DispatchFault::RecoveryDenied);
    const auto ack = guard.acknowledgeStopped(stopped(125), 125);
    assert(ack.accepted() && ack.requirePhysicalKill && ack.state == GdiState::Disarmed);
    assert(guard.startedCount() == 1 && guard.firstFault().fault == DispatchFault::None);
    denied(submit(guard, event(2, 126), 126).status, DispatchFault::ScheduleRejected);
    denied(dispatch(guard, batch.tickets[1], 126).status, DispatchFault::InvalidTicket);
    const auto newBatch = submit(guard, event(2, 230), 126);
    assert(newBatch.status.accepted() && newBatch.tickets[0].id() > batch.tickets[1].id());
    permitted(dispatch(guard, newBatch.tickets[0], 230));
}

static void every_safety_prerequisite_is_rechecked() {
    for (unsigned fault = 0; fault < 9; ++fault) {
        Gdi6DispatchGuard guard(Config, Qualified);
        const auto a = submit(guard, event(1, 100), 90);
        auto s = running(100);
        switch (fault) {
        case 0: s.safety.supplyHealthy = false; break;
        case 1: s.safety.chip[0].fault = true; break;
        case 2: s.safety.chip[1].ready = false; break;
        case 3: s.safety.chip[0].diagnosticsFresh = false; break;
        case 4: s.safety.railSensorValid[0] = false; break;
        case 5: s.safety.railOverPressure = true; break;
        case 6: s.safety.synchronizationValid = false; break;
        case 7: s.safety.emergencyStopReleased = false; break;
        case 8: s.safety.runRequested = false; break;
        }
        const auto out = guard.dispatch(&a.tickets[0], 1, s, 100);
        denied(out.status, DispatchFault::SafetyDenied);
        assert(out.count == 0 && out.status.requirePhysicalKill && guard.queuedCount() == 0);
    }
}

static void session_configuration_cannot_change_during_stop() {
    for (bool active : {false, true}) {
        for (bool revisionChange : {false, true}) {
            Gdi6DispatchGuard guard(Config, Qualified);
            const auto a = submit(guard, event(1, active ? 100 : 200), 90);
            if (active) permitted(dispatch(guard, a.tickets[0], 100));
            assert(guard.stop(stopped(110, false), 110).accepted());
            auto modified = running(111);
            if (revisionChange) modified.configurationRevision = 2;
            else modified.safety.pumpConfigured[1] = false;
            const auto e = event(4, 200);
            const auto out = guard.submit(&e, 1, modified, 111);
            denied(out.status, DispatchFault::ConfigurationChanged);
            assert(out.count == 0 && out.status.requirePhysicalKill);
            assert(guard.startedCount() == (active ? 1u : 0u));
        }
    }
    Gdi6DispatchGuard guard(Config, Qualified);
    const auto a = submit(guard, event(1, 100), 90);
    permitted(dispatch(guard, a.tickets[0], 100));
    assert(guard.stop(stopped(110), 110).accepted()); // Standstill alone does not release a reservation.
    assert(guard.startedCount() == 1);
    assert(guard.stop(stopped(230), 230).accepted());
    assert(guard.startedCount() == 0);
    auto revised = running(231);
    revised.configurationRevision = 2;
    revised.safety.pumpConfigured[1] = false;
    const auto e = event(1, 240);
    assert(guard.submit(&e, 1, revised, 231).status.accepted());
    revised.capturedAtUs = 240;
    assert(guard.observe(revised, 240).accepted());
}

static void invalid_time_and_profile() {
    for (unsigned test = 0; test < 6; ++test) {
        Gdi6DispatchGuard guard(Config, Qualified);
        const auto a = submit(guard, event(1, 100), 90);
        auto s = running(100);
        DispatchFault expected = DispatchFault::None;
        std::uint64_t now = 100;
        switch (test) {
        case 0: s.capturedAtUs = 101; expected = DispatchFault::FutureSnapshot; break;
        case 1: s.capturedAtUs = 49; expected = DispatchFault::StaleSnapshot; break;
        case 2: s = running(89); now = 89; expected = DispatchFault::ClockRollback; break;
        case 3: s.safety.injectorProfile = power8gdi::GdiInjectorProfile::LegacyGdi8;
                expected = DispatchFault::UnsupportedProfile; break;
        case 4: s.safety.engineStoppedConfirmed = true; expected = DispatchFault::IncoherentSnapshot; break;
        case 5: s.capturedAtUs = 89; expected = DispatchFault::SnapshotRollback; break;
        }
        const auto out = guard.dispatch(&a.tickets[0], 1, s, now);
        denied(out.status, expected);
        assert(out.count == 0 && out.status.requirePhysicalKill && guard.queuedCount() == 0);
    }
    Gdi6DispatchGuard boundary(Config, Qualified);
    auto s = running(0);
    const auto e = event(1, 100);
    assert(boundary.submit(&e, 1, s, 50).status.accepted()); // Exact max age accepted.
    s.capturedAtUs = 50;
    const auto tick = boundary.observe(s, 100);
    assert(tick.accepted());
    Gdi6DispatchGuard maxFuture(Config, Qualified);
    auto future = running(U64Max);
    denied(maxFuture.observe(future, 0), DispatchFault::FutureSnapshot); // No unsigned underflow.
}

static void old_standstill_cannot_unlock_or_acknowledge() {
    Gdi6DispatchGuard guard({100, 1}, Qualified);
    const auto a = submit(guard, event(1, 200), 110);
    assert(a.status.accepted());
    denied(guard.stop(stopped(100), 120), DispatchFault::SnapshotRollback);
    auto revised = running(121);
    revised.configurationRevision = 2;
    const auto e = event(1, 200);
    denied(guard.submit(&e, 1, revised, 121).status, DispatchFault::SnapshotRollback);
    assert(guard.queuedCount() == 0 && guard.firstFault().fault == DispatchFault::SnapshotRollback);

    Gdi6DispatchGuard equalCapture({100, 1}, Qualified);
    assert(submit(equalCapture, event(1, 200), 110).status.accepted());
    assert(equalCapture.stop(stopped(110), 120).accepted()); // Cancels, but cannot unlock.
    denied(equalCapture.submit(&e, 1, revised, 121).status, DispatchFault::ConfigurationChanged);

    Gdi6DispatchGuard recovery({100, 1}, Qualified);
    assert(submit(recovery, event(1, 200), 110).status.accepted());
    auto bad = running(110); // Valid but lagging coherent sample at runtime fault boundary.
    bad.safety.chip[0].fault = true;
    denied(recovery.observe(bad, 120), DispatchFault::SafetyDenied);
    denied(recovery.acknowledgeStopped(stopped(110), 121), DispatchFault::RecoveryDenied);
    denied(recovery.acknowledgeStopped(stopped(120), 122), DispatchFault::RecoveryDenied);
    assert(recovery.acknowledgeStopped(stopped(123), 123).accepted());

    Gdi6DispatchGuard rollback({100, 1}, Qualified);
    assert(submit(rollback, event(1, 300), 200).status.accepted());
    denied(rollback.observe(running(100), 100), DispatchFault::ClockRollback);
    denied(rollback.acknowledgeStopped(stopped(101), 101), DispatchFault::ClockRollback);
    denied(rollback.acknowledgeStopped(stopped(200), 200), DispatchFault::RecoveryDenied);
    assert(rollback.acknowledgeStopped(stopped(201), 201).accepted());

    Gdi6DispatchGuard repeated({500, 1}, Qualified);
    assert(submit(repeated, event(1, 300), 90).status.accepted());
    bad = running(100);
    bad.safety.chip[0].fault = true;
    denied(repeated.observe(bad, 100), DispatchFault::SafetyDenied);
    denied(repeated.observe(bad, 200), DispatchFault::SafetyDenied);
    denied(repeated.observe(running(150), 150), DispatchFault::SafetyDenied); // First cause retained.
    denied(repeated.acknowledgeStopped(stopped(180), 210), DispatchFault::RecoveryDenied);
    auto healthy = stopped(211);
    denied(repeated.observe(healthy, 211), DispatchFault::SafetyDenied); // Still latched until ack.
    assert(repeated.acknowledgeStopped(healthy, 211).accepted()); // Same coherent copy, no deadlock.

    Gdi6DispatchGuard zeroRevision({100, 1}, Qualified);
    assert(submit(zeroRevision, event(1, 300), 100).status.accepted());
    auto revisionFault = running(200);
    revisionFault.configurationRevision = 0;
    denied(zeroRevision.observe(revisionFault, 200), DispatchFault::InvalidConfiguration);
    denied(zeroRevision.acknowledgeStopped(stopped(150), 201), DispatchFault::RecoveryDenied);
    assert(zeroRevision.acknowledgeStopped(stopped(202), 202).accepted());

    Gdi6DispatchGuard secondaryFault({500, 1}, Qualified);
    assert(submit(secondaryFault, event(1, 400), 100).status.accepted());
    bad = running(110);
    bad.safety.chip[0].fault = true;
    denied(secondaryFault.observe(bad, 110), DispatchFault::SafetyDenied);
    auto anotherFault = stopped(150);
    anotherFault.safety.chip[1].fault = true;
    denied(secondaryFault.observe(anotherFault, 300), DispatchFault::SafetyDenied);
    assert(secondaryFault.firstFault().safety == power8gdi::GdiFault::DriverA);
    denied(secondaryFault.acknowledgeStopped(stopped(200), 301), DispatchFault::RecoveryDenied);
    const auto afterBothFaults = stopped(302);
    denied(secondaryFault.observe(afterBothFaults, 302), DispatchFault::SafetyDenied);
    assert(secondaryFault.acknowledgeStopped(afterBothFaults, 302).accepted());

    Gdi6DispatchGuard lagging({100, 1}, Qualified);
    assert(submit(lagging, event(1, 300), 90).status.accepted());
    bad = running(100);
    bad.safety.chip[0].fault = true;
    denied(lagging.observe(bad, 100), DispatchFault::SafetyDenied);
    denied(lagging.acknowledgeStopped(stopped(100), 110), DispatchFault::RecoveryDenied);
    assert(lagging.acknowledgeStopped(stopped(105), 115).accepted()); // Barrier stayed at 100.

    Gdi6DispatchGuard unhealthyAck({500, 1}, Qualified);
    assert(submit(unhealthyAck, event(1, 400), 90).status.accepted());
    denied(unhealthyAck.observe(bad, 100), DispatchFault::SafetyDenied);
    auto ackFault = stopped(120);
    ackFault.safety.chip[1].fault = true;
    denied(unhealthyAck.acknowledgeStopped(ackFault, 200), DispatchFault::RecoveryDenied);
    denied(unhealthyAck.acknowledgeStopped(stopped(150), 210), DispatchFault::RecoveryDenied);
    assert(unhealthyAck.acknowledgeStopped(stopped(201), 211).accepted());
}

static void cross_instance_tickets_and_invalid_stop() {
    Gdi6DispatchGuard a(Config, Qualified), b(Config, Qualified);
    const auto qa = submit(a, event(1, 100), 90);
    const auto qb = submit(b, event(1, 100), 90);
    assert(qa.tickets[0].id() == qb.tickets[0].id());
    denied(dispatch(b, qa.tickets[0], 100).status, DispatchFault::InvalidTicket);
    assert(b.queuedCount() == 1 && b.startedCount() == 0);
    permitted(dispatch(b, qb.tickets[0], 100));
    denied(a.stop(running(95), 95), DispatchFault::InvalidStopRequest);
    assert(a.queuedCount() == 0);
}

int main() {
    static_assert(!std::is_copy_constructible_v<Gdi6DispatchGuard>);
    static_assert(!std::is_move_constructible_v<Gdi6DispatchGuard>);
    static_assert(noexcept(Gdi6DispatchGuard(Config, Qualified)));
    default_inhibit_and_bad_configuration();
    crossing_batches_current_paths();
    boost_supply_and_independent_banks();
    release_boundary();
    no_early_or_late_pulses();
    submit_batches_are_atomic();
    dispatch_batches_are_atomic();
    bounded_capacity_and_bad_batch_sizes();
    integer_and_id_overflow();
    stop_rearm_preserves_active_paths();
    safety_fault_recovery_and_first_cause();
    every_safety_prerequisite_is_rechecked();
    session_configuration_cannot_change_during_stop();
    invalid_time_and_profile();
    old_standstill_cannot_unlock_or_acknowledge();
    cross_instance_tickets_and_invalid_stop();
    std::puts("GDI6 dispatch guard: PASS (16 scenario groups, synthetic host qualification only)");
}
