#include "../fuel/allocation_gdi6.h"
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>

using namespace power6gdi;
namespace {
FuelConfig6 sharedConfig() {
    FuelConfig6 config;
    config.cylinders = 6;
    config.piInstalled = true;
    config.pumpConfigured = {true, true};
    return config;
}
CycleFuelRequest6 request() {
    CycleFuelRequest6 input;
    input.fuelAllowed = true;
    input.pumpCapacityMgPerCycle = {400.0f, 200.0f};
    for (unsigned i = 0; i < CylinderCount; ++i)
        input.cylinder[i] = {10.0f * (i + 1), 0.5f, false, 100.0f, 100.0f};
    return input;
}
void near(float actual, float expected) {
    assert(std::fabs(actual - expected) <= 0.00002f * std::fmax(1.0f, std::fabs(expected)));
}
void zero(const CycleFuelPlan6& output) {
    for (const auto& c : output.cylinder) {
        assert(c.diMassMg == 0.0f && c.piMassMg == 0.0f);
        assert(!c.diEventRequired && !c.piEventRequired);
    }
    for (unsigned i = 0; i < 2; ++i) {
        assert(output.diRailMassMg[i] == 0.0f);
        assert(output.pumpFeedForwardMassMg[i] == 0.0f);
        assert(output.pumpFeedForwardPct[i] == 0.0f);
    }
    assert(output.piTotalMassMg == 0.0f);
}
void rejected(const CycleFuelPlan6& output, FuelFault fault) {
    assert(output.disposition == FuelDisposition::Rejected);
    assert(output.fault == fault);
    zero(output);
}
} // namespace

