#pragma once

// Bounded host integration of the pinned RacingDash C engine. No GPIO, CAN HAL,
// event scheduling, graph execution or engine-control output authority here.
#include "../vendor/racing_dash/shared/vm/vm.h"
#include "../vendor/racing_dash/shared/can_tx/can_tx.h"
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace power6gdi::racingdash {

inline constexpr std::size_t MaxInputs = 32;
inline constexpr std::size_t MaxExpressionBytes = 512;
inline constexpr unsigned MaxExpressionOps = 128;
inline constexpr unsigned MaxExpressionStack = 32;

enum class ValueType : std::uint8_t { Integer, Boolean, State };
struct ValueDomain {
    ValueType type = ValueType::Integer;
    std::int32_t min = std::numeric_limits<std::int32_t>::min();
    std::int32_t max = std::numeric_limits<std::int32_t>::max();
};
struct InputSpec {
    std::uint16_t id = 0; // 100..8191 only; no implicit system or peak channels.
    ValueDomain domain{}; // Explicit scaled int32; units/scales belong to schema.
    std::uint32_t maxAgeMs = 0; // Required, 1..INT32_MAX; no never-stale default.
};
struct InputSample {
    std::uint16_t id = 0;
    std::int32_t value = 0;
    std::uint32_t timestampMs = 0;
    bool valid = false; // Preview seed, unreceived and fault values must be false.
};
enum class GuardFault : std::uint8_t {
    None, NotLoaded, InvalidSchema, InvalidLength, TruncatedOperand,
    UnsupportedOpcode, ForbiddenOpcode, StackUnderflow, StackOverflow,
    OperationBudget, MissingEnd, InvalidResultStack, TrailingBytes,
    UnknownInput, DynamicDivisor, InvalidLerpWeight, InputInvalid,
    InputStale, InputRange, OutputRange, InvalidCanConfig, CanSignalRange,
};
struct GuardResult {
    GuardFault fault = GuardFault::NotLoaded;
    std::uint16_t offset = 0; // Byte offset for admission errors.
    std::int32_t value = 0;   // Zero on EVERY failure, never previous result.
    unsigned operations = 0;
    bool ok() const noexcept { return fault == GuardFault::None; }
};

// Owns immutable admitted code and its input schema; no external mutable VM
// handle. One instance runs one pure expression. Not thread/ISR safe: the caller
// owns coherent snapshots and serializes load/run. Place in static/storage
// memory, not a small MCU task stack; the unmodified vendor contexts are large.
class Expression {
public:
    Expression() = default;
    Expression(const Expression&) = delete;
    Expression& operator=(const Expression&) = delete;
    Expression(Expression&&) = delete;
    Expression& operator=(Expression&&) = delete;
    GuardResult load(const std::uint8_t* code, std::size_t length,
                     const InputSpec* inputs, std::size_t inputCount,
                     ValueDomain output) noexcept;
    GuardResult run(const InputSample* samples, std::size_t sampleCount,
                    std::uint32_t nowMs) noexcept;
private:
    bool loaded_ = false;
    std::size_t inputCount_ = 0;
    std::uint16_t length_ = 0;
    unsigned operations_ = 0;
    ValueDomain output_{};
    std::array<InputSpec, MaxInputs> inputs_{};
    std::array<bool, MaxInputs> used_{};
    std::array<std::uint8_t, MaxExpressionBytes> code_{};
    ChannelEngine_t channels_{};
    VM_t vm_{};
};

// Admission check for the current snapshot BEFORE invoking the native CAN TX
// packer. Initial subset: periodic classical CAN, Intel, signed/unsigned integer
// signals. Uses RacingDash's exact offset-after-inverse-scale semantics (NOT a
// claim of arbitrary DBC compatibility). Does not send or queue frames. Recheck
// each snapshot; passing once is not permission to send stale data later.
GuardResult validateCanTx(const CanTxConfig_t& config, const InputSpec* inputs,
                          const InputSample* samples, std::size_t count,
                          std::uint32_t nowMs) noexcept;

} // namespace power6gdi::racingdash
