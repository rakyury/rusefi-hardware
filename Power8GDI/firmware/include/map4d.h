#pragma once

// Stand-alone Power8GDI 4D calibration evaluator (three axes + output).
// Integrating this with rusEFI engine_configuration_s / binary protocol is a
// separate task. Fixed memory, no allocation, no exceptions, deterministic.

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>

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

    // Full bounded validation, also used by this stand-alone lookup. MCU
    // integration must budget this O(cell count) scan and binary64 arithmetic.
    bool validate() const noexcept {
        if (!x_bins || !y_bins || !z_bins || !values ||
            nx == 0 || ny == 0 || nz == 0 ||
            nx > 32 || ny > 32 || nz > 32 ||
            nx * ny * nz > 4096 ||
            !std::isfinite(scale) || !std::isfinite(offset) || scale == 0) {
            return false;
        }
        if (!axisValid(x_bins, nx) || !axisValid(y_bins, ny) ||
            !axisValid(z_bins, nz)) return false;
        for (std::size_t i = 0; i < nx * ny * nz; ++i) {
            const double value = static_cast<double>(values[i]) * scale + offset;
            if (!std::isfinite(value) ||
                std::fabs(value) > std::numeric_limits<float>::max()) return false;
        }
        return true;
    }

    // Return false and do not modify output for an invalid live input or map.
    bool evaluate(float x, float y, float z, float& out) const noexcept {
        if (!validate() || !std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
            return false;
        }
        const auto ax = axisLookup(x_bins, nx, x);
        const auto ay = axisLookup(y_bins, ny, y);
        const auto az = axisLookup(z_bins, nz, z);
        const double low = bilinear(ax, ay, az.lo);
        const double high = bilinear(ax, ay, az.hi);
        const double result = lerp(low, high, az.factor);
        if (!std::isfinite(result) || std::fabs(result) > std::numeric_limits<float>::max()) {
            return false;
        }
        out = static_cast<float>(result);
        return true;
    }

private:
    struct Location {
        std::size_t lo;
        std::size_t hi;
        double factor;
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
                // Finite float32 endpoints may have a difference above FLT_MAX.
                return {i - 1, i, (double(v) - bins[i - 1]) /
                                  (double(bins[i]) - bins[i - 1])};
            }
        }
        return {count - 1, count - 1, 0.f};
    }

    static double lerp(double a, double b, double t) noexcept {
        return a + (b - a) * t;
    }

    double at(std::size_t ix, std::size_t iy, std::size_t iz) const noexcept {
        // Canonical engineering cell: multiply/add in binary64, round once to
        // binary32. The offline Python decoder interpolates these same cells.
        return static_cast<float>(double(values[(iz * ny + iy) * nx + ix]) * scale + offset);
    }

    double bilinear(Location x, Location y, std::size_t z) const noexcept {
        const double a = lerp(at(x.lo, y.lo, z), at(x.hi, y.lo, z), x.factor);
        const double b = lerp(at(x.lo, y.hi, z), at(x.hi, y.hi, z), x.factor);
        return lerp(a, b, y.factor);
    }
};

} // namespace power8gdi
