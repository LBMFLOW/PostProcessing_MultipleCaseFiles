"""Typed boundary between the Qt frontend and backend services."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class DatasetSummary:
    dataset_id: str
    display_name: str
    source_path: Path
    variables: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoadOptions:
    parser_name: str | None = None
    normalize_units: bool = True
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadDatasetRequest:
    dataset_id: str
    load_options: LoadOptions = field(default_factory=LoadOptions)


@dataclass(frozen=True)
class DatasetDetail:
    summary: DatasetSummary
    metadata: dict[str, Any] = field(default_factory=dict)
    axes: tuple[str, ...] = ()
    series: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlotDataRequest:
    dataset_id: str
    x_variable: str
    y_variables: tuple[str, ...]
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlotSeries:
    name: str
    values: tuple[float, ...]


@dataclass(frozen=True)
class PlotDataResponse:
    x: tuple[float, ...]
    series: tuple[PlotSeries, ...]
    units: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LineStyle:
    color: str = "#1f77b4"
    width: float = 1.5
    pattern: str = "solid"
    marker: str | None = None


@dataclass(frozen=True)
class PlotDefaults:
    x_variable: str | None = None
    y_variables: tuple[str, ...] = ()
    line_styles: dict[str, LineStyle] = field(default_factory=dict)


@dataclass(frozen=True)
class PlotState:
    dataset_id: str | None = None
    x_variable: str | None = None
    y_variables: tuple[str, ...] = ()
    filters: dict[str, Any] = field(default_factory=dict)
    line_styles: dict[str, LineStyle] = field(default_factory=dict)


@dataclass(frozen=True)
class ExportSvgRequest:
    output_path: Path
    plot_state: PlotState
    width_inches: float = 8.0
    height_inches: float = 5.0


@dataclass(frozen=True)
class ExportResult:
    output_path: Path
    bytes_written: int


@dataclass(frozen=True)
class SessionState:
    root_path: Path | None = None
    selected_dataset_id: str | None = None
    plot_state: PlotState = field(default_factory=PlotState)


@dataclass(frozen=True)
class SaveSessionRequest:
    output_path: Path
    session_state: SessionState


@dataclass(frozen=True)
class SessionResult:
    path: Path


@dataclass(frozen=True)
class JobStatus:
    job_id: str
    state: JobState
    progress: float | None = None
    message: str = ""


class BackendAPI(Protocol):
    def scan_directory(self, directory_path: str, extensions: list[str]) -> list[dict]:
        """Scan a directory for supported simulation result files."""

    def parse_file_headers(
        self,
        filepath: str,
        name_row: int = 0,
        unit_row: int | None = 1,
    ) -> dict:
        """Parse parameter names, units, data start row, and warnings from a file."""

    def list_datasets(self) -> list[DatasetSummary]:
        """Return datasets discovered in the current session."""

    def load_dataset(self, request: LoadDatasetRequest) -> DatasetDetail:
        """Load metadata and preview information for a dataset."""

    def get_plot_data(
        self,
        filepath: str,
        x_param: str,
        y_param: str,
        name_row: int,
        unit_row: int | None,
        data_start_row: int,
    ) -> dict:
        """Return numeric x/y arrays and axis labels for plotting."""

    def get_plot_defaults(self, dataset_id: str) -> PlotDefaults:
        """Return suggested plot defaults for a dataset."""

    def export_plot_svg(self, request: ExportSvgRequest) -> ExportResult:
        """Export the requested plot state to SVG."""

    def save_session(self, request: SaveSessionRequest) -> SessionResult:
        """Persist the current session."""

    def load_session(self, path: Path) -> SessionState:
        """Load a previously persisted session."""

    def get_job_status(self, job_id: str) -> JobStatus:
        """Return status for a long-running backend job."""

    def cancel_job(self, job_id: str) -> JobStatus:
        """Request cancellation for a long-running backend job."""
