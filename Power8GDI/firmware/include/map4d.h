#pragma once

// Stand-alone Power8GDI 4D calibration evaluator (three axes + output).
// Integrating this with rusEFI engine_configuration_s / binary protocol is a
// separate task. Fixed memory, no allocation, no exceptions, deterministic.

#include <cmath>
#include <cstddef>
#include <cstdint>

namespace power8gdi {

// In ECU terminology: 4D = X, Y, Z inputs and one output value. This is
// mathematically trilinear interpolation over [Z][Y][X], X fastest.
template <typename Scalar>
struct Map4DView {
    const float* x_bins = nullptr;
    const float* y_bins = nullptr;
    const float* z_bins = nullptr;
    const Scalar* values = nullptr;
    std::size_t nx = 0;
    std::size_t ny = 0;
    std::size_t nz = 0;
    float scale = 1.0f;
    float offset = 0.0f;

    // Call at configuration load/Burn time, rather than every real-time lookup.
    bool validate() const noexcept {
        if (!x_bins || !y_bins || !z_bins || !values ||
            nx == 0 || ny == 0 || nz == 0 ||
            nx > 32 || ny > 32 || nz > 32 ||
            nx * ny * nz > 4096 ||
            !std::isfinite(scale) || !std::isfinite(offset) || scale == 0) {
            return false;
        }
        return axisValid(x_bins, nx) && axisValid(y_bins, ny) &&
               axisValid(z_bins, nz);
    }

    // Return false and do not modify output for an invalid live input or map.
    bool evaluate(float x, float y, float z, float& out) const noexcept {
        if (!validate() || !std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
            return false;
        }
        const auto ax = axisLookup(x_bins, nx, x);
        const auto ay = axisLookup(y_bins, ny, y);
        const auto az = axisLookup(z_bins, nz, z);
        const float low = bilinear(ax, ay, az.lo);
        const float high = bilinear(ax, ay, az.hi);
        const float raw = lerp(low, high, az.factor);
        const float result = raw * scale + offset;
        if (!std::isfinite(result)) {
            return false;
        }
        out = result;
        return true;
    }

private:
    struct Location {
        std::size_t lo;
        std::size_t hi;
        float factor;
    };

    static bool axisValid(const float* bins, std::size_t count) noexcept {
        if (!std::isfinite(bins[0])) return false;
        for (std::size_t i = 1; i < count; ++i) {
            if (!std::isfinite(bins[i]) || bins[i] <= bins[i - 1]) return false;
        }
        return true;
    }

    static Location axisLookup(const float* bins, std::size_t count, float v) noexcept {
        if (count == 1 || v <= bins[0]) return {0, 0, 0.f};
        if (v >= bins[count - 1]) return {count - 1, count - 1, 0.f};
        for (std::size_t i = 1; i < count; ++i) {
            if (v <= bins[i]) {
                return {i - 1, i, (v - bins[i - 1]) / (bins[i] - bins[i - 1])};
            }
        }
        return {count - 1, count - 1, 0.f};
    }

    static float lerp(float a, float b, float t) noexcept {
        return a + (b - a) * t;
    }

    float at(std::size_t ix, std::size_t iy, std::size_t iz) const noexcept {
        return static_cast<float>(values[(iz * ny + iy) * nx + ix]);
    }

    float bilinear(Location x, Location y, std::size_t z) const noexcept {
        const float a = lerp(at(x.lo, y.lo, z), at(x.hi, y.lo, z), x.factor);
        const float b = lerp(at(x.lo, y.hi, z), at(x.hi, y.hi, z), x.factor);
        return lerp(a, b, y.factor);
    }
};

} // namespace power8gdi
