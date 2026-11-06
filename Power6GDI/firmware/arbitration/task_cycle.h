#pragma once

// Fixed-order engine task cycle (host-testable, no RTOS/timer calls).
//
// One call of runCycle() is one control cycle:
//   1. the accumulator is reset;
//   2. tasks run strictly in registration order: update() only in the slots
//      assigned to the task, contribute() EVERY cycle;
//   3. the slot counter advances (KSlots slots per full period).
//
// Final stages (ignition angle, fuel, cylinder cut) are registered with
// isFinal = true and must come after every contributing task; add() rejects
// a contributing task registered after a final one, so the "all requests are
// in before anybody reads the result" rule cannot be broken by accident.
// Within the same cycle a request made by any task is therefore visible to
// all final stages. For the cylinder cut, registration order is also the
// tie-break priority (see InterventionAccumulator::requestCylinderCut).

#include <cstdint>

#include "intervention_accumulator.h"

namespace power8gdi {

using TaskUpdateFn = void (*)(void* context);
using TaskContributeFn = void (*)(void* context, InterventionAccumulator& acc);

struct TaskSpec {
    const char* name = "";
    std::uint8_t updatesPerPeriod = 1;   // must divide kSlots: 1, 2, 4, 5, 10, 20
    TaskUpdateFn update = nullptr;       // optional
    TaskContributeFn contribute = nullptr;  // optional
    void* context = nullptr;
    bool isFinal = false;
};

enum class AddResult : std::uint8_t { Ok = 0, Full, BadRate, OrderViolation, Frozen, Empty };

class TaskCycle {
public:
    static constexpr std::uint8_t kSlots = 20;
    static constexpr std::uint8_t kMaxTasks = 40;

    AddResult add(const TaskSpec& spec);
    void freeze() { frozen_ = true; }   // call when registration is complete
    bool frozen() const { return frozen_; }

    void runCycle(InterventionAccumulator& acc);

    std::uint8_t taskCount() const { return count_; }
    std::uint8_t currentSlot() const { return slot_; }
    std::uint32_t slotMask(std::uint8_t task) const;      // bit n = update runs in slot n
    std::uint8_t updatesInSlot(std::uint8_t slot) const;  // scheduled update() calls
    const char* taskName(std::uint8_t task) const;

private:
    struct Entry {
        TaskSpec spec;
        std::uint32_t mask;
    };

    Entry tasks_[kMaxTasks] = {};
    std::uint8_t load_[kSlots] = {};
    std::uint8_t count_ = 0;
    std::uint8_t slot_ = 0;
    bool finalSeen_ = false;
    bool frozen_ = false;
};

} // namespace power8gdi
