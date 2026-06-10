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
from simpost.backend.ingestion import (
    get_plot_data as load_plot_data,
    parse_file_headers,
    scan_directory,
)


class BackendController(BackendAPI):
    def scan_directory(self, directory_path: str, extensions: list[str]) -> list[dict]:
        return scan_directory(directory_path, extensions)

    def parse_file_headers(
        self,
        filepath: str,
        name_row: int = 0,
        unit_row: int | None = 1,
    ) -> dict:
        return parse_file_headers(filepath, name_row, unit_row)

    def list_datasets(self) -> list[DatasetSummary]:
        raise NotImplementedError

    def load_dataset(self, request: LoadDatasetRequest) -> DatasetDetail:
        raise NotImplementedError

    def get_plot_data(
        self,
        filepath: str,
        x_param: str,
        y_param: str,
        name_row: int,
        unit_row: int | None,
        data_start_row: int,
    ) -> dict:
        return load_plot_data(filepath, x_param, y_param, name_row, unit_row, data_start_row)

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
