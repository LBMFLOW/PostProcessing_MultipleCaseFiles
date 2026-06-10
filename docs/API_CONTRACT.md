# Backend API Contract

The PyQt6 frontend calls the backend in process through a typed Python interface. These are not HTTP endpoints. They are the planned method calls that the UI layer should depend on.

All calls are currently scaffolded only. Implementations should live behind `BackendController` and preserve this boundary so UI code does not read simulation files directly.

## Data Types

The canonical request and response shapes are defined in `src/simpost/backend/api_contract.py`.

Use immutable request/response dataclasses at the boundary. Convert third-party library objects, such as NumPy arrays or Matplotlib figures, into explicit contract types before returning them to the UI.

## Calls

### `scan_directory(directory_path: str, extensions: list[str]) -> list[dict]`

Recursively scans a user-selected directory for simulation result files whose names end with any requested extension. The extension filter is only for discovery; matching files are parsed as comma-separated text even when the extension is not `.csv`.

Arguments:

- `directory_path`: directory selected by the user.
- `extensions`: one or more extensions, with or without leading dots, such as `["dat", "out", "res"]`.

Each returned dictionary contains:

- `path`: absolute full path.
- `filename`: base filename.
- `size_bytes`: file size in bytes.
- `modified_timestamp`: last modified timestamp from the filesystem.
- `row_count`: detected comma-separated data row count.
- `column_count`: detected comma-separated column count.
- `parse_warning`: non-fatal parse warning, or `None`.
- `parse_error`: parse failure message, or `None`.

Files with parse errors are still returned so the frontend can show them with a warning indicator and let the user decide whether to inspect them.

### `list_datasets() -> list[DatasetSummary]`

Returns datasets discovered during the current session.

Response fields:

- `dataset_id`: stable identifier for UI selection.
- `display_name`: human-readable label.
- `source_path`: originating file path.
- `variables`: available variable names.

### `parse_file_headers(filepath: str, name_row: int = 0, unit_row: int | None = 1) -> dict`

Parses parameter names and units from a comma-separated simulation file. Row indexes are zero-based in the backend API. The UI presents them as one-based row numbers.

Arguments:

- `filepath`: file selected in the scan results.
- `name_row`: zero-based row index containing parameter names.
- `unit_row`: zero-based row index containing units, or `None` when the file has no units row.

Response fields:

- `parameters`: stripped parameter names, in file order.
- `units`: stripped units aligned to `parameters`; absent units are returned as empty strings.
- `data_start_row`: zero-based row index where numeric data begins.
- `num_data_rows`: count of non-empty data rows after `data_start_row`.
- `warnings`: warning dictionaries for invalid metadata, such as empty or numeric parameter names.

The frontend stores user-edited parameter and unit overrides in application state only. It must not write those edits back to the source simulation file.

### `load_dataset(request: LoadDatasetRequest) -> DatasetDetail`

Loads metadata and lightweight preview information for a selected dataset.

Request fields:

- `dataset_id`: dataset to load.
- `load_options`: parser and normalization options.

Response fields:

- `summary`: dataset summary.
- `metadata`: dataset-level metadata.
- `axes`: available x-axis candidates.
- `series`: available y-series candidates.

### `get_plot_data(request: PlotDataRequest) -> PlotDataResponse`

Returns numeric series ready for plotting.

Request fields:

- `dataset_id`: source dataset.
- `x_variable`: x-axis variable.
- `y_variables`: one or more y-axis variables.
- `filters`: variable filters chosen in the UI.

Response fields:

- `x`: x-axis values.
- `series`: one or more named y-series.
- `units`: optional display units.

### `get_plot_defaults(dataset_id: str) -> PlotDefaults`

Returns suggested plotting defaults for a dataset.

Response fields:

- `x_variable`: default x-axis variable.
- `y_variables`: default y-axis variables.
- `line_styles`: per-series style hints.

### `export_plot_svg(request: ExportSvgRequest) -> ExportResult`

Exports the current plot state to an SVG file.

Request fields:

- `output_path`: destination SVG path.
- `plot_state`: serializable plot configuration.
- `width_inches`: export width.
- `height_inches`: export height.

Response fields:

- `output_path`: written SVG path.
- `bytes_written`: output size.

### `save_session(request: SaveSessionRequest) -> SessionResult`

Saves the current application session.

Request fields:

- `output_path`: destination session file.
- `session_state`: serializable UI/backend state.

Response fields:

- `path`: saved session path.

### `load_session(path: Path) -> SessionState`

Loads a previously saved session.

Response fields:

- `root_path`: last selected data directory.
- `selected_dataset_id`: active dataset.
- `plot_state`: saved plot configuration.

### `get_job_status(job_id: str) -> JobStatus`

Returns progress for a long-running scan, load, or export operation.

Response fields:

- `job_id`: job identifier.
- `state`: queued, running, complete, failed, or canceled.
- `progress`: optional value from 0.0 to 1.0.
- `message`: user-facing progress or error text.

### `cancel_job(job_id: str) -> JobStatus`

Requests cancellation for a long-running operation.

Response fields are the same as `get_job_status`.

## Error Behavior

Backend implementations should raise typed application exceptions rather than Qt exceptions. The UI layer is responsible for converting those failures into dialogs, status messages, or inline validation.

Planned exception categories:

- `InvalidDirectoryError`
- `UnsupportedFileError`
- `DatasetNotLoadedError`
- `PlotDataError`
- `ExportError`
- `SessionError`
