"""Client-side target descriptions, not discovered ECU/wire capabilities.

The legacy project format identified only cylinders and HPFP count. Unknown
hardware is deliberately left unknown instead of assigning a newer board to it.
"""
from dataclasses import dataclass


SPORT_GDI6 = 'sport-gdi6'
LEGACY_POWER8GDI = 'legacy-power8gdi'


@dataclass(frozen=True)
class TargetProfile:
    id: str
    label: str
    revision: str
    cylinders: int
    hpfp_channels: int
    di_channels: int | None = None
    pi_channels: int | None = None
    ignition_channels: int | None = None
    dbw_channels: int | None = None
    ewg_channels: int | None = None
    lambda_channels: int | None = None
    knock_channels: int | None = None
    can_buses: int | None = None
    sent_required: bool | None = None
    lin_required: bool | None = None


_PROFILES = {
    SPORT_GDI6: TargetProfile(
        id=SPORT_GDI6, label='R2 Sport GDI6', revision='2026-10-25',
        cylinders=6, hpfp_channels=2, di_channels=6, pi_channels=6,
        ignition_channels=6, dbw_channels=1, ewg_channels=1,
        lambda_channels=1, knock_channels=2, can_buses=2,
        sent_required=True, lin_required=True),
    LEGACY_POWER8GDI: TargetProfile(
        id=LEGACY_POWER8GDI, label='Legacy Power8GDI project', revision='v1/v2',
        cylinders=8, hpfp_channels=2),
}


def target_profile(profile_id: str) -> TargetProfile:
    if not isinstance(profile_id, str) or profile_id not in _PROFILES:
        raise ValueError('Unknown target profile; no automatic hardware mapping is permitted')
    return _PROFILES[profile_id]
