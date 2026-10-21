#include "../arbitration/ignition_arbiter.h"
#include "../arbitration/intervention_accumulator.h"
#include "../arbitration/task_cycle.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>

using namespace power8gdi;

namespace {

const float kNaN = std::numeric_limits<float>::quiet_NaN();
const float kInf = std::numeric_limits<float>::infinity();

bool near(float a, float b) { return std::fabs(a - b) < 1e-4f; }

template <typename E>
std::uint16_t bit(E e) { return static_cast<std::uint16_t>(1u << static_cast<unsigned>(e)); }

void accumulatorRules() {
    InterventionAccumulator acc;

    // Fuel: product of factors, source mask only for factors != 1.
    assert(acc.multiplyFuel(FuelSource::Warmup, 1.2f));
    assert(acc.multiplyFuel(FuelSource::Ethanol, 1.5f));
    assert(acc.multiplyFuel(FuelSource::Custom, 1.0f));
    assert(near(acc.fuelFactor(), 1.8f));
    assert(acc.fuelMask() == (bit(FuelSource::Warmup) | bit(FuelSource::Ethanol)));

    // Any cut forces 0, whatever the factors are.
    acc.cutFuel(FuelCutSource::OilPressure);
    assert(acc.fuelCutActive() && acc.fuelFactor() == 0.0f);
    assert(acc.fuelCutMask() == bit(FuelCutSource::OilPressure));

    // Ignition: sum, clamped to limits.
    assert(acc.addIgnition(IgnitionSource::Knock, -4.0f));
    assert(acc.addIgnition(IgnitionSource::CoolantTemp, 1.5f));
    assert(near(acc.ignitionOffset(), -2.5f));
    assert(acc.addIgnition(IgnitionSource::SpeedLimiter, -100.0f));
    assert(near(acc.ignitionOffset(), AccumulatorLimits{}.ignitionOffsetMin));

    // Lambda: offsets summed, then floor, then ceiling (richer wins on conflict).
    assert(acc.addLambda(LambdaSource::ExhaustTemp, -0.05f));
    assert(near(acc.applyLambda(1.0f), 0.95f));
    assert(acc.limitLambdaBelow(LambdaSource::Minimum, 0.97f));
    assert(near(acc.applyLambda(1.0f), 0.97f));
    assert(acc.limitLambdaAbove(LambdaSource::NitrousCeiling, 0.85f));
    assert(acc.limitLambdaAbove(LambdaSource::NitrousCeiling, 0.90f));  // lowest ceiling kept
    assert(near(acc.applyLambda(1.0f), 0.85f));

    // Boost: product.
    assert(acc.multiplyBoost(BoostSource::CoolantTemp, 0.9f));
    assert(acc.multiplyBoost(BoostSource::Gear, 0.5f));
    assert(near(acc.boostFactor(), 0.45f));

    // Reset returns to neutral.
    acc.reset();
    assert(acc.fuelFactor() == 1.0f && !acc.fuelCutActive());
    assert(acc.ignitionOffset() == 0.0f && near(acc.applyLambda(0.9f), 0.9f));
    assert(acc.boostFactor() == 1.0f && acc.cylinderCut().percent == 0.0f);
    assert(acc.fuelMask() == 0 && acc.rejectedRequests() == 0);
}

void accumulatorRejectsBadInput() {
    InterventionAccumulator acc;
    assert(!acc.multiplyFuel(FuelSource::Knock, kNaN));
    assert(!acc.multiplyFuel(FuelSource::Knock, -0.1f));
    assert(!acc.multiplyFuel(FuelSource::Knock, 10.0f));
    assert(!acc.addIgnition(IgnitionSource::Knock, kInf));
    assert(!acc.addLambda(LambdaSource::Custom, kNaN));
    assert(!acc.addLambda(LambdaSource::Custom, 0.9f));
    assert(!acc.limitLambdaAbove(LambdaSource::NitrousCeiling, 0.0f));
    assert(!acc.limitLambdaBelow(LambdaSource::Minimum, kNaN));
    assert(!acc.multiplyBoost(BoostSource::User, kNaN));
    assert(!acc.requestCylinderCut(CylinderCutSource::RpmLimiter, kNaN, 0));
    assert(acc.rejectedRequests() == 10);
    // Nothing leaked into the results.
    assert(acc.fuelFactor() == 1.0f && acc.ignitionOffset() == 0.0f);
    assert(acc.boostFactor() == 1.0f && near(acc.applyLambda(1.0f), 1.0f));
    assert(acc.cylinderCut().source == CylinderCutSource::None);
}

void cylinderCutMaxWinsEarlierOnTie() {
    InterventionAccumulator acc;
    assert(acc.requestCylinderCut(CylinderCutSource::GearShift, 50.0f, 1));
    assert(acc.requestCylinderCut(CylinderCutSource::SpeedLimiter, 50.0f, 2));  // tie: earlier keeps it
    assert(acc.cylinderCut().source == CylinderCutSource::GearShift);
    assert(acc.cylinderCut().pattern == 1);
    assert(acc.requestCylinderCut(CylinderCutSource::RpmLimiter, 75.0f, 3));
    assert(acc.cylinderCut().source == CylinderCutSource::RpmLimiter && acc.cylinderCut().percent == 75.0f);
    assert(acc.requestCylinderCut(CylinderCutSource::Overboost, 250.0f, 4));  // clamped to 100
    assert(acc.cylinderCut().percent == 100.0f);
    assert(acc.requestCylinderCut(CylinderCutSource::AntiLag, 0.0f, 5));      // no-op, not a candidate
    assert(acc.cutCandidateMask() == (bit(CylinderCutSource::GearShift) | bit(CylinderCutSource::SpeedLimiter) |
                                      bit(CylinderCutSource::RpmLimiter) | bit(CylinderCutSource::Overboost)));
}

// --- task cycle -----------------------------------------------------------

struct Recorder {
    char log[256] = {};
    int n = 0;
    void put(char c) { if (n < 255) log[n++] = c; }
};

struct Probe {
    Recorder* rec;
    char upd;
    char con;
    float cutPct;
    CylinderCutSource src;
    int updates = 0;
};

void probeUpdate(void* c) { auto* p = static_cast<Probe*>(c); p->updates++; p->rec->put(p->upd); }
void probeContribute(void* c, InterventionAccumulator& acc) {
    auto* p = static_cast<Probe*>(c);
    p->rec->put(p->con);
    if (p->cutPct > 0) acc.requestCylinderCut(p->src, p->cutPct, 0);
}

struct FinalStage {
    CylinderCut seen{};
    float fuel = -1;
};
void finalContribute(void* c, InterventionAccumulator& acc) {
    auto* f = static_cast<FinalStage*>(c);
    f->seen = acc.cylinderCut();
    f->fuel = acc.fuelFactor();
}

void cycleOrderAndFinalStage() {
    Recorder rec;
    Probe a{&rec, 'A', 'a', 40.0f, CylinderCutSource::GearShift};
    Probe b{&rec, 'B', 'b', 40.0f, CylinderCutSource::SpeedLimiter};
    FinalStage fin;

    TaskCycle cycle;
    assert(cycle.add({"gear", 20, probeUpdate, probeContribute, &a, false}) == AddResult::Ok);
    assert(cycle.add({"speed", 20, probeUpdate, probeContribute, &b, false}) == AddResult::Ok);
    assert(cycle.add({"cut", 20, nullptr, finalContribute, &fin, true}) == AddResult::Ok);
    // A contributor after a final stage would read nothing -> rejected.
    assert(cycle.add({"late", 20, probeUpdate, probeContribute, &a, false}) == AddResult::OrderViolation);
    cycle.freeze();
    assert(cycle.add({"x", 1, probeUpdate, nullptr, &a, true}) == AddResult::Frozen);

    InterventionAccumulator acc;
    acc.cutFuel(FuelCutSource::StopSwitch);  // stale request from a previous cycle
    cycle.runCycle(acc);
    // Strict order, update before contribute per task; final stage saw both requests.
    assert(rec.n == 4 && rec.log[0] == 'A' && rec.log[1] == 'a' && rec.log[2] == 'B' && rec.log[3] == 'b');
    assert(fin.seen.source == CylinderCutSource::GearShift);  // equal 40 %: earlier task wins
    assert(fin.fuel == 1.0f);                                 // accumulator was reset at cycle start
}

void cycleRatesAndSlots() {
    Recorder rec;
    Probe p1{&rec, '1', '-', 0, CylinderCutSource::None};
    Probe p5{&rec, '5', '-', 0, CylinderCutSource::None};
    Probe p5b{&rec, '6', '-', 0, CylinderCutSource::None};
    Probe p10{&rec, 'T', '-', 0, CylinderCutSource::None};

    TaskCycle cycle;
    assert(cycle.add({"bad3", 3, probeUpdate, nullptr, &p1, false}) == AddResult::BadRate);
    assert(cycle.add({"bad0", 0, probeUpdate, nullptr, &p1, false}) == AddResult::BadRate);
    assert(cycle.add({"empty", 1, nullptr, nullptr, &p1, false}) == AddResult::Empty);
    assert(cycle.add({"r1", 1, probeUpdate, nullptr, &p1, false}) == AddResult::Ok);
    assert(cycle.add({"r5", 5, probeUpdate, nullptr, &p5, false}) == AddResult::Ok);
    assert(cycle.add({"r5b", 5, probeUpdate, nullptr, &p5b, false}) == AddResult::Ok);
    assert(cycle.add({"r10", 10, probeUpdate, nullptr, &p10, false}) == AddResult::Ok);

    // Masks have exactly `rate` bits, evenly spaced.
    auto popcount = [](std::uint32_t m) { int c = 0; while (m) { c += m & 1u; m >>= 1; } return c; };
    assert(popcount(cycle.slotMask(0)) == 1 && popcount(cycle.slotMask(1)) == 5);
    assert(popcount(cycle.slotMask(2)) == 5 && popcount(cycle.slotMask(3)) == 10);
    // Two rate-5 tasks do not share a phase (load spreading).
    assert((cycle.slotMask(1) & cycle.slotMask(2)) == 0);
    // No slot carries more than the unavoidable load.
    int peak = 0;
    for (std::uint8_t s = 0; s < TaskCycle::kSlots; s++) peak = cycle.updatesInSlot(s) > peak ? cycle.updatesInSlot(s) : peak;
    assert(peak <= 2);

    InterventionAccumulator acc;
    for (int i = 0; i < 2 * TaskCycle::kSlots; i++) cycle.runCycle(acc);
    assert(p1.updates == 2 && p5.updates == 10 && p5b.updates == 10 && p10.updates == 20);
    assert(cycle.currentSlot() == 0);
}

void cycleCapacity() {
    Recorder rec;
    Probe p{&rec, 'x', 'x', 0, CylinderCutSource::None};
    TaskCycle cycle;
    for (int i = 0; i < TaskCycle::kMaxTasks; i++) assert(cycle.add({"t", 1, probeUpdate, nullptr, &p, false}) == AddResult::Ok);
    assert(cycle.add({"t", 1, probeUpdate, nullptr, &p, false}) == AddResult::Full);
}

// --- ignition arbiter -----------------------------------------------------

IgnitionInput tableOnly(float table) {
    IgnitionInput in;
    in.tableAdvanceDeg = table;
    return in;
}

void ignitionPriority() {
    IgnitionArbiter arb(IgnitionConfig{});
    InterventionAccumulator acc;
    acc.addIgnition(IgnitionSource::Knock, -3.0f);

    auto in = tableOnly(25.0f);
    auto r = arb.update(in, acc, 0.01f);
    assert(r.source == AngleSource::Table && near(r.advanceDeg, 22.0f) && near(r.correctionDeg, -3.0f));

    in.request[static_cast<unsigned>(AngleSource::Overrun)] = {true, 5.0f, 0.0f};
    in.request[static_cast<unsigned>(AngleSource::AntiLag)] = {true, -10.0f, 0.0f};
    r = arb.update(in, acc, 0.01f);
    // ALS outranks overrun; accumulator corrections not applied to ALS by default.
    assert(r.source == AngleSource::AntiLag && near(r.advanceDeg, -10.0f) && r.correctionDeg == 0.0f);

    in.request[static_cast<unsigned>(AngleSource::Cranking)] = {true, 8.0f, 0.0f};
    r = arb.update(in, acc, 0.01f);
    assert(r.source == AngleSource::Cranking && near(r.advanceDeg, 8.0f));

    // A non-finite request is ignored; the next active source wins.
    in.request[static_cast<unsigned>(AngleSource::Cranking)] = {true, kNaN, 0.0f};
    r = arb.update(in, acc, 0.01f);
    assert(r.source == AngleSource::AntiLag && !r.fault);
}

void ignitionCustomConfigAndClamp() {
    IgnitionConfig cfg;
    cfg.correctionsApplyMask = 0x3F;  // corrections for every source
    cfg.maxAdvance = 30.0f;
    IgnitionArbiter arb(cfg);
    InterventionAccumulator acc;
    acc.addIgnition(IgnitionSource::CoolantTemp, 10.0f);
    auto in = tableOnly(25.0f);
    in.request[static_cast<unsigned>(AngleSource::Idle)] = {true, 12.0f, 0.0f};
    auto r = arb.update(in, acc, 0.01f);
    assert(r.source == AngleSource::Idle && near(r.advanceDeg, 22.0f) && near(r.correctionDeg, 10.0f));
    in.request[static_cast<unsigned>(AngleSource::Idle)].active = false;
    r = arb.update(in, acc, 0.01f);
    assert(r.source == AngleSource::Table && near(r.advanceDeg, 30.0f));  // 35 clamped to max
}

void ignitionRamp() {
    IgnitionArbiter arb(IgnitionConfig{});
    InterventionAccumulator acc;
    auto in = tableOnly(20.0f);
    auto r = arb.update(in, acc, 0.01f);
    assert(near(r.advanceDeg, 20.0f) && !r.ramping);
    // Launch takes over with 100 deg/s: 30 deg away -> 1 deg per 10 ms.
    in.request[static_cast<unsigned>(AngleSource::LaunchControl)] = {true, -10.0f, 100.0f};
    r = arb.update(in, acc, 0.01f);
    assert(r.source == AngleSource::LaunchControl && r.ramping && near(r.advanceDeg, 19.0f));
    for (int i = 0; i < 40; i++) r = arb.update(in, acc, 0.01f);
    assert(!r.ramping && near(r.advanceDeg, -10.0f));
}

void ignitionFaults() {
    IgnitionConfig bad;
    bad.priority[0] = AngleSource::Table;  // duplicate Table, Cranking missing
    assert(!validateIgnitionConfig(bad));
    IgnitionArbiter arbBad(bad);
    InterventionAccumulator acc;
    auto r = arbBad.update(tableOnly(20.0f), acc, 0.01f);
    assert(r.fault && r.advanceDeg == 0.0f);

    IgnitionConfig cfg;
    cfg.safeAdvance = 5.0f;
    assert(validateIgnitionConfig(cfg));
    IgnitionArbiter arb(cfg);
    r = arb.update(tableOnly(kNaN), acc, 0.01f);
    assert(r.fault && r.advanceDeg == 5.0f);
    r = arb.update(tableOnly(20.0f), acc, kNaN);
    assert(r.fault && r.advanceDeg == 5.0f);

    IgnitionConfig outside;
    outside.safeAdvance = 99.0f;
    assert(!validateIgnitionConfig(outside));
}

} // namespace

int main() {
    accumulatorRules();
    accumulatorRejectsBadInput();
    cylinderCutMaxWinsEarlierOnTie();
    cycleOrderAndFinalStage();
    cycleRatesAndSlots();
    cycleCapacity();
    ignitionPriority();
    ignitionCustomConfigAndClamp();
    ignitionRamp();
    ignitionFaults();
    std::cout << "arbitration (accumulator, task cycle, ignition arbiter) tests: PASS\n";
}