int main() {
    auto config = sharedConfig();
    auto input = request();
    auto output = allocateFuelCycle(config, input);
    assert(output.disposition == FuelDisposition::Accepted && output.fault == FuelFault::None);
    // Nonuniform cylinder masses catch the incorrect cylinder1 * 6 approach.
    near(output.diRailMassMg[0], 105.0f);
    near(output.piTotalMassMg, 105.0f);
    near(output.pumpFeedForwardMassMg[0], 70.0f);
    near(output.pumpFeedForwardMassMg[1], 35.0f);
    near(output.pumpFeedForwardPct[0], 17.5f);
    near(output.pumpFeedForwardPct[1], 17.5f);

    // Hydraulic assignments are independent of the PT driver bank or order.
    config.railTopology = RailTopology::Independent;
    config.diRail = {0, 1, 1, 0, 1, 0};
    output = allocateFuelCycle(config, input);
    assert(output.disposition == FuelDisposition::Accepted);
    near(output.diRailMassMg[0], 55.0f);
    near(output.diRailMassMg[1], 50.0f);
    near(output.pumpFeedForwardPct[0], 13.75f);
    near(output.pumpFeedForwardPct[1], 25.0f);

    // PI wall film is applied AFTER partition, without altering DI rail demand.
    for (auto& c : input.cylinder) c.piTransientDeltaMg = 2.0f;
    output = allocateFuelCycle(config, input);
    assert(output.disposition == FuelDisposition::Accepted);
    near(output.diRailMassMg[0], 55.0f);
    near(output.diRailMassMg[1], 50.0f);
    near(output.piTotalMassMg, 117.0f);
    // Signed release corrections are allowed; a negative final dose is not.
    input.cylinder[0].piTransientDeltaMg = -5.0f;
    output = allocateFuelCycle(config, input);
    assert(output.disposition == FuelDisposition::Accepted);
    assert(output.cylinder[0].piMassMg == 0.0f && !output.cylinder[0].piEventRequired);
    input.cylinder[0].piTransientDeltaMg = -5.01f;
    rejected(allocateFuelCycle(config, input), FuelFault::DemandInvalid);
    input = request();

    // Final group doses, including transients, determine both capacities.
    input.cylinder[5].diCapacityMg = 30.0f;
    input.cylinder[5].diTransientDeltaMg = 1.0f;
    rejected(allocateFuelCycle(config, input), FuelFault::DiCapacityExceeded);
    input.cylinder[5].diTransientDeltaMg = 0.0f;
    input.cylinder[5].piCapacityMg = 30.0f;
    input.cylinder[5].piTransientDeltaMg = 1.0f;
    rejected(allocateFuelCycle(config, input), FuelFault::PiCapacityExceeded);
    input = request();
    input.pumpCapacityMgPerCycle = {55.0f, 50.0f};
    input.cylinder[5].diTransientDeltaMg = 1.0f;
    rejected(allocateFuelCycle(config, input), FuelFault::PumpCapacityExceeded);
    input = request();

    // Every cut cancels both base and transient injection, not film state.
    for (unsigned cuts = 0; cuts < 64; ++cuts) {
        input = request();
        float expectedDi = 0, expectedPi = 0;
        for (unsigned i = 0; i < CylinderCount; ++i) {
            auto& c = input.cylinder[i];
            c.diTransientDeltaMg = 1.0f;
            c.piTransientDeltaMg = -1.0f;
            c.fuelCut = (cuts & (1u << i)) != 0;
            if (!c.fuelCut) {
                expectedDi += c.totalMassMg * 0.5f + 1.0f;
                expectedPi += c.totalMassMg * 0.5f - 1.0f;
            }
        }
        output = allocateFuelCycle(config, input);
        assert(output.disposition == FuelDisposition::Accepted);
        near(output.diRailMassMg[0] + output.diRailMassMg[1], expectedDi);
        near(output.piTotalMassMg, expectedPi);
    }
    input = request();

    // Every cut pattern and several DI fractions conserve accepted mass.
    const float fractions[] = {0.0f, 0.125f, 0.5f, 0.75f, 1.0f};
    for (unsigned cuts = 0; cuts < 64; ++cuts) {
        for (float fraction : fractions) {
            float expectedRail[2] = {0.0f, 0.0f};
            float expectedPi = 0.0f;
            for (unsigned i = 0; i < CylinderCount; ++i) {
                input.cylinder[i].diFraction = fraction;
                input.cylinder[i].fuelCut = (cuts & (1u << i)) != 0;
                if (!input.cylinder[i].fuelCut) {
                    expectedRail[config.diRail[i]] += input.cylinder[i].totalMassMg * fraction;
                    expectedPi += input.cylinder[i].totalMassMg * (1.0f - fraction);
                }
            }
            output = allocateFuelCycle(config, input);
            assert(output.disposition == FuelDisposition::Accepted);
            for (unsigned i = 0; i < CylinderCount; ++i) {
                const auto& actual = output.cylinder[i];
                near(actual.diMassMg + actual.piMassMg,
                     input.cylinder[i].fuelCut ? 0.0f : input.cylinder[i].totalMassMg);
                assert(actual.diEventRequired == (actual.diMassMg > 0.0f));
                assert(actual.piEventRequired == (actual.piMassMg > 0.0f));
            }
            near(output.diRailMassMg[0], expectedRail[0]);
            near(output.diRailMassMg[1], expectedRail[1]);
            near(output.piTotalMassMg, expectedPi);
            near(output.pumpFeedForwardMassMg[0], expectedRail[0]);
            near(output.pumpFeedForwardMassMg[1], expectedRail[1]);
        }
    }

    config = sharedConfig();
    input = request();
    input.fuelAllowed = false;
    output = allocateFuelCycle(config, input);
    assert(output.disposition == FuelDisposition::Inhibited && output.fault == FuelFault::None);
    zero(output);
    // Missing PI cannot silently convert a split calibration into DI-only.
    input = request();
    config.piInstalled = false;
    rejected(allocateFuelCycle(config, input), FuelFault::ConfigurationInvalid);
    for (auto& c : input.cylinder) c.diFraction = 1.0f;
    output = allocateFuelCycle(config, input);
    assert(output.disposition == FuelDisposition::Accepted);
    near(output.diRailMassMg[0], 210.0f);
    assert(output.piTotalMassMg == 0.0f);
    input.cylinder[0].piTransientDeltaMg = 1.0f;
    rejected(allocateFuelCycle(config, input), FuelFault::ConfigurationInvalid);

    // Either single pump can serve a shared rail. Inactive outputs remain zero.
    for (unsigned activePump = 0; activePump < 2; ++activePump) {
        config = sharedConfig();
        input = request();
        config.pumpConfigured[1 - activePump] = false;
        input.pumpCapacityMgPerCycle[1 - activePump] = 0.0f;
        input.pumpCapacityMgPerCycle[activePump] = 210.0f;
        output = allocateFuelCycle(config, input);
        assert(output.disposition == FuelDisposition::Accepted);
        near(output.pumpFeedForwardMassMg[activePump], 105.0f);
        near(output.pumpFeedForwardPct[activePump], 50.0f);
        assert(output.pumpFeedForwardMassMg[1 - activePump] == 0.0f);
        assert(output.pumpFeedForwardPct[1 - activePump] == 0.0f);
        input.pumpCapacityMgPerCycle[1 - activePump] = 1.0f;
        rejected(allocateFuelCycle(config, input), FuelFault::ConfigurationInvalid);
    }
    // A late cylinder error rejects the WHOLE result; no silent DI/PI transfer.
    config = sharedConfig();
    input = request();
    input.cylinder[5].diCapacityMg = 29.9f;
    output = allocateFuelCycle(config, input);
    rejected(output, FuelFault::DiCapacityExceeded);
    assert(output.faultCylinder == 5);
    input.cylinder[5].diCapacityMg = 30.0f;
    input.cylinder[5].piCapacityMg = 29.9f;
    rejected(allocateFuelCycle(config, input), FuelFault::PiCapacityExceeded);
    input.cylinder[5].fuelCut = true;
    assert(allocateFuelCycle(config, input).disposition == FuelDisposition::Accepted);
    input.cylinder[5].fuelCut = false;
    input.cylinder[5].piCapacityMg = 30.0f;
    assert(allocateFuelCycle(config, input).disposition == FuelDisposition::Accepted);
    input.cylinder[5] = {70.0f, 0.1f, false, 7.0f, 63.0f};
    output = allocateFuelCycle(config, input);
    assert(output.disposition == FuelDisposition::Accepted);
    assert(output.cylinder[5].diMassMg == 7.0f && output.cylinder[5].piMassMg == 63.0f);
    input = request();
    input.pumpCapacityMgPerCycle = {50.0f, 50.0f};
    rejected(allocateFuelCycle(config, input), FuelFault::PumpCapacityExceeded);
    input.pumpCapacityMgPerCycle = {70.0f, 35.0f};
    output = allocateFuelCycle(config, input);
    assert(output.disposition == FuelDisposition::Accepted);
    near(output.pumpFeedForwardPct[0], 100.0f);
    near(output.pumpFeedForwardPct[1], 100.0f);
    config.railTopology = RailTopology::Independent;
    config.diRail = {0, 0, 0, 1, 1, 1};
    // Spare capacity on rail0 must not hide rail1 starvation.
    input.pumpCapacityMgPerCycle = {1000.0f, 74.0f};
    rejected(allocateFuelCycle(config, input), FuelFault::PumpCapacityExceeded);

    // No 4/8-cylinder truncation, bad rail index or unknown topology.
    for (unsigned count = 0; count < 256; ++count) {
        config = sharedConfig();
        config.cylinders = static_cast<std::uint8_t>(count);
        output = allocateFuelCycle(config, request());
        if (count == 6) assert(output.disposition == FuelDisposition::Accepted);
        else rejected(output, FuelFault::ConfigurationInvalid);
    }
    config = sharedConfig();
    config.diRail[5] = 1;
    rejected(allocateFuelCycle(config, request()), FuelFault::ConfigurationInvalid);
    config.diRail[5] = 2;
    rejected(allocateFuelCycle(config, request()), FuelFault::ConfigurationInvalid);
    config = sharedConfig();
    config.railTopology = static_cast<RailTopology>(2);
    rejected(allocateFuelCycle(config, request()), FuelFault::ConfigurationInvalid);
    config = sharedConfig();
    config.pumpConfigured = {false, false};
    rejected(allocateFuelCycle(config, request()), FuelFault::ConfigurationInvalid);
    config = sharedConfig();
    config.railTopology = RailTopology::Independent;
    rejected(allocateFuelCycle(config, request()), FuelFault::ConfigurationInvalid);
    config.diRail = {0, 0, 0, 1, 1, 1};
    config.pumpConfigured[1] = false;
    input = request();
    input.pumpCapacityMgPerCycle[1] = 0;
    rejected(allocateFuelCycle(config, input), FuelFault::ConfigurationInvalid);

    config = sharedConfig();
    const float bad[] = {std::numeric_limits<float>::quiet_NaN(),
                         std::numeric_limits<float>::infinity(), -1.0f};
    for (float value : bad) {
        for (unsigned field = 0; field < 4; ++field) {
            input = request();
            switch (field) {
                case 0: input.cylinder[4].totalMassMg = value; break;
                case 1: input.cylinder[4].diFraction = value; break;
                case 2: input.cylinder[4].diCapacityMg = value; break;
                case 3: input.cylinder[4].piCapacityMg = value; break;
            }
            rejected(allocateFuelCycle(config, input), FuelFault::DemandInvalid);
            input.cylinder[4].fuelCut = true;
            rejected(allocateFuelCycle(config, input), FuelFault::DemandInvalid);
        }
        input = request();
        input.pumpCapacityMgPerCycle[1] = value;
        rejected(allocateFuelCycle(config, input), FuelFault::ConfigurationInvalid);
    }
    const float badDelta[] = {std::numeric_limits<float>::quiet_NaN(),
                             std::numeric_limits<float>::infinity(),
                             -std::numeric_limits<float>::infinity()};
    for (float value : badDelta) {
        input = request();
        input.cylinder[5].diTransientDeltaMg = value;
        rejected(allocateFuelCycle(config, input), FuelFault::DemandInvalid);
        input = request();
        input.cylinder[5].piTransientDeltaMg = value;
        rejected(allocateFuelCycle(config, input), FuelFault::DemandInvalid);
        input.cylinder[5].fuelCut = true;
        rejected(allocateFuelCycle(config, input), FuelFault::DemandInvalid);
    }
    input = request();
    input.cylinder[0].diFraction = 1.01f;
    rejected(allocateFuelCycle(config, input), FuelFault::DemandInvalid);
    input = request();
    input.pumpCapacityMgPerCycle[0] = 0.0f;
    rejected(allocateFuelCycle(config, input), FuelFault::ConfigurationInvalid);
    // No deadtime-generated event from zero mass. Zero feed-forward is not a
    // pressure-controller shutdown command.
    input = request();
    for (auto& c : input.cylinder) c.totalMassMg = 0.0f;
    output = allocateFuelCycle(config, input);
    assert(output.disposition == FuelDisposition::Accepted);
    zero(output);
    // Finite per-cylinder inputs can still overflow the float aggregate.
    input = request();
    for (auto& c : input.cylinder)
        c = {std::numeric_limits<float>::max(), 1.0f, false,
             std::numeric_limits<float>::max(), 0.0f};
    input.pumpCapacityMgPerCycle = {std::numeric_limits<float>::max(),
                                  std::numeric_limits<float>::max()};
    rejected(allocateFuelCycle(config, input), FuelFault::NumericOverflow);
    input = request();
    input.cylinder[0] = {std::numeric_limits<float>::max(), 1.0f, false,
                        std::numeric_limits<float>::max(), 0.0f,
                        std::numeric_limits<float>::max(), 0.0f};
    rejected(allocateFuelCycle(config, input), FuelFault::NumericOverflow);
    std::cout << "GDI6 DI/PI mass and rail feed-forward contract: PASS\n";
}
