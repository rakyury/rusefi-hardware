#include "../runtime/racing_dash_guard.h"
#include "racing_dash_vectors.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <type_traits>
#include <vector>

using namespace power6gdi::racingdash;
static_assert(!std::is_copy_constructible_v<Expression> && !std::is_move_constructible_v<Expression>,
              "Native context pointers must remain bound to their owning expression");
namespace {
Expression guarded; // Vendor contexts intentionally outside the call stack.
ChannelEngine_t nativeChannels;
VM_t nativeVm;
CanTxManager_t nativeCan;
InputSpec inputs[] = {{100, {}, 20}, {101, {}, 20}};
InputSample samples[] = {{100, 6000, 90, true}, {101, 150, 90, true}};
void constant(std::vector<std::uint8_t>& code, std::int32_t value) {
    code.push_back(OP_PUSH_CONST);
    for (unsigned shift = 0; shift < 32; shift += 8)
        code.push_back(static_cast<std::uint8_t>(static_cast<std::uint32_t>(value) >> shift));
}
GuardResult load(const std::vector<std::uint8_t>& code, ValueDomain output = {}) {
    return guarded.load(code.data(), code.size(), inputs, 2, output);
}
void fault(GuardResult result, GuardFault expected) {
    assert(result.fault == expected && result.value == 0 && !result.ok());
}
unsigned sends = 0;
std::uint8_t sentBus = 0, sentDlc = 0;
std::uint32_t sentId = 0;
bool sentExtended = false;
std::uint8_t sentBytes[8]{};
void capture(std::uint8_t bus, std::uint32_t id, bool extended,
             const std::uint8_t* bytes, std::uint8_t len) {
    ++sends; sentBus = bus; sentId = id; sentDlc = len; sentExtended = extended;
    assert(len <= 8);
    std::memcpy(sentBytes, bytes, len);
}
CanTxConfig_t config() {
    auto result = CanTx_CreatePeriodic(1, 0x321, 0, 100, "test");
    result.dlc = 4;
    CanTx_AddSignal(&result, 100, 0, 16, 4, 1, 0);
    CanTx_AddSignal(&result, 101, 16, 16, 1, 1, 0);
    result.signals[1].signal_type = CAN_SIGNAL_SIGNED;
    return result;
}
GuardResult validate(const CanTxConfig_t& c) {
    return validateCanTx(c, inputs, samples, 2, 100);
}
} // namespace

