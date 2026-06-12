# Simulation Post Processor

Desktop scaffold for a local simulation post-processing application with a Python backend and a native PyQt6 frontend.

## Framework Choice

This scaffold uses **PyQt6 with an embedded Matplotlib canvas**.

PyQt6 is the best fit for this application because the requirements are local-first and desktop-oriented:

- Native filesystem access is direct through Python and Qt, without a browser permission model or local web server bridge.
- Matplotlib integrates cleanly with Qt, supports interactive 2D scientific plotting, and can export figures to SVG.
- Qt provides mature desktop controls such as combo boxes, sliders, color dialogs, file dialogs, splitters, toolbars, and menus.
- Engineers and scientists usually benefit from dense, predictable desktop workflows over a web-style application shell.
- Packaging is simpler than a React/FastAPI or Tauri/Python sidecar architecture because the UI and backend run in one Python process.

Alternatives considered:

- **React/TypeScript + Flask/FastAPI**: strong UI ecosystem, but adds browser/server lifecycle, filesystem access routing, and packaging overhead for a local desktop tool.
- **Dear PyGui**: fast for immediate-mode tools, but less mature for native desktop conventions and SVG scientific plot export.
- **Tauri + Python sidecar**: good for polished web UIs, but introduces IPC and sidecar packaging complexity before the application needs it.

If GPL/commercial licensing is a concern for PyQt6, the same architecture can be ported to PySide6 with minimal structural changes.

## Local Verification

PyQt6 was smoke-tested in a project-local virtual environment.

Verified versions:

- PyQt6 `6.11.0`
- Qt runtime package `PyQt6-Qt6 6.11.1`
- Matplotlib `3.10.9`
- NumPy `2.4.6`

The dependency versions are pinned in `pyproject.toml` and `requirements.txt` to reduce Windows Qt DLL churn.

## Project Structure

```text
.
|-- README.md
|-- docs/
|   `-- API_CONTRACT.md
|-- pyproject.toml
|-- requirements.txt
|-- scripts/
|   `-- smoke_test_qt.py
|-- tests/
|   `-- test_ingestion.py
`-- src/
    `-- simpost/
        |-- __init__.py
        |-- app.py
        |-- backend/
        |   |-- __init__.py
        |   |-- api_contract.py
        |   |-- controller.py
        |   |-- export.py
        |   `-- ingestion.py
        `-- ui/
            |-- __init__.py
            |-- main_window.py
            |-- plot_models.py
            `-- widgets/
                |-- __init__.py
                |-- batch_export_dialog.py
                |-- controls_panel.py
                `-- plot_panel.py
```

## Setup

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Run the frontend smoke test:

```powershell
python scripts\smoke_test_qt.py
```

Expected output includes:

```text
MainWindow smoke test ok
QApplication event loop ok
```

Run the desktop shell:

```powershell
simpost
```

Or run the module directly:

```powershell
python -m simpost.app
```

On Windows, you can also double-click `run_app.bat` from the repository root.

## Current Scope

This project currently defines:

- The desktop application entry point.
- A main Qt window layout.
- A directory scan UI with extension filtering and selectable file rows.
- Local persistence for the last scan directory, extension text, and header configuration.
- A backend file ingestion function for recursively scanning comma-separated files with non-standard extensions.
- Header detection for parameter names and units with editable in-memory overrides.
- Core 2D plotting for selected x/y parameters using embedded Matplotlib.
- Multi-curve plotting from multiple selected files or multiple Y variables from one file.
- A curve list with editable labels and delete controls that drives reactive plot redraws.
- Axis range, plot title, axis title, legend, per-curve style, and global plot style controls backed by structured dataclasses.
- Batch SVG export that applies one template curve/style to every selected case file.
- A typed backend API boundary.
- The planned frontend/backend contract.

Filtering and session persistence are not implemented yet. Matplotlib's built-in toolbar also supports saving the current interactive figure.

## Plotting Workflow

The Plot Configuration panel supports two multi-curve modes:

- Multiple selected files: choose one X parameter and one Y parameter, check files in the file list, then use `Add curves for all selected files`.
- Multiple Y variables: choose one highlighted file, choose an X parameter, add one or more Y variables with `+ Add Y variable`, then use `Add curve(s)`.

Use `Reset plot area and add curves` after changing X/Y parameters when you want a new figure instead of adding the new curves to the existing plot. This clears current curves, resets X/Y ranges to Auto, clears X/Y title overrides, and then adds curves using the current selection.

Use the trace button on the plot toolbar to inspect values on the selected curve. Click or drag across the plot while tracing is active to move the X-axis value tag; the Y-axis value tag follows the selected curve and dashed guides mark the intersection. Double-click the yellow X tag to enter a numeric X value, or right-click it and choose `Save y-axis values` to export the current Y values for plotted curves to CSV.

Use `Select all files` above the file list to check or uncheck large batches at once. Header Configuration can optionally read default curve-label prefix text from a user-selected row in each data file. A single non-empty label cell is reused for every plotted variable from that file.

The app remembers the last directory, extension text, parameter row, units row setting, curve-label row setting, and curve-label formula when it is closed and restores them the next time it starts.

Curve labels are built from the curve label formula. The formula can use `curve_label`, `parameter`, and `file_name`. The default formula is `('curve_label'-{'|','.trn'}+"_"+'parameter')`, which removes `|` and `.trn` from the label-row value, adds `_`, then adds the selected parameter name. Use a formula such as `('file_name'-{'.trn'}+"_"+'parameter')` to build labels from the case data filename instead.

Changing the curve label formula also reapplies it to currently plotted curves and refreshes the legend, using each curve's stored source file and parameter metadata.

For GT-style files with a first-line case header followed by parameter names and units, use Parameter row `2`, units row `3`, and curve label row `1`.

Plotted curves appear in the Curves panel. Curve labels are editable inline, and the delete button removes a curve from both the list and the plot. The plot redraws from the curve list whenever curves are added, renamed, or removed.

Curves can be selected from the Curves table, from the Selected Curve label dropdown, or by clicking a plotted line directly. The selected curve is drawn above the others with a thicker highlighted stroke. Browsing labels in the dropdown previews that curve highlight before editing its style.

## Style Controls

The Style panel includes:

- Manual or automatic X/Y axis ranges.
- Per-curve color, line style, line weight, marker, marker size, opacity, and label controls for the selected curve.
- Plot title, X/Y axis title overrides, legend location/style controls including outside plot placement, global font size, and grid controls.
- Reset all styles and apply-uniform-style actions.

Curve and plot styling state is defined in `src/simpost/ui/plot_models.py` as Python dataclasses so it can be serialized and reapplied by later save/export workflows.

## Batch Export

Batch export uses the currently selected curve as the plot template. Select the files to export in the file list, configure the template curve and plot style, then click `Batch Export`.

The export dialog asks for:

- Output directory.
- Filename pattern, with tokens such as `{casename}`, `{filename}`, `{x_param}`, and `{y_param}`.
- Whether each exported SVG should use auto axis ranges or lock to the template plot ranges.

The backend renders each selected file with Matplotlib's SVG backend and returns a per-file success/failure summary.

## Backend API Contract

The native UI and backend run in the same Python process. The frontend should call the backend through the typed `BackendAPI` interface in `src/simpost/backend/api_contract.py`.

See `docs/API_CONTRACT.md` for the planned calls, request models, response models, and error behavior.
