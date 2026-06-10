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

PyQt6 was smoke-tested on this computer in a project-local virtual environment.

Verified versions:

- PyQt6 `6.11.0`
- Qt runtime package `PyQt6-Qt6 6.11.1`
- Matplotlib `3.10.9`
- NumPy `2.4.6`

The dependency versions are pinned in `pyproject.toml` and `requirements.txt` to reduce Windows Qt DLL churn.

## Project Structure

```text
.
├── README.md
├── docs/
│   └── API_CONTRACT.md
├── pyproject.toml
├── requirements.txt
└── src/
    └── simpost/
        ├── __init__.py
        ├── app.py
        ├── backend/
        │   ├── __init__.py
        │   ├── api_contract.py
        │   └── controller.py
        └── ui/
            ├── __init__.py
            ├── main_window.py
            └── widgets/
                ├── __init__.py
                ├── controls_panel.py
                └── plot_panel.py
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

## Current Scope

This project currently defines:

- The desktop application entry point.
- A main Qt window layout.
- A directory scan UI with extension filtering and selectable file rows.
- A backend file ingestion function for recursively scanning comma-separated files with non-standard extensions.
- Header detection for parameter names and units with editable in-memory overrides.
- Core 2D plotting for selected x/y parameters using embedded Matplotlib.
- A typed backend API boundary.
- The planned frontend/backend contract.

Filtering, session persistence, and explicit SVG export workflow logic are not implemented yet. Matplotlib's built-in toolbar supports saving figures, including SVG output.

## Backend API Contract

The native UI and backend run in the same Python process. The frontend should call the backend through the typed `BackendAPI` interface in `src/simpost/backend/api_contract.py`.

See `docs/API_CONTRACT.md` for the planned calls, request models, response models, and error behavior.
