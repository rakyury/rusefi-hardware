#pragma once
// P4DM v1 reader for an offline, CRC-checked experimental 4D calibration blob.
// NOT a rusEFI config page format, not flash persistence, not an engine-safe tune.
// Fixed storage (8 KB int16 cells + bins), no heap, no locks, no exceptions.

#include "map4d.h"
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>

namespace power8gdi {

class Map4DBlob {
public:
    static constexpr std::size_t HeaderBytes = 48;
    static constexpr std::size_t MaxBins = 32;
    static constexpr std::size_t MaxCells = 4096;

    // Requires offline-staged immutable blob; invalidate() disables lookup.
    // On failure all cells are considered unavailable; no output is returned.
    bool load(const std::uint8_t* bytes, std::size_t length) noexcept {
        invalidate();
        if (!bytes || length < HeaderBytes ||
            bytes[0] != 'P' || bytes[1] != '4' || bytes[2] != 'D' || bytes[3] != 'M' ||
            u16(bytes + 4) != 1 || u16(bytes + 6) != HeaderBytes ||
            u16(bytes + 14) != 0 || u32(bytes + 40) || u32(bytes + 44)) return false;

        nx_ = u16(bytes + 8);
        ny_ = u16(bytes + 10);
        nz_ = u16(bytes + 12);
        if (!nx_ || !ny_ || !nz_ || nx_ > MaxBins || ny_ > MaxBins || nz_ > MaxBins)
            return false;

        const std::size_t count = nx_ * ny_ * nz_;
        if (count > MaxCells) return false;
        const std::size_t expected = (nx_ + ny_ + nz_) * 4 + count * 2;
        if (u32(bytes + 32) != expected || length != HeaderBytes + expected) return false;
        if (crc32(bytes + HeaderBytes, expected) != u32(bytes + 36)) return false;

        scale_ = f32(bytes + 16);
        offset_ = f32(bytes + 20);
        const float minimum = f32(bytes + 24);
        const float maximum = f32(bytes + 28);
        if (!std::isfinite(scale_) || scale_ <= 0 || !std::isfinite(offset_) ||
            !std::isfinite(minimum) || !std::isfinite(maximum) || minimum > maximum)
            return false;

        std::size_t at = HeaderBytes;
        for (std::size_t i = 0; i < nx_; ++i, at += 4) x_[i] = f32(bytes + at);
        for (std::size_t i = 0; i < ny_; ++i, at += 4) y_[i] = f32(bytes + at);
        for (std::size_t i = 0; i < nz_; ++i, at += 4) z_[i] = f32(bytes + at);

        for (std::size_t i = 0; i < count; ++i, at += 2) {
            const auto raw = u16(bytes + at);
            cells_[i] = static_cast<std::int16_t>(raw <= 32767 ? int(raw) : int(raw) - 65536);
            // One final binary32 rounding, shared with the Python codec. A float
            // multiply followed by add can overflow before offset cancellation.
            const double wide = double(cells_[i]) * scale_ + offset_;
            if (!std::isfinite(wide) || std::fabs(wide) > std::numeric_limits<float>::max())
                return false;
            const float v = static_cast<float>(wide);
            if (v < minimum || v > maximum) return false;
        }
        if (!axisValid(x_.data(), nx_) || !axisValid(y_.data(), ny_) ||
            !axisValid(z_.data(), nz_)) return false;

        ready_ = true;
        return true;
    }

    void invalidate() noexcept {
        ready_ = false;
        nx_ = ny_ = nz_ = 0;
    }

    bool ready() const noexcept { return ready_; }

    bool evaluate(float x, float y, float z, float& output) const noexcept {
        if (!ready_) return false;
        const Map4DView<std::int16_t> map{
            x_.data(), y_.data(), z_.data(), cells_.data(),
            nx_, ny_, nz_, scale_, offset_
        };
        return map.evaluate(x, y, z, output);
    }

    std::size_t cellCount() const noexcept { return ready_ ? nx_ * ny_ * nz_ : 0; }

private:
    static std::uint16_t u16(const std::uint8_t* p) noexcept {
        return std::uint16_t(p[0]) | (std::uint16_t(p[1]) << 8);
    }
    static std::uint32_t u32(const std::uint8_t* p) noexcept {
        return std::uint32_t(u16(p)) | (std::uint32_t(u16(p + 2)) << 16);
    }
    static float f32(const std::uint8_t* p) noexcept {
        static_assert(sizeof(float) == 4, "Map4D requires IEEE754 32-bit float");
        static_assert(std::numeric_limits<float>::is_iec559, "Map4D requires IEEE754");
        std::uint32_t raw = u32(p);
        float f;
        std::memcpy(&f, &raw, 4);
        return f;
    }
    static std::uint32_t crc32(const std::uint8_t* data, std::size_t n) noexcept {
        std::uint32_t crc = 0xffffffff;
        for (std::size_t i = 0; i < n; ++i) {
            crc ^= data[i];
            for (int b = 0; b < 8; ++b)
                crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320u : 0u);
        }
        return ~crc;
    }
    static bool axisValid(const float* axis, std::size_t n) noexcept {
        if (!std::isfinite(axis[0])) return false;
        for (std::size_t i = 1; i < n; ++i)
            if (!std::isfinite(axis[i]) || axis[i] <= axis[i - 1]) return false;
        return true;
    }

    std::array<float, MaxBins> x_{};
    std::array<float, MaxBins> y_{};
    std::array<float, MaxBins> z_{};
    std::array<std::int16_t, MaxCells> cells_{};
    std::size_t nx_ = 0, ny_ = 0, nz_ = 0;
    float scale_ = 1.f, offset_ = 0.f;
    bool ready_ = false;
};

} // namespace power8gdi
