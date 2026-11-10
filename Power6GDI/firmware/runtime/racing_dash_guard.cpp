#include "racing_dash_guard.h"
#include <cstring>

namespace power6gdi::racingdash {
namespace {
GuardResult fail(GuardFault fault, std::size_t pc = 0) noexcept {
    return {fault, static_cast<std::uint16_t>(pc), 0, 0};
}
bool domainValid(ValueDomain d) noexcept {
    if (d.min > d.max) return false;
    switch (d.type) {
        case ValueType::Integer: return true;
        case ValueType::Boolean: return d.min >= 0 && d.max <= 1;
        case ValueType::State: return d.min >= 0 && d.max <= 255;
        default: return false;
    }
}
bool schemaValid(const InputSpec* inputs, std::size_t count) noexcept {
    if (count > MaxInputs || (count && !inputs)) return false;
    for (std::size_t i = 0; i < count; ++i) {
        if (inputs[i].id < 100 || inputs[i].id >= CH_PEAK_SRC_LIMIT ||
            !domainValid(inputs[i].domain) || inputs[i].maxAgeMs == 0 ||
            inputs[i].maxAgeMs > 0x7fffffffU) return false;
        for (std::size_t j = 0; j < i; ++j)
            if (inputs[j].id == inputs[i].id) return false;
    }
    return true;
}
GuardFault sampleFault(const InputSpec& spec, const InputSample& sample,
                       std::uint32_t now) noexcept {
    if (sample.id != spec.id || !sample.valid) return GuardFault::InputInvalid;
    // Unsigned subtraction accepts timestamp rollover but rejects future and
    // ambiguously old values; validity must also be cleared across ECU reset.
    if (now - sample.timestampMs > spec.maxAgeMs) return GuardFault::InputStale;
    if (sample.value < spec.domain.min || sample.value > spec.domain.max)
        return GuardFault::InputRange;
    return GuardFault::None;
}
std::int32_t literal32(const std::uint8_t* code) noexcept {
    const std::uint32_t bits = std::uint32_t(code[0]) | (std::uint32_t(code[1]) << 8) |
        (std::uint32_t(code[2]) << 16) | (std::uint32_t(code[3]) << 24);
    std::int32_t result;
    std::memcpy(&result, &bits, sizeof(result));
    return result;
}
} // namespace

GuardResult Expression::load(const std::uint8_t* code, std::size_t length,
                             const InputSpec* inputs, std::size_t count,
                             ValueDomain output) noexcept {
    loaded_ = false; // Failed replacement MUST NOT retain an executable old tune.
    used_.fill(false);
    if (!schemaValid(inputs, count) || !domainValid(output))
        return fail(GuardFault::InvalidSchema);
    if (!code || length == 0 || length > MaxExpressionBytes)
        return fail(GuardFault::InvalidLength);
    // Literal provenance only, not a second evaluator: used to admit nonzero
    // fixed divisors and bounded literal lerp weights. Other results unknown.
    struct Literal { bool known = false; std::int32_t value = 0; };
    std::array<Literal, MaxExpressionStack> stack{};
    unsigned depth = 0, ops = 0;
    bool ended = false;
    for (std::size_t pc = 0; pc < length;) {
        const auto at = pc;
        const auto opcode = code[pc++];
        if (++ops > MaxExpressionOps) return fail(GuardFault::OperationBudget, at);
        unsigned pop = 0, push = 0;
        Literal result{};
        switch (opcode) {
            case OP_END:
                if (depth != 1) return fail(GuardFault::InvalidResultStack, at);
                if (pc != length) return fail(GuardFault::TrailingBytes, at);
                ended = true;
                break;
            case OP_NOP: break;
            case OP_PUSH_CONST:
                if (length - pc < 4) return fail(GuardFault::TruncatedOperand, at);
                result = {true, literal32(code + pc)};
                pc += 4; push = 1; break;
            case OP_PUSH_CH: {
                if (length - pc < 2) return fail(GuardFault::TruncatedOperand, at);
                const unsigned id = code[pc] | (unsigned(code[pc + 1]) << 8);
                pc += 2;
                std::size_t i = 0;
                for (; i < count && inputs[i].id != id; ++i) {}
                if (i == count) return fail(GuardFault::UnknownInput, at);
                used_[i] = true; push = 1; break;
            }
            case OP_POP: pop = 1; break;
            case OP_DUP:
                if (!depth) return fail(GuardFault::StackUnderflow, at);
                result = stack[depth - 1]; push = 1; break;
            case OP_SWAP:
                if (depth < 2) return fail(GuardFault::StackUnderflow, at);
                result = stack[depth - 1]; stack[depth - 1] = stack[depth - 2];
                stack[depth - 2] = result; break;
            case OP_ROT:
                if (depth < 3) return fail(GuardFault::StackUnderflow, at);
                result = stack[depth - 3]; stack[depth - 3] = stack[depth - 2];
                stack[depth - 2] = stack[depth - 1]; stack[depth - 1] = result; break;
            case OP_NEG:
                if (!depth) return fail(GuardFault::StackUnderflow, at);
                result = stack[depth - 1];
                if (result.known) {
                    const std::uint32_t neg = 0U - static_cast<std::uint32_t>(result.value);
                    std::memcpy(&result.value, &neg, sizeof(neg));
                }
                pop = push = 1; break;
            case OP_ABS: case OP_SIGN: case OP_NOT: case OP_LNOT:
                pop = push = 1; break;
            case OP_DIV: case OP_MOD:
                if (depth < 2) return fail(GuardFault::StackUnderflow, at);
                if (!stack[depth - 1].known || stack[depth - 1].value == 0)
                    return fail(GuardFault::DynamicDivisor, at);
                pop = 2; push = 1; break;
            case OP_ADD: case OP_SUB: case OP_MUL:
            case OP_AND: case OP_OR: case OP_XOR: case OP_SHL: case OP_SHR:
            case OP_EQ: case OP_NE: case OP_LT: case OP_LE: case OP_GT: case OP_GE:
            case OP_LAND: case OP_LOR: case OP_MIN: case OP_MAX:
                pop = 2; push = 1; break;
            case OP_LERP:
                if (depth < 3) return fail(GuardFault::StackUnderflow, at);
                if (!stack[depth - 1].known || stack[depth - 1].value < 0 ||
                    stack[depth - 1].value > 1000)
                    return fail(GuardFault::InvalidLerpWeight, at);
                pop = 3; push = 1; break;
            case OP_CLAMP: case OP_IF: pop = 3; push = 1; break;
            case OP_STORE_CH: case OP_STORE_IDX: case OP_LOAD_IDX:
                return fail(GuardFault::ForbiddenOpcode, at);
            // MAP, SWITCH and stub table/timer/filter ops remain unadmitted.
            default: return fail(GuardFault::UnsupportedOpcode, at);
        }
        if (depth < pop) return fail(GuardFault::StackUnderflow, at);
        depth -= pop;
        if (depth + push > MaxExpressionStack) return fail(GuardFault::StackOverflow, at);
        if (push) stack[depth++] = result;
    }
    if (!ended) return fail(GuardFault::MissingEnd, length);
    inputCount_ = count; length_ = static_cast<std::uint16_t>(length);
    operations_ = ops; output_ = output;
    std::memcpy(code_.data(), code, length);
    Channel_Init(&channels_);
    for (std::size_t i = 0; i < count; ++i) {
        inputs_[i] = inputs[i];
        Channel_Register(&channels_, inputs[i].id, CH_TYPE_NUMBER, CH_CLASS_INPUT, nullptr);
    }
    VM_Init(&vm_, &channels_);
    loaded_ = true;
    return {GuardFault::None, 0, 0, ops};
}

GuardResult Expression::run(const InputSample* samples, std::size_t count,
                            std::uint32_t nowMs) noexcept {
    if (!loaded_) return fail(GuardFault::NotLoaded);
    if (count != inputCount_ || (count && !samples)) return fail(GuardFault::InputInvalid);
    for (std::size_t i = 0; i < count; ++i) {
        if (samples[i].id != inputs_[i].id) return fail(GuardFault::InputInvalid);
        if (!used_[i]) continue;
        const auto fault = sampleFault(inputs_[i], samples[i], nowMs);
        if (fault != GuardFault::None) return fail(fault);
    }
    channels_.current_tick = nowMs;
    for (std::size_t i = 0; i < count; ++i)
        if (used_[i]) Channel_SetValueWithTick(&channels_, inputs_[i].id,
                                             samples[i].value, samples[i].timestampMs);
    const std::int32_t result = VM_Execute(&vm_, code_.data(), length_);
    if (result < output_.min || result > output_.max) return fail(GuardFault::OutputRange);
    return {GuardFault::None, 0, result, operations_};
}

GuardResult validateCanTx(const CanTxConfig_t& c, const InputSpec* inputs,
                          const InputSample* samples, std::size_t count,
                          std::uint32_t nowMs) noexcept {
    if (!schemaValid(inputs, count) || (count && !samples)) return fail(GuardFault::InvalidSchema);
    if (c.bus > 1 || c.is_extended > 1 || c.dlc == 0 || c.dlc > 8 ||
        c.can_id > (c.is_extended ? 0x1fffffffU : 0x7ffU) ||
        c.mode != CAN_TX_PERIODIC || c.flags != CAN_TX_FLAG_ENABLED ||
        c.interval_ms == 0 || c.signal_count == 0 || c.signal_count > CAN_TX_MAX_SIGNALS)
        return fail(GuardFault::InvalidCanConfig);
    std::uint64_t occupied = 0;
    for (unsigned i = 0; i < c.signal_count; ++i) {
        const auto& s = c.signals[i];
        if (s.byte_order != CAN_BYTE_ORDER_LE || s.signal_type > CAN_SIGNAL_SIGNED ||
            s.bit_length == 0 || s.bit_length > 32 ||
            unsigned(s.start_bit) + s.bit_length > unsigned(c.dlc) * 8 ||
            s.scale_num <= 0 || s.scale_den <= 0) return fail(GuardFault::InvalidCanConfig);
        const std::uint64_t mask = ((std::uint64_t{1} << s.bit_length) - 1) << s.start_bit;
        if (mask & occupied) return fail(GuardFault::InvalidCanConfig);
        occupied |= mask;
        std::size_t index = 0;
        for (; index < count && inputs[index].id != s.source_channel; ++index) {}
        if (index == count) return fail(GuardFault::UnknownInput);
        const auto fault = sampleFault(inputs[index], samples[index], nowMs);
        if (fault != GuardFault::None) return fail(fault);
        const std::int64_t value = (std::int64_t(samples[index].value) * s.scale_den) /
                                   s.scale_num - s.offset;
        const std::int64_t min = s.signal_type == CAN_SIGNAL_SIGNED ?
            -(std::int64_t{1} << (s.bit_length - 1)) : 0;
        const std::int64_t max = s.signal_type == CAN_SIGNAL_SIGNED ?
            (std::int64_t{1} << (s.bit_length - 1)) - 1 :
            (std::int64_t{1} << s.bit_length) - 1;
        if (value < min || value > max) return fail(GuardFault::CanSignalRange);
    }
    return {GuardFault::None, 0, 0, 0};
}
} // namespace power6gdi::racingdash