int main() {
    // Bytecode produced by the actual pinned RacingDash ExprCompiler, not a
    // rewritten compiler. Expected values are explicit independent vectors.
    for (const auto& v : fixtures) {
        samples[0] = {100, v.a, 90, true}; samples[1] = {101, v.b, 90, true};
        auto admitted = guarded.load(v.code, v.length, inputs, 2, {});
        assert(admitted.ok());
        const auto result = guarded.run(samples, 2, 100);
        assert(result.ok() && result.value == v.expected);
        assert(result.operations <= MaxExpressionOps);
        Channel_Init(&nativeChannels);
        for (const auto& s : samples) {
            Channel_Register(&nativeChannels, s.id, CH_TYPE_NUMBER, CH_CLASS_INPUT, nullptr);
            Channel_SetValue(&nativeChannels, s.id, s.value);
        }
        VM_Init(&nativeVm, &nativeChannels);
        assert(VM_Execute(&nativeVm, v.code, v.length) == v.expected);
        // Every strict prefix is an incomplete expression, never executable.
        for (std::size_t cut = 0; cut < v.length; ++cut)
            assert(!guarded.load(v.code, cut, inputs, 2, {}).ok());
    }
    std::vector<std::uint8_t> read = {OP_PUSH_CH, 100, 0, OP_END};
    assert(load(read).ok());
    samples[0] = {100, 12, 90, true}; samples[1] = {101, 0, 0, false};
    assert(guarded.run(samples, 2, 100).value == 12); // unused input may be invalid
    samples[0].valid = false;
    fault(guarded.run(samples, 2, 100), GuardFault::InputInvalid);
    samples[0].valid = true; samples[0].timestampMs = 79;
    fault(guarded.run(samples, 2, 100), GuardFault::InputStale);
    samples[0].timestampMs = 101;
    fault(guarded.run(samples, 2, 100), GuardFault::InputStale);
    samples[0].timestampMs = 0xfffffffau;
    assert(guarded.run(samples, 2, 5).ok()); // 11ms across uint32 rollover
    samples[0] = {100, 12, 90, true};
    fault(guarded.run(samples, 1, 100), GuardFault::InputInvalid);
    fault(guarded.run(nullptr, 2, 100), GuardFault::InputInvalid);
    samples[0].id = 101;
    fault(guarded.run(samples, 2, 100), GuardFault::InputInvalid);
    samples[0].id = 100;
    assert(load(read, {ValueType::Boolean, 0, 1}).ok());
    fault(guarded.run(samples, 2, 100), GuardFault::OutputRange);
    inputs[0].domain = {ValueType::Boolean, 0, 1};
    assert(load(read).ok());
    fault(guarded.run(samples, 2, 100), GuardFault::InputRange);
    inputs[0].domain = {};
    inputs[0].maxAgeMs = 0;
    fault(load(read), GuardFault::InvalidSchema);
    fault(guarded.run(samples, 2, 100), GuardFault::NotLoaded);
    inputs[0].maxAgeMs = 20;
    inputs[1].id = 100;
    fault(load(read), GuardFault::InvalidSchema);
    inputs[1].id = 101;
    fault(load(read, {static_cast<ValueType>(99), 0, 1}), GuardFault::InvalidSchema);
    auto unknown = read; unknown[1] = 102;
    fault(load(unknown), GuardFault::UnknownInput);
    fault(load({OP_PUSH_CONST, 1, 2, 3}), GuardFault::TruncatedOperand);
    fault(load({OP_PUSH_CH, 100}), GuardFault::TruncatedOperand);
    fault(load({OP_ADD, OP_END}), GuardFault::StackUnderflow);
    fault(load({OP_DUP, OP_END}), GuardFault::StackUnderflow);
    fault(load({OP_END}), GuardFault::InvalidResultStack);
    auto trailing = read; trailing.push_back(OP_NOP);
    fault(load(trailing), GuardFault::TrailingBytes);
    auto noEnd = read; noEnd.pop_back();
    fault(load(noEnd), GuardFault::MissingEnd);
    for (auto opcode : {OP_TABLE_2D, OP_TABLE_3D, OP_TIMER_VAL, OP_FILTER_VAL, OP_MAP, OP_SWITCH})
        fault(load({static_cast<std::uint8_t>(opcode), 0, 0, OP_END}), GuardFault::UnsupportedOpcode);
    for (auto opcode : {OP_STORE_CH, OP_STORE_IDX, OP_LOAD_IDX})
        fault(load({static_cast<std::uint8_t>(opcode), 0, 0, OP_END}), GuardFault::ForbiddenOpcode);
    auto divide = noEnd;
    divide.insert(divide.end(), {OP_PUSH_CH, 101, 0, OP_DIV, OP_END});
    fault(load(divide), GuardFault::DynamicDivisor);
    divide = noEnd; constant(divide, 0); divide.insert(divide.end(), {OP_DIV, OP_END});
    fault(load(divide), GuardFault::DynamicDivisor);
    std::vector<std::uint8_t> lerp;
    constant(lerp, 1); constant(lerp, 2); constant(lerp, 1001);
    lerp.insert(lerp.end(), {OP_LERP, OP_END});
    fault(load(lerp), GuardFault::InvalidLerpWeight);
    std::vector<std::uint8_t> budget;
    constant(budget, 1);
    budget.insert(budget.end(), MaxExpressionOps - 2, OP_NOP); budget.push_back(OP_END);
    assert(load(budget).ok());
    budget.insert(budget.begin(), OP_NOP);
    fault(load(budget), GuardFault::OperationBudget);
    std::vector<std::uint8_t> deep;
    for (unsigned i = 0; i < MaxExpressionStack; ++i) constant(deep, 1);
    auto tooDeep = deep; constant(tooDeep, 1); tooDeep.push_back(OP_END);
    fault(load(tooDeep), GuardFault::StackOverflow);
    deep.insert(deep.end(), MaxExpressionStack - 1, OP_POP); deep.push_back(OP_END);
    assert(load(deep).ok());
    std::vector<std::uint8_t> oversized(MaxExpressionBytes + 1, OP_NOP);
    fault(load(oversized), GuardFault::InvalidLength);
    // Bounded mutation smoke test: each unknown byte and incomplete operand
    // reaches admission, never an unchecked native interpreter entry point.
    for (unsigned opcode = 0; opcode < 256; ++opcode) {
        auto mutant = read; mutant.insert(mutant.end() - 1, static_cast<std::uint8_t>(opcode));
        auto r = load(mutant);
        if (r.ok()) assert(guarded.run(samples, 2, 100).operations <= MaxExpressionOps);
    }

    samples[0] = {100, 6000, 90, true}; samples[1] = {101, -120, 90, true};
    // Real native CAN packer, both buses/ID widths, scaling and signed values.
    for (unsigned bus = 0; bus < 2; ++bus) {
        auto c = config(); c.bus = static_cast<std::uint8_t>(bus);
        c.is_extended = static_cast<std::uint8_t>(bus); c.can_id = bus ? 0x12345 : 0x321;
        assert(validate(c).ok());
        Channel_Init(&nativeChannels);
        for (const auto& s : samples) {
            Channel_Register(&nativeChannels, s.id, CH_TYPE_NUMBER, CH_CLASS_INPUT, nullptr);
            Channel_SetValue(&nativeChannels, s.id, s.value);
        }
        Channel_BeginTick(&nativeChannels, 100);
        CanTx_Init(&nativeCan, &nativeChannels, capture);
        assert(CanTx_Add(&nativeCan, &c) == 0);
        sends = 0;
        CanTx_Update(&nativeCan, 99); CanTx_SendPending(&nativeCan); assert(sends == 0);
        CanTx_Update(&nativeCan, 100); CanTx_SendPending(&nativeCan); assert(sends == 1);
        assert(sentBus == bus && sentId == c.can_id && sentExtended == (bus != 0) && sentDlc == 4);
        assert(sentBytes[0] == 0xdc && sentBytes[1] == 0x05);
        assert(sentBytes[2] == 0x88 && sentBytes[3] == 0xff);
        CanTx_SendPending(&nativeCan); assert(sends == 1);
    }
    auto c = config();
    // Retain the native scale/offset ordering explicitly. It is not the DBC
    // physical-offset inverse: raw=6000,scale=4,offset=100 produces1400.
    c.signals[0].offset = 100;
    assert(validate(c).ok());
    CanTx_Init(&nativeCan, &nativeChannels, capture);
    assert(CanTx_Add(&nativeCan, &c) == 0);
    CanTx_Update(&nativeCan, 100); CanTx_SendPending(&nativeCan);
    assert(sentBytes[0] == 0x78 && sentBytes[1] == 0x05);
    c = config();
    c.signals[0].scale_num = 0; // Native implementation would divide by zero.
    fault(validate(c), GuardFault::InvalidCanConfig);
    c = config(); c.signals[0].scale_den = 0;
    fault(validate(c), GuardFault::InvalidCanConfig);
    c = config(); c.signals[0].bit_length = 33;
    fault(validate(c), GuardFault::InvalidCanConfig);
    c = config(); c.signals[1].start_bit = 8; // overlap
    fault(validate(c), GuardFault::InvalidCanConfig);
    c = config(); c.dlc = 3; // incomplete final signal
    fault(validate(c), GuardFault::InvalidCanConfig);
    c = config(); c.bus = 2;
    fault(validate(c), GuardFault::InvalidCanConfig);
    c = config(); c.can_id = 0x800;
    fault(validate(c), GuardFault::InvalidCanConfig);
    c = config(); c.is_extended = 1; c.can_id = 0x20000000;
    fault(validate(c), GuardFault::InvalidCanConfig);
    c = config(); c.mode = CAN_TX_GATEWAY;
    fault(validate(c), GuardFault::InvalidCanConfig);
    c = config(); c.signals[0].byte_order = CAN_BYTE_ORDER_BE;
    fault(validate(c), GuardFault::InvalidCanConfig);
    c = config(); c.signals[0].signal_type = CAN_SIGNAL_FLOAT;
    fault(validate(c), GuardFault::InvalidCanConfig);
    c = config(); c.signals[0].source_channel = 102;
    fault(validate(c), GuardFault::UnknownInput);
    c = config(); c.signals[1].signal_type = CAN_SIGNAL_UNSIGNED;
    fault(validate(c), GuardFault::CanSignalRange);
    c = config(); c.signals[0].bit_length = 8;
    fault(validate(c), GuardFault::CanSignalRange);
    c = config(); samples[0].valid = false;
    fault(validate(c), GuardFault::InputInvalid);
    samples[0].valid = true; samples[0].timestampMs = 0;
    fault(validate(c), GuardFault::InputStale);
    samples[0] = {100, 0, 90, true};
    c = config(); c.signal_count = 1;
    for (unsigned bits = 0; bits < 256; ++bits) {
        c.signals[0].bit_length = static_cast<std::uint8_t>(bits);
        assert(validate(c).ok() == (bits >= 1 && bits <= 32));
    }
    c = config();
    for (unsigned bus = 0; bus < 256; ++bus) {
        c.bus = static_cast<std::uint8_t>(bus);
        assert(validate(c).ok() == (bus < 2));
    }
    std::cout << "RacingDash unchanged native VM/CAN + admission: PASS; expression bytes="
              << sizeof(Expression) << "\n";
}
