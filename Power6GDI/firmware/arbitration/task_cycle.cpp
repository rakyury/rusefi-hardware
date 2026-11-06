#include "task_cycle.h"

namespace power8gdi {

AddResult TaskCycle::add(const TaskSpec& spec) {
    if (frozen_) {
        return AddResult::Frozen;
    }
    if (count_ >= kMaxTasks) {
        return AddResult::Full;
    }
    const std::uint8_t rate = spec.updatesPerPeriod;
    if (rate == 0 || rate > kSlots || kSlots % rate != 0) {
        return AddResult::BadRate;
    }
    if (spec.update == nullptr && spec.contribute == nullptr) {
        return AddResult::Empty;
    }
    if (finalSeen_ && !spec.isFinal) {
        return AddResult::OrderViolation;
    }

    // Spread update() calls: the task runs every `interval` slots starting at
    // the phase whose busiest slot is the least loaded (lowest phase on a tie).
    const std::uint8_t interval = kSlots / rate;
    std::uint8_t bestPhase = 0;
    std::uint8_t bestPeak = 0xFF;
    for (std::uint8_t phase = 0; phase < interval; phase++) {
        std::uint8_t peak = 0;
        for (std::uint8_t s = phase; s < kSlots; s += interval) {
            if (load_[s] > peak) {
                peak = load_[s];
            }
        }
        if (peak < bestPeak) {
            bestPeak = peak;
            bestPhase = phase;
        }
    }

    std::uint32_t mask = 0;
    if (spec.update != nullptr) {
        for (std::uint8_t s = bestPhase; s < kSlots; s += interval) {
            mask |= 1u << s;
            load_[s]++;
        }
    }

    tasks_[count_++] = Entry{spec, mask};
    finalSeen_ = finalSeen_ || spec.isFinal;
    return AddResult::Ok;
}

void TaskCycle::runCycle(InterventionAccumulator& acc) {
    acc.reset();
    const std::uint32_t bit = 1u << slot_;
    for (std::uint8_t i = 0; i < count_; i++) {
        const Entry& e = tasks_[i];
        if ((e.mask & bit) != 0) {
            e.spec.update(e.spec.context);
        }
        if (e.spec.contribute != nullptr) {
            e.spec.contribute(e.spec.context, acc);
        }
    }
    slot_ = static_cast<std::uint8_t>((slot_ + 1) % kSlots);
}

std::uint32_t TaskCycle::slotMask(std::uint8_t task) const {
    return task < count_ ? tasks_[task].mask : 0;
}

std::uint8_t TaskCycle::updatesInSlot(std::uint8_t slot) const {
    return slot < kSlots ? load_[slot] : 0;
}

const char* TaskCycle::taskName(std::uint8_t task) const {
    return task < count_ ? tasks_[task].spec.name : "";
}

} // namespace power8gdi
