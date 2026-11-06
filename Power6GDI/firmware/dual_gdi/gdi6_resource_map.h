// Generated from hardware/design/gdi/scheduling_contract.json. Do not edit.
// Normalized SHA256: e5b55b0bd0e02192f2e378f9caa1aa3929491494776f6c300f0f10da28b59946
#pragma once
#include <array>
#include <cstdint>
namespace power6gdi {
inline constexpr std::array<std::uint8_t, 6> CurrentPath = {0, 0, 1, 2, 2, 3};
inline constexpr std::array<std::uint8_t, 6> BoostSupply = {0, 0, 0, 1, 1, 1};
inline constexpr bool ContractEnginePermission = false;
inline constexpr bool ContractGuardQualified = false;
inline constexpr std::uint32_t ContractGuardUs = 0;
} // namespace power6gdi
