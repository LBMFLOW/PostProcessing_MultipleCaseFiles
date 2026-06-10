"""Backend controller.

The UI should depend on this controller through the BackendAPI protocol.
"""

from __future__ import annotations

from pathlib import Path

from simpost.backend.api_contract import (
    BackendAPI,
    DatasetDetail,
    DatasetSummary,
    ExportResult,
    ExportSvgRequest,
    JobStatus,
    LoadDatasetRequest,
    PlotDataRequest,
    PlotDataResponse,
    PlotDefaults,
    SaveSessionRequest,
    SessionResult,
    SessionState,
)
from simpost.backend.ingestion import scan_directory


class BackendController(BackendAPI):
    def scan_directory(self, directory_path: str, extensions: list[str]) -> list[dict]:
        return scan_directory(directory_path, extensions)

    def list_datasets(self) -> list[DatasetSummary]:
        raise NotImplementedError

    def load_dataset(self, request: LoadDatasetRequest) -> DatasetDetail:
        raise NotImplementedError

    def get_plot_data(self, request: PlotDataRequest) -> PlotDataResponse:
        raise NotImplementedError

    def get_plot_defaults(self, dataset_id: str) -> PlotDefaults:
        raise NotImplementedError

    def export_plot_svg(self, request: ExportSvgRequest) -> ExportResult:
        raise NotImplementedError

    def save_session(self, request: SaveSessionRequest) -> SessionResult:
        raise NotImplementedError

    def load_session(self, path: Path) -> SessionState:
        raise NotImplementedError

    def get_job_status(self, job_id: str) -> JobStatus:
        raise NotImplementedError

    def cancel_job(self, job_id: str) -> JobStatus:
        raise NotImplementedError
