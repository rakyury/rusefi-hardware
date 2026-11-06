#include "gdi6_dispatch_guard.h"
#include <limits>

namespace power6gdi {
namespace {
using power8gdi::GdiFault;
using power8gdi::GdiState;

DispatchDiagnostic admissionDiagnostic(const ScheduleAdmission& a) noexcept {
    return {DispatchFault::ScheduleRejected, a.fault, GdiFault::None, a.first, a.second};
}

bool healthyStandstill(const power8gdi::GdiSafetySnapshot& snapshot) noexcept {
    // Reuse the existing recovery predicate; this temporary object has no I/O.
    power8gdi::DualPt2001Safety probe;
    probe.latchFault(GdiFault::ConfigurationInvalid);
    return probe.acknowledgeStopped(snapshot);
}
}

Gdi6DispatchGuard::Gdi6DispatchGuard(DispatchGuardConfig config,
                                   ScheduleQualification qualification) noexcept
    : config_(config), qualification_(qualification), nextTicketId_(config.initialTicketId) {}

DispatchGuardResult Gdi6DispatchGuard::result(DispatchDiagnostic diagnostic) const noexcept {
    return {diagnostic, safety_.state(), safety_.state() != GdiState::Armed ||
        firstFault_.fault != DispatchFault::None || !qualification_.enginePermission ||
        !qualification_.guardQualified || qualification_.guardUs == 0};
}

void Gdi6DispatchGuard::cancelQueued() noexcept {
    for (auto& r : reservations_) {
        if (r.state == ReservationState::Queued) r = {};
    }
}

DispatchGuardResult Gdi6DispatchGuard::trip(DispatchDiagnostic diagnostic) noexcept {
    if (firstFault_.fault == DispatchFault::None) {
        firstFault_ = diagnostic;
    }
    recoveryAfterUs_ = lastNowUs_; // Monotonic watermark; keep advancing on repeated faults.
    // A guard runtime failure uses the existing stopped/healthy acknowledge
    // mechanism. Its precise cause remains firstFault_, not the generic fallback.
    safety_.latchFault(diagnostic.safety == GdiFault::None ?
        GdiFault::ConfigurationInvalid : diagnostic.safety);
    cancelQueued();
    return result(firstFault_);
}

void Gdi6DispatchGuard::releaseStarted(std::uint64_t nowUs) noexcept {
    for (auto& r : reservations_) {
        if (r.state == ReservationState::Started && nowUs >= r.releaseAtUs) r = {};
    }
}

std::size_t Gdi6DispatchGuard::queuedCount() const noexcept {
    std::size_t count = 0;
    for (const auto& r : reservations_) if (r.state == ReservationState::Queued) ++count;
    return count;
}

std::size_t Gdi6DispatchGuard::startedCount() const noexcept {
    std::size_t count = 0;
    for (const auto& r : reservations_) if (r.state == ReservationState::Started) ++count;
    return count;
}

bool Gdi6DispatchGuard::sameConfiguration(const TimedSafetySnapshot& snapshot) const noexcept {
    const auto& a = sessionConfiguration_;
    const auto& b = snapshot.safety;
    return sessionRevision_ == snapshot.configurationRevision &&
        a.injectorProfile == b.injectorProfile && a.railTopology == b.railTopology &&
        a.pumpConfigured[0] == b.pumpConfigured[0] && a.pumpConfigured[1] == b.pumpConfigured[1] &&
        a.railSensorConfigured[0] == b.railSensorConfigured[0] &&
        a.railSensorConfigured[1] == b.railSensorConfigured[1];
}

DispatchGuardResult Gdi6DispatchGuard::validateObservation(const TimedSafetySnapshot& s,
                                                          std::uint64_t nowUs) noexcept {
    if (clockSeen_ && nowUs < lastNowUs_) return trip({DispatchFault::ClockRollback});
    clockSeen_ = true;
    lastNowUs_ = nowUs; // Equal time is valid for simultaneous independent events.
    if (config_.maxSnapshotAgeUs == 0 || config_.initialTicketId == 0 ||
        s.configurationRevision == 0) return trip({DispatchFault::InvalidConfiguration});
    if (s.capturedAtUs > nowUs) return trip({DispatchFault::FutureSnapshot});
    if (nowUs - s.capturedAtUs > config_.maxSnapshotAgeUs)
        return trip({DispatchFault::StaleSnapshot});
    if (captureSeen_ && s.capturedAtUs < lastCapturedAtUs_)
        return trip({DispatchFault::SnapshotRollback});
    captureSeen_ = true;
    lastCapturedAtUs_ = s.capturedAtUs;
    if (s.safety.injectorProfile != power8gdi::GdiInjectorProfile::SportGdi6)
        return trip({DispatchFault::UnsupportedProfile});
    if (s.safety.engineStoppedConfirmed && s.safety.synchronizationValid)
        return trip({DispatchFault::IncoherentSnapshot});
    const auto qualification = admitDiSchedule(qualification_, nullptr, 0);
    if (!qualification.accepted()) return trip({DispatchFault::Unqualified, qualification.fault});
    releaseStarted(nowUs);
    // This helper deliberately permits a valid observation while fault-latched,
    // so acknowledgeStopped can use fresh time without erasing reservations.
    return result();
}

DispatchGuardResult Gdi6DispatchGuard::prepare(const TimedSafetySnapshot& s,
                                              std::uint64_t nowUs) noexcept {
    auto checked = validateObservation(s, nowUs);
    if (!checked.accepted()) return checked;
    if (firstFault_.fault != DispatchFault::None) {
        // A healthy stopped observation is usable for acknowledge at this same
        // instant. An ongoing run/unhealthy state still requires later evidence.
        if (!healthyStandstill(s.safety)) recoveryAfterUs_ = lastNowUs_;
        return result(firstFault_);
    }

    for (std::size_t i = 0; i < reservations_.size(); ++i) {
        const auto& r = reservations_[i];
        if (r.state == ReservationState::Queued && r.event.start < nowUs)
            return trip({DispatchFault::MissedDispatch, AdmissionFault::None,
                         GdiFault::None, i, MaxScheduleEvents, r.ticketId});
    }
    if (configurationLocked_ && !sameConfiguration(s))
        return trip({DispatchFault::ConfigurationChanged});

    const auto permits = safety_.update(s.safety); // Fresh check on EVERY call.
    if (permits.state == GdiState::FaultLatched)
        return trip({DispatchFault::SafetyDenied, AdmissionFault::None, permits.fault});
    if (permits.state != GdiState::Armed) {
        cancelQueued();
        if (s.safety.runRequested)
            return trip({DispatchFault::SafetyDenied, AdmissionFault::None, permits.fault});
        if (startedCount() == 0 && s.capturedAtUs > lastArmedAtUs_ &&
            healthyStandstill(s.safety)) configurationLocked_ = false;
    } else {
        lastArmedAtUs_ = nowUs;
        if (!configurationLocked_) {
            sessionConfiguration_ = s.safety;
            sessionRevision_ = s.configurationRevision;
            configurationLocked_ = true;
        }
    }
    return result();
}

std::size_t Gdi6DispatchGuard::retainedEvents(
    std::array<DiEvent, MaxScheduleEvents>& events) const noexcept {
    std::size_t count = 0;
    for (const auto& r : reservations_) {
        if (r.state != ReservationState::Empty) events[count++] = r.event;
    }
    return count;
}

SubmitResult Gdi6DispatchGuard::submit(const DiEvent* events, std::size_t count,
                                     const TimedSafetySnapshot& s, std::uint64_t nowUs) noexcept {
    SubmitResult out;
    out.status = prepare(s, nowUs);
    if (!out.status.accepted()) return out;
    if (out.status.requirePhysicalKill) {
        out.status = result({DispatchFault::SafetyDenied});
        return out;
    }
    if (!events || count == 0 || count > MaxScheduleEvents) {
        out.status = result({DispatchFault::InvalidBatch});
        return out;
    }
    std::array<DiEvent, MaxScheduleEvents> all{};
    const auto retained = retainedEvents(all);
    if (count > MaxScheduleEvents - retained) {
        out.status = result({DispatchFault::CapacityExceeded});
        return out;
    }
    for (std::size_t i = 0; i < count; ++i) all[retained + i] = events[i];
    const auto admission = admitDiSchedule(qualification_, all.data(), retained + count);
    if (!admission.accepted()) {
        out.status = result(admissionDiagnostic(admission));
        return out;
    }
    for (std::size_t i = 0; i < count; ++i) {
        if (events[i].start < nowUs) {
            out.status = result({DispatchFault::StartInPast, AdmissionFault::None, GdiFault::None, i});
            return out;
        }
    }
    if (ticketIdsExhausted_ || count - 1 > std::numeric_limits<std::uint64_t>::max() - nextTicketId_) {
        out.status = result({DispatchFault::TicketExhausted});
        return out;
    }
    // Everything above is read-only w.r.t. batch acceptance. Only now reserve
    // all entries and IDs. No failure path or external callback during commit.
    std::size_t slot = 0;
    for (std::size_t i = 0; i < count; ++i) {
        while (reservations_[slot].state != ReservationState::Empty) ++slot;
        reservations_[slot] = {events[i], nextTicketId_, events[i].demagEnd + qualification_.guardUs,
                               ReservationState::Queued};
        out.tickets[i].owner_ = this;
        out.tickets[i].id_ = nextTicketId_;
        if (nextTicketId_ == std::numeric_limits<std::uint64_t>::max()) ticketIdsExhausted_ = true;
        else ++nextTicketId_;
        ++slot;
    }
    out.count = count;
    return out;
}

std::size_t Gdi6DispatchGuard::ticketSlot(const EventTicket& ticket) const noexcept {
    if (ticket.owner_ != this || ticket.id_ == 0) return MaxScheduleEvents;
    for (std::size_t i = 0; i < reservations_.size(); ++i) {
        if (reservations_[i].state != ReservationState::Empty &&
            reservations_[i].ticketId == ticket.id_) return i;
    }
    return MaxScheduleEvents;
}

DispatchResult Gdi6DispatchGuard::dispatch(const EventTicket* tickets, std::size_t count,
                                         const TimedSafetySnapshot& s, std::uint64_t nowUs) noexcept {
    DispatchResult out;
    out.status = prepare(s, nowUs);
    if (!out.status.accepted()) return out;
    if (out.status.requirePhysicalKill) {
        out.status = result({DispatchFault::SafetyDenied});
        return out;
    }
    if (!tickets || count == 0 || count > MaxScheduleEvents) {
        out.status = result({DispatchFault::InvalidBatch});
        return out;
    }
    std::array<std::size_t, MaxScheduleEvents> slots{};
    for (std::size_t i = 0; i < count; ++i) {
        slots[i] = ticketSlot(tickets[i]);
        if (slots[i] == MaxScheduleEvents) {
            out.status = result({DispatchFault::InvalidTicket, AdmissionFault::None,
                                 GdiFault::None, i, MaxScheduleEvents, tickets[i].id()});
            return out;
        }
        for (std::size_t j = 0; j < i; ++j) {
            if (slots[i] == slots[j]) {
                out.status = result({DispatchFault::DuplicateTicket, AdmissionFault::None,
                                     GdiFault::None, j, i, tickets[i].id()});
                return out;
            }
        }
        const auto& r = reservations_[slots[i]];
        if (r.state == ReservationState::Started) {
            out.status = result({DispatchFault::TicketConsumed, AdmissionFault::None,
                                 GdiFault::None, i, MaxScheduleEvents, r.ticketId});
            return out;
        }
        if (nowUs < r.event.start) {
            out.status = result({DispatchFault::TooEarly, AdmissionFault::None,
                                 GdiFault::None, i, MaxScheduleEvents, r.ticketId});
            return out;
        }
        // prepare latched/cancelled any queued event with start < nowUs.
    }
    std::array<DiEvent, MaxScheduleEvents> all{};
    const auto retained = retainedEvents(all);
    const auto admission = admitDiSchedule(qualification_, all.data(), retained);
    if (!admission.accepted()) {
        out.status = trip(admissionDiagnostic(admission));
        return out;
    }
    for (std::size_t i = 0; i < count; ++i) {
        auto& r = reservations_[slots[i]];
        r.state = ReservationState::Started; // Consume BEFORE returning permission.
        out.events[i] = r.event;
    }
    out.count = count;
    return out;
}

DispatchGuardResult Gdi6DispatchGuard::observe(const TimedSafetySnapshot& s,
                                              std::uint64_t nowUs) noexcept {
    return prepare(s, nowUs);
}

DispatchGuardResult Gdi6DispatchGuard::stop(const TimedSafetySnapshot& s,
                                           std::uint64_t nowUs) noexcept {
    const auto checked = prepare(s, nowUs);
    if (!checked.accepted()) return checked;
    if (s.safety.runRequested) return trip({DispatchFault::InvalidStopRequest});
    return checked;
}

DispatchGuardResult Gdi6DispatchGuard::acknowledgeStopped(const TimedSafetySnapshot& s,
                                                        std::uint64_t nowUs) noexcept {
    const auto checked = validateObservation(s, nowUs);
    if (!checked.accepted()) return checked;
    if (firstFault_.fault == DispatchFault::None) return result({DispatchFault::RecoveryDenied});
    if (!healthyStandstill(s.safety) ||
        (configurationLocked_ && startedCount() != 0 && !sameConfiguration(s))) {
        recoveryAfterUs_ = lastNowUs_;
        return result({DispatchFault::RecoveryDenied});
    }
    // A merely old but otherwise healthy proof must not move its own target:
    // lagging coherent samples could otherwise never catch the recovery barrier.
    if (s.capturedAtUs <= recoveryAfterUs_ || !safety_.acknowledgeStopped(s.safety))
        return result({DispatchFault::RecoveryDenied});
    firstFault_ = {};
    cancelQueued();
    if (startedCount() == 0) configurationLocked_ = false;
    return result(); // Still disarmed. A later fresh run request is required.
}

} // namespace power6gdi
