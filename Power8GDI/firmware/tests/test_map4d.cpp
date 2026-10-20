#include "map4d.h"
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>

using power8gdi::Map4DView;

int main() {
    const float x[] = {0.f, 100.f};
    const float y[] = {1000.f, 3000.f};
    const float z[] = {0.f, 100.f};
    // affine function: f(x,y,z) = x * 0.1 + y * 0.001 + z * 0.2
    const float values[] = {
        1.f, 11.f, 3.f, 13.f,
        21.f, 31.f, 23.f, 33.f
    };
    Map4DView<float> map{x, y, z, values, 2, 2, 2, 1.f, 0.f};
    assert(map.validate());
    float out = 777.f;
    assert(map.evaluate(50.f, 2000.f, 50.f, out));
    assert(std::fabs(out - 17.f) < 1e-5f);
    assert(map.evaluate(-900.f, -999.f, -1.f, out) && out == 1.f);
    assert(map.evaluate(900.f, 9999.f, 200.f, out) && out == 33.f);
    assert(map.evaluate(100.f, 1000.f, 100.f, out) && out == 31.f);
    assert(map.evaluate(0.f, 3000.f, 100.f, out) && out == 23.f);
    out = 123.f;
    assert(!map.evaluate(std::numeric_limits<float>::quiet_NaN(), 1000.f, 0.f, out));
    assert(out == 123.f); // failed lookup must not change current command
    const float bad_z[] = {5.f, 4.f};
    Map4DView<float> bad{x, y, bad_z, values, 2, 2, 2};
    assert(!bad.validate());
    const float nan_z[] = {0.f, std::numeric_limits<float>::infinity()};
    Map4DView<float> invalid{x, y, nan_z, values, 2, 2, 2};
    assert(!invalid.validate());
    Map4DView<float> oversize{x, y, z, values, 32, 32, 5};
    assert(!oversize.validate());
    const int16_t packed[] = {0, 100, 200, 300, 400, 500, 600, 700};
    Map4DView<int16_t> packed_map{x, y, z, packed, 2, 2, 2, 0.1f, -20.f};
    assert(packed_map.evaluate(50.f, 2000.f, 50.f, out));
    assert(std::fabs(out - 15.f) < 1e-5f);
    const float one[] = {42.f};
    const float one_value[] = {4.5f};
    Map4DView<float> degenerate{one, one, one, one_value, 1, 1, 1};
    assert(degenerate.evaluate(1.f, 1.f, 1.f, out) && out == 4.5f);
    return 0;
}
