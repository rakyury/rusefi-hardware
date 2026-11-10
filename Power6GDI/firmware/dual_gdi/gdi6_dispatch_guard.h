#pragma once

#include "dual_pt2001_safety.h"
#include "gdi6_schedule_admission.h"
#include <array>
#include <cstddef>
#include <cstdint>

namespace power6gdi {

// Host-verifiable output-boundary policy. One serialized owner, no GPIO/ISR API.
// A coherent copy is captured upstream; each individual diagnostic must also be
// fresh. configurationRevision covers PT current/phase settings and calibration.
struct TimedSafetySnapshot {
    power8gdi::GdiSafetySnapshot safety{};
    std::uint64_t capturedAtUs = 0;
    std::uint64_t configurationRevision = 0; // Zero is not a configured revision.
};

struct DispatchGuardConfig {
    std::uint64_t maxSnapshotAgeUs = 0; // Must be positive; immutable after construction.
    std::uint64_t initialTicketId = 1; // Constructor-only overflow test seam; zero invalid.
};

class Gdi6DispatchGuard;
class EventTicket final {
public:
    constexpr EventTicket() noexcept = default;
    std::uint64_t id() const noexcept { return id_; }
private:
    friend class Gdi6DispatchGuard;
    const Gdi6DispatchGuard* owner_ = nullptr;
    std::uint64_t id_ = 0;
};

enum class DispatchFault : std::uint8_t {
    None, InvalidConfiguration, Unqualified, FutureSnapshot, StaleSnapshot,
    ClockRollback, SnapshotRollback, UnsupportedProfile, IncoherentSnapshot, ConfigurationChanged,
    SafetyDenied, InvalidBatch, CapacityExceeded, ScheduleRejected, StartInPast,
    TicketExhausted, InvalidTicket, DuplicateTicket, TicketConsumed, TooEarly,
    MissedDispatch, InvalidStopRequest, RecoveryDenied
};

struct DispatchDiagnostic {
    DispatchFault fault = DispatchFault::None;
    AdmissionFault admission = AdmissionFault::None;
    power8gdi::GdiFault safety = power8gdi::GdiFault::None;
    // Admission indices refer to retained slots in slot order, then new events.
    // Ticket-batch errors use indices into the supplied ticket batch.
    std::size_t first = MaxScheduleEvents, second = MaxScheduleEvents;
    std::uint64_t ticketId = 0;
};

struct DispatchGuardResult {
    DispatchDiagnostic diagnostic{};
    power8gdi::GdiState state = power8gdi::GdiState::Disarmed;
    // An obligation for the caller, not evidence that hardware was disabled.
    bool requirePhysicalKill = true;
    bool accepted() const noexcept { return diagnostic.fault == DispatchFault::None; }
};

struct SubmitResult {
    DispatchGuardResult status{};
    std::array<EventTicket, MaxScheduleEvents> tickets{};
    std::size_t count = 0;
};

struct DispatchResult {
    DispatchGuardResult status{};
    // Nonempty only after an atomic, one-time permit. Entries correspond to the
    // supplied tickets. Caller must act at this same instant or physically kill.
    std::array<DiEvent, MaxScheduleEvents> events{};
    std::size_t count = 0;
};

class Gdi6DispatchGuard final {
public:
    explicit Gdi6DispatchGuard(DispatchGuardConfig config,
                              ScheduleQualification qualification = {}) noexcept;
    Gdi6DispatchGuard(const Gdi6DispatchGuard&) = delete;
    Gdi6DispatchGuard& operator=(const Gdi6DispatchGuard&) = delete;
    Gdi6DispatchGuard(Gdi6DispatchGuard&&) = delete;
    Gdi6DispatchGuard& operator=(Gdi6DispatchGuard&&) = delete;

    SubmitResult submit(const DiEvent* events, std::size_t count,
                        const TimedSafetySnapshot& snapshot, std::uint64_t nowUs) noexcept;
    DispatchResult dispatch(const EventTicket* tickets, std::size_t count,
                            const TimedSafetySnapshot& snapshot, std::uint64_t nowUs) noexcept;
    DispatchGuardResult observe(const TimedSafetySnapshot& snapshot, std::uint64_t nowUs) noexcept;
    // stop requires runRequested=false. Pending entries are cancelled; started
    // entries remain reserved. observe with runRequested=false has the same effect.
    DispatchGuardResult stop(const TimedSafetySnapshot& snapshot, std::uint64_t nowUs) noexcept;
    DispatchGuardResult acknowledgeStopped(const TimedSafetySnapshot& snapshot,
                                          std::uint64_t nowUs) noexcept;

    std::size_t queuedCount() const noexcept;
    std::size_t startedCount() const noexcept;
    DispatchDiagnostic firstFault() const noexcept { return firstFault_; }

private:
    enum class ReservationState : std::uint8_t { Empty, Queued, Started };
    struct Reservation {
        DiEvent event{};
        std::uint64_t ticketId = 0, releaseAtUs = 0;
        ReservationState state = ReservationState::Empty;
    };
    const DispatchGuardConfig config_;
    const ScheduleQualification qualification_;
    power8gdi::DualPt2001Safety safety_{};
    std::array<Reservation, MaxScheduleEvents> reservations_{};
    DispatchDiagnostic firstFault_{};
    power8gdi::GdiSafetySnapshot sessionConfiguration_{};
    std::uint64_t sessionRevision_ = 0, nextTicketId_ = 1, lastNowUs_ = 0;
    std::uint64_t lastCapturedAtUs_ = 0, lastArmedAtUs_ = 0, recoveryAfterUs_ = 0;
    bool ticketIdsExhausted_ = false, clockSeen_ = false, captureSeen_ = false;
    bool configurationLocked_ = false;

    DispatchGuardResult result(DispatchDiagnostic diagnostic = {}) const noexcept;
    DispatchGuardResult trip(DispatchDiagnostic diagnostic) noexcept;
    DispatchGuardResult validateObservation(const TimedSafetySnapshot& snapshot,
                                           std::uint64_t nowUs) noexcept;
    DispatchGuardResult prepare(const TimedSafetySnapshot& snapshot, std::uint64_t nowUs) noexcept;
    void cancelQueued() noexcept;
    void releaseStarted(std::uint64_t nowUs) noexcept;
    bool sameConfiguration(const TimedSafetySnapshot& snapshot) const noexcept;
    std::size_t retainedEvents(std::array<DiEvent, MaxScheduleEvents>& events) const noexcept;
    std::size_t ticketSlot(const EventTicket& ticket) const noexcept;
};

} // namespace power6gdi
