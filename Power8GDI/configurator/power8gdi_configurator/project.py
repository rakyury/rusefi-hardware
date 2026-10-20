"""Versioned, validated offline calibration model for Power8GDI.

No claim of rusEFI memory-layout compatibility is made. Until matching
Power8GDI firmware/INI exists, exported JSON is an editor-only format.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import json
import math
import tempfile
from typing import Any

FORMAT_VERSION = 2


def _finite_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Expected numeric value')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite value')
    return result


def _axis(values: Any, label: str) -> list[float]:
    if not isinstance(values, list) or not 1 <= len(values) <= 32:
        raise ValueError(f'{label}: 1..32 bins required')
    result = [_finite_number(value) for value in values]
    if any(b <= a for a, b in zip(result, result[1:])):
        raise ValueError(f'{label}: bins must be strictly increasing')
    return result


@dataclass
class CalibrationTable:
    name: str
    description: str
    x_label: str
    y_label: str
    value_unit: str
    x_bins: list[float]
    y_bins: list[float]
    values: list[list[float]]
    minimum: float
    maximum: float
    safety_class: str = 'calibration'

    def validate(self) -> None:
        for key in ('name', 'description', 'x_label', 'y_label', 'value_unit'):
            if not isinstance(getattr(self, key), str):
                raise ValueError(f'{key} must be text')
        if not self.name or self.safety_class not in ('calibration', 'safety_critical'):
            raise ValueError('Invalid name or safety class')
        self.x_bins = _axis(self.x_bins, 'X axis')
        self.y_bins = _axis(self.y_bins, 'Y axis')
        lo = _finite_number(self.minimum)
        hi = _finite_number(self.maximum)
        if lo > hi or len(self.values) != len(self.y_bins):
            raise ValueError('Invalid value bounds or Y dimension')
        for row in self.values:
            if len(row) != len(self.x_bins):
                raise ValueError('Value X dimension mismatch')
            for val in row:
                value = _finite_number(val)
                if value < lo or value > hi:
                    raise ValueError(f'Value {value} outside {lo}..{hi}')

    def set_value(self, x: int, y: int, value: float) -> None:
        n = _finite_number(value)
        if not self.minimum <= n <= self.maximum:
            raise ValueError(f'{n:g} outside range {self.minimum:g}..{self.maximum:g}')
        self.values[y][x] = n

    def interpolate(self, x: float, y: float) -> float:
        """Bilinear interpolation with axis clamping (offline preview only)."""
        self.validate()
        xx, yy = _finite_number(x), _finite_number(y)

        def coord(bins: list[float], val: float) -> tuple[int, int, float]:
            if val <= bins[0]:
                return 0, 0, 0.
            if val >= bins[-1]:
                return len(bins)-1, len(bins)-1, 0.
            for i in range(len(bins)-1):
                if bins[i] <= val <= bins[i+1]:
                    return i, i+1, (val-bins[i])/(bins[i+1]-bins[i])
            raise AssertionError('Monotonic axis invariant')

        i0,i1,t=coord(self.x_bins,xx)
        j0,j1,u=coord(self.y_bins,yy)
        a=self.values[j0][i0]*(1-t)+self.values[j0][i1]*t
        b=self.values[j1][i0]*(1-t)+self.values[j1][i1]*t
        return a*(1-u)+b*u

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return vars(self).copy()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> 'CalibrationTable':
        table=cls(**value)
        table.validate()
        return table


@dataclass
class CalibrationTable4D:
    """3 input axes + scalar output, stored [z][y][x] with X fastest.

    Format version 2 (editor-only; NOT a rusEFI ECU memory-page format).
    """
    name: str
    description: str
    x_label: str
    y_label: str
    z_label: str
    value_unit: str
    x_bins: list[float]
    y_bins: list[float]
    z_bins: list[float]
    values: list[list[list[float]]]
    minimum: float
    maximum: float
    safety_class: str = 'calibration'

    def validate(self) -> None:
        for key in ('name', 'description', 'x_label', 'y_label', 'z_label', 'value_unit'):
            if not isinstance(getattr(self, key), str):
                raise ValueError(f'{key} must be text')
        if not self.name or self.safety_class not in ('calibration', 'safety_critical'):
            raise ValueError('Invalid map name or safety class')
        self.x_bins = _axis(self.x_bins, 'X axis')
        self.y_bins = _axis(self.y_bins, 'Y axis')
        self.z_bins = _axis(self.z_bins, 'Z axis')
        lo = _finite_number(self.minimum)
        hi = _finite_number(self.maximum)
        if lo > hi:
            raise ValueError('Invalid map minimum / maximum')
        if len(self.x_bins) * len(self.y_bins) * len(self.z_bins) > 4096:
            raise ValueError('4D map exceeds 4096-cell prototype memory budget')
        if not isinstance(self.values, list) or len(self.values) != len(self.z_bins):
            raise ValueError('4D Z dimension mismatch')
        for slab in self.values:
            if not isinstance(slab, list) or len(slab) != len(self.y_bins):
                raise ValueError('4D Y dimension mismatch')
            for row in slab:
                if not isinstance(row, list) or len(row) != len(self.x_bins):
                    raise ValueError('4D X dimension mismatch')
                for v in row:
                    scalar = _finite_number(v)
                    if not lo <= scalar <= hi:
                        raise ValueError(f'Map value {scalar} outside {lo}..{hi}')

    def set_value(self, x: int, y: int, z: int, value: float) -> None:
        scalar = _finite_number(value)
        if not self.minimum <= scalar <= self.maximum:
            raise ValueError(f'{scalar:g} outside {self.minimum:g}..{self.maximum:g}')
        self.values[z][y][x] = scalar

    @staticmethod
    def _coordinate(bins: list[float], val: float) -> tuple[int, int, float]:
        if val <= bins[0]:
            return 0, 0, 0.
        if val >= bins[-1]:
            return len(bins) - 1, len(bins) - 1, 0.
        for i in range(1, len(bins)):
            if val <= bins[i]:
                return i - 1, i, (val - bins[i-1]) / (bins[i] - bins[i-1])
        raise AssertionError('Axis must be monotonic')

    @staticmethod
    def _lerp(a: float, b: float, f: float) -> float:
        return a + (b - a) * f

    def interpolate(self, x: float, y: float, z: float) -> float:
        self.validate()
        i0, i1, a = self._coordinate(self.x_bins, _finite_number(x))
        j0, j1, b = self._coordinate(self.y_bins, _finite_number(y))
        k0, k1, c = self._coordinate(self.z_bins, _finite_number(z))

        def plane(k: int) -> float:
            low = self._lerp(self.values[k][j0][i0], self.values[k][j0][i1], a)
            high = self._lerp(self.values[k][j1][i0], self.values[k][j1][i1], a)
            return self._lerp(low, high, b)

        return self._lerp(plane(k0), plane(k1), c)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return vars(self).copy()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> 'CalibrationTable4D':
        table = cls(**value)
        table.validate()
        return table


@dataclass
class CalibrationProject:
    name: str = 'Power8GDI — V8 Reference'
    cylinders: int = 8
    pumps: int = 2
    format_version: int = FORMAT_VERSION
    tables: dict[str, CalibrationTable | CalibrationTable4D] = field(default_factory=dict)
    notes: str = 'Calibration data only. NEVER flash or run directly on an engine.'

    def validate(self) -> None:
        if self.format_version != FORMAT_VERSION:
            raise ValueError('Unsupported project version')
        if self.cylinders != 8 or self.pumps != 2:
            raise ValueError('This project is for eight cylinders and two HPFP channels')
        for name, table in self.tables.items():
            if name != table.name:
                raise ValueError(f'Table key and name mismatch: {name}')
            table.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            'format_version': self.format_version,
            'name': self.name, 'cylinders': self.cylinders, 'pumps': self.pumps,
            'notes': self.notes,
            'tables': {name: obj.to_dict() for name, obj in self.tables.items()}
        }

    @classmethod
    def from_dict(cls, obj: dict[str, Any]) -> 'CalibrationProject':
        allowed={'format_version','name','cylinders','pumps','notes','tables'}
        if not isinstance(obj,dict) or set(obj) - allowed:
            raise ValueError('Unexpected fields in project')
        ts=obj.get('tables',{})
        if not isinstance(ts,dict) or len(ts)>128:
            raise ValueError('Invalid table collection')
        version = obj['format_version']
        if type(version) is not int or version not in (1, FORMAT_VERSION):
            raise ValueError('Unsupported project version')
        result=cls(format_version=FORMAT_VERSION,
                   name=obj['name'],cylinders=obj['cylinders'], pumps=obj['pumps'],
                   notes=obj.get('notes',''),
                   tables={name:(CalibrationTable4D.from_dict(v) if 'z_bins' in v
                                 else CalibrationTable.from_dict(v)) for name,v in ts.items()})
        result.validate()
        return result

    def save(self, path: Path | str) -> None:
        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        payload=json.dumps(self.to_dict(),indent=2,ensure_ascii=False)+'\n'
        # A unique sibling permits atomic replacement without consuming another
        # window's temporary file or an existing user recovery sidecar.
        temp=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                    prefix=path.name+'.',suffix='.tmp',delete=False) as stream:
                temp=Path(stream.name)
                stream.write(payload)
            temp.replace(path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    @classmethod
    def load(cls, path: Path | str) -> 'CalibrationProject':
        file=Path(path)
        if file.stat().st_size>8_000_000:
            raise ValueError('Calibration project too large')
        return cls.from_dict(json.loads(file.read_text(encoding='utf-8')))


def _make(name: str, x: list[float], y: list[float], initial: float,
          bounds: tuple[float,float],x_name: str,y_name: str,unit: str,
          desc: str, critical=False) -> CalibrationTable:
    table=CalibrationTable(name,desc,x_name,y_name,unit,x,y,
            [[float(initial) for _ in x] for _ in y],*bounds,
            safety_class='safety_critical' if critical else 'calibration')
    table.validate()
    return table


def default_project() -> CalibrationProject:
    rpm=[1000,2000,3000,4000,5000,6000,7000,8000]
    pedal=[0,10,20,30,40,50,60,70,80,90,100]
    load=[40,70,100,130,160,190,220,250,280,310]
    p=CalibrationProject()
    ts=[
        _make('Fuel / VE',load,rpm,55,(0,150),'MAP [kPa abs]','RPM','%',
              'Volumetric efficiency (offline UI prototype)'),
        _make('Ignition / Advance',load,rpm,10,(-30,60),'MAP [kPa abs]','RPM','°BTDC',
              'Ignition base map — illustrative values ONLY',True),
        _make('Boost / Target',pedal,rpm,100,(0,400),'Pedal [%]','RPM','kPa abs',
              'Manifold pressure target, absolute'),
        _make('Boost / Feed-forward',list(range(70,341,30)),rpm,40,(0,100),
              'Target MAP [kPa abs]','RPM','% EWG','Requested actuator position'),
        _make('Knock / Threshold',load,rpm,50,(0,100),
              'Ignition load [%]','RPM','dBv', 'Per-cell knock threshold proposal',True),
        _make('DBW / Pedal translation',pedal,[800,1600,3200,4800,6400,8000],0,
              (0,100),'Pedal [%]','RPM','% TPS','Requested throttle position',True),
        _make('ALS / Ignition correction',pedal,rpm,0,(-50,20),
              'Pedal [%]','RPM','°','ALS-only spark correction',True),
        _make('HPFP / Shared target',load,rpm,10000,(0,45000),
              'MAP [kPa abs]','RPM','kPa','Requested rail pressure, not live output',True),
        _make('Oil / Target pressure',rpm,[30,50,70,90,110,130],350,
              (0,1200),'RPM','Oil temperature [°C]','kPa',
              'B58 oil pressure solenoid target — example only',True),
    ]
    ts[5].values=[[float(v) for v in pedal] for _ in ts[5].y_bins]
    # Illustrative 4D tables. Neither table is wired to rusEFI ECU memory yet.
    ethanol = [0, 50, 85, 100]
    ignition_ethanol = CalibrationTable4D(
        name='Ignition / Ethanol 4D',
        description='Prototype RPM × MAP × ethanol ignition surface; NOT engine-safe',
        x_label='MAP [kPa abs]', y_label='RPM', z_label='Ethanol [%]',
        value_unit='°BTDC', x_bins=load, y_bins=rpm, z_bins=ethanol,
        values=[[[5.0 for _ in load] for _ in rpm] for _ in ethanol],
        minimum=-30, maximum=60, safety_class='safety_critical',
    )
    gears = [1, 2, 3, 4, 5, 6]
    boost_gear = CalibrationTable4D(
        name='Boost / Target 4D by Gear',
        description='Prototype RPM × pedal × gear pressure target; example ONLY',
        x_label='Pedal [%]', y_label='RPM', z_label='Gear',
        value_unit='kPa abs', x_bins=pedal, y_bins=rpm, z_bins=gears,
        values=[[[100.0 for _ in pedal] for _ in rpm] for _ in gears],
        minimum=0, maximum=400, safety_class='safety_critical',
    )
    ts.extend([ignition_ethanol, boost_gear])
    p.tables={t.name:t for t in ts}
    p.validate()
    return p
