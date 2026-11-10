"""Inputs and results independent of the mesh engine and HTTP framework."""
from dataclasses import dataclass, asdict
import math
from numbers import Real


@dataclass(frozen=True)
class BodyMeasurements:
    height: float
    shoulderWidth: float
    chest: float
    waist: float
    hip: float

    def __post_init__(self):
        # This prototype fits adult bodies; reject unsupported inputs explicitly.
        limits = {"height": (130, 220), "shoulderWidth": (25, 65),
                  "chest": (50, 180), "waist": (45, 180), "hip": (55, 190)}
        for name, value in asdict(self).items():
            low, high = limits[name]
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name}: expected {low}–{high} cm")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class DeclaredBodyData:
    height_cm: float
    weight_kg: float

    def __post_init__(self):
        for name, value, low, high in [("height_cm", self.height_cm, 130, 220),
                                       ("weight_kg", self.weight_kg, 30, 250)]:
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name}: expected {low}–{high}")


@dataclass(frozen=True)
class PhotoEstimationRequest:
    declared: DeclaredBodyData
    image: bytes
    width: int
    height: int
