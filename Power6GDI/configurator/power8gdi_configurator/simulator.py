"""Deterministic display simulator. No transport, calibration writes or ECU model.

These artificial signals exercise the client lifecycle and rendering only. They
do not predict engine/firmware behaviour and cannot command any physical output.
"""
from dataclasses import dataclass
import math

from .profiles import SPORT_GDI6, target_profile


@dataclass(frozen=True)
class Channel:
    id: str
    label: str
    unit: str
    minimum: float
    maximum: float


CHANNELS = (
    Channel('rpm', 'Engine speed', 'rpm', 0, 10000),
    Channel('map', 'Manifold pressure', 'kPa abs', 0, 400),
    Channel('lambda', 'Lambda 1', 'lambda', 0.5, 2),
    Channel('rail', 'DI rail pressure', 'kPa', 0, 45000),
    Channel('throttle', 'DBW position', '%', 0, 100),
    Channel('wastegate', 'EWG position', '%', 0, 100),
)


@dataclass(frozen=True)
class Sample:
    simulation_time_s: float
    values: tuple[float, ...]


class DisplaySimulator:
    def __init__(self):
        self.connected = False
        self.time_s = 0.0

    def connect(self, profile_id: str) -> None:
        profile = target_profile(profile_id)
        if profile.id != SPORT_GDI6:
            raise ValueError('Simulator supports Sport GDI6 only; legacy files are not converted')
        self.time_s = 0.0
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False
        self.time_s = 0.0

    def step(self, interval_s: float) -> Sample:
        if not self.connected:
            raise RuntimeError('Simulator is disconnected')
        if (isinstance(interval_s, bool) or not isinstance(interval_s, (int, float)) or
                not math.isfinite(interval_s) or not 0 < interval_s <= 1):
            raise ValueError('Simulation step must be finite and in (0, 1] seconds')
        self.time_s += interval_s
        # Bounded artificial signals, not outputs from the fuel/spark controller.
        phase = self.time_s * 0.7
        values = (2500 + 1700 * math.sin(phase),
                  130 + 60 * math.sin(phase - 0.2),
                  0.95 + 0.03 * math.sin(phase * 2),
                  12000 + 3500 * math.sin(phase - 0.4),
                  35 + 25 * math.sin(phase),
                  45 + 20 * math.sin(phase - 0.5))
        return Sample(self.time_s, values)
