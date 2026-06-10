"""Structured plot state models."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class CurveStyle:
    color: str
    line_style: str = "solid"
    line_weight: float = 1.5
    marker_style: str = "none"
    marker_size: float = 6.0
    opacity: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CurveState:
    id: str
    label: str
    source_file: str
    source_path: str
    x_param: str
    y_param: str
    x: list[float]
    y: list[float]
    x_label: str
    y_label: str
    style: CurveStyle
    default_style: CurveStyle

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AxisRangeState:
    auto: bool = True
    minimum: float = 0.0
    maximum: float = 1.0


@dataclass
class GridStyle:
    enabled: bool = True
    color: str = "#b0b0b0"
    opacity: float = 0.3


@dataclass
class PlotStyleState:
    x_range: AxisRangeState
    y_range: AxisRangeState
    font_size: int = 10
    grid: GridStyle | None = None

    def __post_init__(self) -> None:
        if self.grid is None:
            self.grid = GridStyle()

    @classmethod
    def defaults(cls) -> "PlotStyleState":
        return cls(x_range=AxisRangeState(), y_range=AxisRangeState(), grid=GridStyle())
