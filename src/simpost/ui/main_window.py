"""Main application window scaffold."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

from PyQt6.QtCore import QSettings, QStandardPaths, Qt
from PyQt6.QtGui import QAction, QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QStatusBar,
)

from simpost.backend.label_formula import format_curve_label
from simpost.backend.controller import BackendController
from simpost.ui.plot_models import CurveState, CurveStyle, PlotStyleState
from simpost.ui.widgets.batch_export_dialog import BatchExportDialog
from simpost.ui.widgets.controls_panel import ControlsPanel
from simpost.ui.widgets.plot_panel import PlotPanel


COLORBLIND_SAFE_PALETTE = [
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#E69F00",
    "#56B4E9",
    "#332288",
    "#88CCEE",
    "#44AA99",
    "#117733",
    "#999933",
    "#882255",
]

SETTINGS_ORGANIZATION = "Simulation Tools"
SETTINGS_APPLICATION = "Simulation Post Processor"
SETTINGS_ENV_VAR = "SIMPOST_SETTINGS_PATH"
SETTINGS_FILENAME = "settings.ini"
FALLBACK_SETTINGS_FILENAME = ".simpost_settings.ini"
LAST_DIRECTORY_KEY = "scan/last_directory"
EXTENSIONS_KEY = "scan/extensions"
HEADER_NAME_ROW_KEY = "headers/name_row"
HEADER_USE_UNIT_ROW_KEY = "headers/use_unit_row"
HEADER_UNIT_ROW_KEY = "headers/unit_row"
HEADER_USE_LABEL_ROW_KEY = "headers/use_label_row"
HEADER_LABEL_ROW_KEY = "headers/label_row"
HEADER_CURVE_LABEL_FORMULA_KEY = "headers/curve_label_formula"


class MainWindow(QMainWindow):
    def __init__(self, backend: BackendController | None = None) -> None:
        super().__init__()

        self.backend = backend or BackendController()
        self.controls_panel = ControlsPanel()
        self.plot_panel = PlotPanel()
        self._curves: list[CurveState] = []
        self._next_curve_id = 1
        self._selected_curve_id: str | None = None
        self._plot_style = PlotStyleState.defaults()
        self._restoring_settings = False
        self._settings_file_path = self._resolve_settings_file_path()

        self.setWindowTitle("Simulation Post Processor")
        self.resize(1280, 800)

        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setWidget(self.controls_panel)
        controls_scroll.setMinimumWidth(500)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(controls_scroll)
        splitter.addWidget(self.plot_panel)
        splitter.setSizes([520, 760])

        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        self._build_menu()
        self._build_toolbar()
        self._connect_signals()
        self.controls_panel.set_plot_style(self._plot_style)
        self._restore_last_settings()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        self.open_action = QAction("&Open Directory...", self)
        self.open_action.setStatusTip("Select a simulation results directory")
        self.open_action.triggered.connect(self._browse_directory)
        file_menu.addAction(self.open_action)

        save_session_action = QAction("&Save Session...", self)
        save_session_action.setEnabled(False)
        file_menu.addAction(save_session_action)

        load_session_action = QAction("&Load Session...", self)
        load_session_action.setEnabled(False)
        file_menu.addAction(load_session_action)

        export_svg_action = QAction("Export Plot as &SVG...", self)
        export_svg_action.setEnabled(False)
        file_menu.addAction(export_svg_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = self.menuBar().addMenu("&View")
        reset_layout_action = QAction("&Reset Layout", self)
        reset_layout_action.setEnabled(False)
        view_menu.addAction(reset_layout_action)

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        open_action = QAction("Open Directory", self)
        open_action.triggered.connect(self._browse_directory)
        toolbar.addAction(open_action)

        export_action = QAction("Export SVG", self)
        export_action.setEnabled(False)
        toolbar.addAction(export_action)

    def _connect_signals(self) -> None:
        self.controls_panel.browse_requested.connect(self._browse_directory)
        self.controls_panel.scan_requested.connect(self._scan_directory)
        self.controls_panel.add_curve_requested.connect(self._add_curve)
        self.controls_panel.add_selected_files_curves_requested.connect(
            self._add_curves_for_selected_files
        )
        self.controls_panel.reset_plot_and_add_curves_requested.connect(
            self._reset_plot_and_add_curves
        )
        self.controls_panel.curve_label_changed.connect(self._rename_curve)
        self.controls_panel.curve_delete_requested.connect(self._delete_curve)
        self.controls_panel.curve_highlighted.connect(self._preview_curve)
        self.controls_panel.curve_selected.connect(self._select_curve)
        self.controls_panel.curve_style_changed.connect(self._update_curve_style)
        self.controls_panel.plot_style_changed.connect(self._update_plot_style)
        self.controls_panel.reset_all_styles_requested.connect(self._reset_all_styles)
        self.controls_panel.apply_uniform_style_requested.connect(self._apply_uniform_style)
        self.controls_panel.batch_export_requested.connect(self._open_batch_export_dialog)
        self.controls_panel.selection_changed.connect(self._update_selection_status)
        self.controls_panel.file_highlighted.connect(self._parse_highlighted_file_headers)
        self.controls_panel.header_config_changed.connect(self._parse_selected_file_headers)
        self.controls_panel.curve_label_formula_changed.connect(self._relabel_curves_from_formula)
        self.controls_panel.settings_changed.connect(self._save_last_settings)
        self.plot_panel.curve_selected.connect(self._select_curve)

    def _browse_directory(self) -> None:
        start_directory = self.controls_panel.directory_path()
        if not start_directory or not Path(start_directory).is_dir():
            start_directory = str(Path.home())
        directory_path = QFileDialog.getExistingDirectory(
            self,
            "Select simulation results directory",
            start_directory,
        )
        if not directory_path:
            return

        self.controls_panel.set_directory_path(directory_path)
        self.statusBar().showMessage(f"Selected directory: {directory_path}")

    def _scan_directory(self) -> None:
        self._save_last_settings()
        directory_path = self.controls_panel.directory_path()
        extensions = self.controls_panel.extensions()

        if not directory_path:
            self.statusBar().showMessage("Select a directory before scanning.")
            return
        if not extensions:
            self.statusBar().showMessage("Enter at least one file extension before scanning.")
            return

        self.statusBar().showMessage("Scanning files...")
        try:
            files = self.backend.scan_directory(directory_path, extensions)
        except (FileNotFoundError, NotADirectoryError, ValueError, OSError) as exc:
            self.controls_panel.set_files([])
            self.statusBar().showMessage(str(exc))
            return

        self.controls_panel.set_files(files)
        warning_count = sum(
            1 for file_info in files if file_info.get("parse_error") or file_info.get("parse_warning")
        )

        if not files:
            self.statusBar().showMessage("No matching files found.")
        elif warning_count:
            self.statusBar().showMessage(
                f"Found {len(files)} files. {warning_count} files have parse warnings."
            )
        else:
            self.statusBar().showMessage(f"Found {len(files)} files.")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_last_settings()
        super().closeEvent(event)

    def _restore_last_settings(self) -> None:
        settings = self._settings()
        restored = False

        self._restoring_settings = True
        try:
            if settings.contains(LAST_DIRECTORY_KEY):
                directory_path = self._settings_string(settings, LAST_DIRECTORY_KEY, "")
                self.controls_panel.set_directory_path(directory_path)
                restored = True

            if settings.contains(EXTENSIONS_KEY):
                extensions_text = self._settings_string(settings, EXTENSIONS_KEY, "")
                self.controls_panel.set_extensions_text(extensions_text)
                restored = True

            self.controls_panel.set_header_settings(
                {
                    "name_row": self._settings_int(settings, HEADER_NAME_ROW_KEY, 1),
                    "use_unit_row": self._settings_bool(settings, HEADER_USE_UNIT_ROW_KEY, True),
                    "unit_row": self._settings_int(settings, HEADER_UNIT_ROW_KEY, 2),
                    "use_label_row": self._settings_bool(settings, HEADER_USE_LABEL_ROW_KEY, False),
                    "label_row": self._settings_int(settings, HEADER_LABEL_ROW_KEY, 3),
                    "curve_label_formula": self._settings_string(
                        settings,
                        HEADER_CURVE_LABEL_FORMULA_KEY,
                        "",
                    ),
                }
            )
        finally:
            self._restoring_settings = False

        if restored:
            self.statusBar().showMessage("Restored last scan settings.")

    def _save_last_settings(self) -> None:
        if self._restoring_settings:
            return
        settings = self._settings()
        header_settings = self.controls_panel.header_settings()
        settings.setValue(LAST_DIRECTORY_KEY, self.controls_panel.directory_path())
        settings.setValue(EXTENSIONS_KEY, self.controls_panel.extensions_text())
        settings.setValue(HEADER_NAME_ROW_KEY, header_settings["name_row"])
        settings.setValue(HEADER_USE_UNIT_ROW_KEY, header_settings["use_unit_row"])
        settings.setValue(HEADER_UNIT_ROW_KEY, header_settings["unit_row"])
        settings.setValue(HEADER_USE_LABEL_ROW_KEY, header_settings["use_label_row"])
        settings.setValue(HEADER_LABEL_ROW_KEY, header_settings["label_row"])
        settings.setValue(
            HEADER_CURVE_LABEL_FORMULA_KEY,
            header_settings["curve_label_formula"],
        )
        settings.sync()

    def _settings(self) -> QSettings:
        return QSettings(str(self._settings_file_path), QSettings.Format.IniFormat)

    def _resolve_settings_file_path(self) -> Path:
        override = os.environ.get(SETTINGS_ENV_VAR)
        if override:
            return Path(override).expanduser()

        config_directory = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )
        candidates: list[Path] = []
        if config_directory:
            candidates.append(Path(config_directory) / SETTINGS_FILENAME)
        candidates.append(Path.cwd() / FALLBACK_SETTINGS_FILENAME)

        for candidate in candidates:
            if self._can_use_settings_path(candidate):
                return candidate
        return candidates[-1]

    def _can_use_settings_path(self, settings_path: Path) -> bool:
        probe_path = settings_path.parent / f".{settings_path.name}.probe"
        try:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            probe_path.write_text("", encoding="utf-8")
            probe_path.unlink(missing_ok=True)
        except OSError:
            return False
        return True

    def _settings_string(self, settings: QSettings, key: str, default: str) -> str:
        value = settings.value(key, default)
        return str(value) if value is not None else default

    def _settings_int(self, settings: QSettings, key: str, default: int) -> int:
        value = settings.value(key, default)
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    def _settings_bool(self, settings: QSettings, key: str, default: bool) -> bool:
        value = settings.value(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _update_selection_status(self, total: int, selected: int) -> None:
        self.statusBar().showMessage(f"{total} files found, {selected} selected")

    def _parse_selected_file_headers(self) -> None:
        file_info = self.controls_panel.selected_file()
        if file_info is None:
            self.controls_panel.clear_header_preview()
            return
        self._parse_highlighted_file_headers(file_info)

    def _parse_highlighted_file_headers(self, file_info: dict) -> None:
        if file_info.get("parse_error"):
            self.controls_panel.clear_header_preview()
            self.statusBar().showMessage(
                f"Cannot preview headers for {file_info['filename']}: {file_info['parse_error']}"
            )
            return

        name_row, unit_row, label_row = self.controls_panel.header_config()
        try:
            header_info = self.backend.parse_file_headers(
                str(file_info["path"]),
                name_row=name_row,
                unit_row=unit_row,
                label_row=label_row,
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            self.controls_panel.clear_header_preview()
            self.statusBar().showMessage(str(exc))
            return

        self.controls_panel.set_header_preview(file_info, header_info)
        warning_count = len(header_info.get("warnings", []))
        if warning_count:
            self.statusBar().showMessage(
                f"Parsed headers for {file_info['filename']} with {warning_count} warnings."
            )
        else:
            self.statusBar().showMessage(f"Parsed headers for {file_info['filename']}.")

    def _add_curve(self, reset_plot: bool = False) -> None:
        selections = self.controls_panel.plot_selections_for_current_file()
        if not selections:
            self.statusBar().showMessage("Select a file and plot axes before adding a curve.")
            return

        if reset_plot:
            self._reset_plot_state_for_new_parameters()

        added = 0
        for selection in selections:
            curve_label = str(selection["curve_label"] or selection["y_display"])
            if self._add_curve_from_selection(selection, curve_label):
                added += 1

        if added:
            self._refresh_curve_views()
            if reset_plot:
                self.statusBar().showMessage(f"Reset plot area and added {added} curve(s).")
            else:
                self.statusBar().showMessage(f"Added {added} curve(s).")
        elif reset_plot:
            self._refresh_curve_views()

    def _add_curves_for_selected_files(self, reset_plot: bool = False) -> None:
        base_selection = self.controls_panel.plot_selection()
        selected_files = self.controls_panel.selected_files()
        if base_selection is None:
            self.statusBar().showMessage("Select x and y parameters before adding curves.")
            return
        if not selected_files:
            self.statusBar().showMessage("Select at least one file before adding curves.")
            return

        if reset_plot:
            self._reset_plot_state_for_new_parameters()

        added = 0
        failures: list[str] = []
        for file_info in selected_files:
            if file_info.get("parse_error"):
                failures.append(str(file_info["filename"]))
                continue

            try:
                header_info = self.backend.parse_file_headers(
                    str(file_info["path"]),
                    name_row=base_selection["name_row"],
                    unit_row=base_selection["unit_row"],
                    label_row=base_selection["label_row"],
                )
                selection = {
                    **base_selection,
                    "filepath": str(file_info["path"]),
                    "filename": str(file_info["filename"]),
                    "data_start_row": int(header_info["data_start_row"]),
                    "curve_label": self._curve_label_from_header(
                        header_info,
                        base_selection["y_column_index"],
                        base_selection["y_display"],
                        str(file_info["filename"]),
                        base_selection["curve_label_formula"],
                        str(file_info["filename"]),
                    ),
                }
                if self._add_curve_from_selection(selection, str(selection["curve_label"])):
                    added += 1
            except (FileNotFoundError, ValueError, OSError):
                failures.append(str(file_info["filename"]))

        if added:
            self._refresh_curve_views()

        if failures:
            self.statusBar().showMessage(
                f"Added {added} curve(s). {len(failures)} selected file(s) could not be plotted."
            )
        elif reset_plot:
            self.statusBar().showMessage(f"Reset plot area and added {added} curve(s).")
        else:
            self.statusBar().showMessage(f"Added {added} curve(s) from selected files.")

    def _reset_plot_and_add_curves(self) -> None:
        if len(self.controls_panel.selected_files()) > 1:
            self._add_curves_for_selected_files(reset_plot=True)
        else:
            self._add_curve(reset_plot=True)

    def _reset_plot_state_for_new_parameters(self) -> None:
        self._curves = []
        self._selected_curve_id = None
        self._next_curve_id = 1
        self.plot_panel.reset_curve_visibility()
        self._plot_style.x_range.auto = True
        self._plot_style.y_range.auto = True
        self._plot_style.x_axis_title = ""
        self._plot_style.y_axis_title = ""
        self.controls_panel.set_plot_style(self._plot_style)

    def _add_curve_from_selection(self, selection: dict, curve_label: str) -> bool:
        try:
            plot_data = self.backend.get_plot_data(
                selection["filepath"],
                selection["x_param"],
                selection["y_param"],
                selection["name_row"],
                selection["unit_row"],
                selection["data_start_row"],
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            self.statusBar().showMessage(str(exc))
            return False

        plot_data["x_label"] = selection["x_label"]
        plot_data["y_label"] = selection["y_label"]
        default_style = CurveStyle(
            color=COLORBLIND_SAFE_PALETTE[
                (self._next_curve_id - 1) % len(COLORBLIND_SAFE_PALETTE)
            ]
        )
        curve = CurveState(
            id=f"curve-{self._next_curve_id}",
            label=curve_label,
            source_file=selection["filename"],
            source_path=selection["filepath"],
            x_source_param=selection["x_param"],
            y_source_param=selection["y_param"],
            x_param=selection["x_display"],
            y_param=selection["y_display"],
            name_row=selection["name_row"],
            unit_row=selection["unit_row"],
            label_row=selection["label_row"],
            curve_label_formula=selection["curve_label_formula"],
            data_start_row=selection["data_start_row"],
            y_column_index=selection["y_column_index"],
            x=list(plot_data["x"]),
            y=list(plot_data["y"]),
            x_label=plot_data["x_label"],
            y_label=plot_data["y_label"],
            style=deepcopy(default_style),
            default_style=default_style,
        )
        self._next_curve_id += 1
        self._curves.append(curve)
        self._selected_curve_id = curve.id
        return True

    def _rename_curve(self, curve_id: str, label: str) -> None:
        for curve in self._curves:
            if curve.id == curve_id:
                curve.label = label or curve.label
                break
        self._refresh_curve_views()

    def _relabel_curves_from_formula(self, formula: str) -> None:
        if self._restoring_settings or not self._curves:
            return

        formula = formula.strip()
        changed = 0
        header_cache: dict[tuple[str, int, int | None, int | None], dict] = {}
        needs_label_row = "curve_label" in formula

        for curve in self._curves:
            header_info = {"plot_labels": []}
            if needs_label_row:
                cache_key = (curve.source_path, curve.name_row, curve.unit_row, curve.label_row)
                if cache_key not in header_cache:
                    try:
                        header_cache[cache_key] = self.backend.parse_file_headers(
                            curve.source_path,
                            name_row=curve.name_row,
                            unit_row=curve.unit_row,
                            label_row=curve.label_row,
                        )
                    except (FileNotFoundError, ValueError, OSError):
                        header_cache[cache_key] = header_info
                header_info = header_cache[cache_key]

            new_label = self._curve_label_from_header(
                header_info,
                curve.y_column_index,
                curve.y_param,
                curve.label,
                formula,
                curve.source_file,
            )
            curve.curve_label_formula = formula
            if new_label != curve.label:
                curve.label = new_label
                changed += 1

        self._refresh_curve_views()
        if changed:
            self.statusBar().showMessage(f"Updated {changed} curve label(s) from formula.")

    def _delete_curve(self, curve_id: str) -> None:
        self._curves = [curve for curve in self._curves if curve.id != curve_id]
        if self._selected_curve_id == curve_id:
            self._selected_curve_id = self._curves[-1].id if self._curves else None
        self._refresh_curve_views()
        self.statusBar().showMessage("Curve removed.")

    def _refresh_curve_views(self) -> None:
        if self._selected_curve_id is not None and not self._curve_by_id(self._selected_curve_id):
            self._selected_curve_id = self._curves[-1].id if self._curves else None

        self.controls_panel.set_curves(self._curves, self._selected_curve_id)
        self.controls_panel.set_selected_curve(self._curve_by_id(self._selected_curve_id))
        self.plot_panel.render_curves(self._curves, self._plot_style, self._selected_curve_id)

    def _select_curve(self, curve_id: str) -> None:
        if self._curve_by_id(curve_id) is None:
            return
        self._selected_curve_id = curve_id
        self.controls_panel.set_selected_curve(self._curve_by_id(curve_id))
        self.plot_panel.render_curves(self._curves, self._plot_style, self._selected_curve_id)

    def _preview_curve(self, curve_id: str) -> None:
        curve = self._curve_by_id(curve_id)
        if curve is None:
            return
        self._selected_curve_id = curve_id
        self.controls_panel.set_selected_curve(curve, sync_selector=False)
        self.plot_panel.render_curves(self._curves, self._plot_style, self._selected_curve_id)

    def _update_curve_style(self, curve_id: str, style: CurveStyle) -> None:
        curve = self._curve_by_id(curve_id)
        if curve is None:
            return
        curve.style = style
        self._refresh_curve_views()

    def _update_plot_style(self, plot_style: PlotStyleState) -> None:
        self._plot_style = plot_style
        self.plot_panel.render_curves(self._curves, self._plot_style, self._selected_curve_id)

    def _reset_all_styles(self) -> None:
        for curve in self._curves:
            curve.style = deepcopy(curve.default_style)
        self._refresh_curve_views()
        self.statusBar().showMessage("Curve styles reset.")

    def _apply_uniform_style(self) -> None:
        source_curve = self._curve_by_id(self._selected_curve_id)
        if source_curve is None:
            self.statusBar().showMessage("Select a curve before applying a uniform style.")
            return

        uniform_style = deepcopy(source_curve.style)
        for curve in self._curves:
            curve.style = deepcopy(uniform_style)
        self._refresh_curve_views()
        self.statusBar().showMessage("Uniform style applied to all curves.")

    def _curve_label_from_header(
        self,
        header_info: dict,
        column_index: int,
        parameter: str,
        fallback: str,
        formula: str,
        file_name: str,
    ) -> str:
        labels = header_info.get("plot_labels", [])
        curve_label = ""
        if 0 <= column_index < len(labels):
            curve_label = str(labels[column_index]).strip()
        return format_curve_label(
            formula,
            curve_label,
            parameter,
            fallback,
            file_name=file_name,
        )

    def _curve_by_id(self, curve_id: str | None) -> CurveState | None:
        if curve_id is None:
            return None
        return next((curve for curve in self._curves if curve.id == curve_id), None)

    def _open_batch_export_dialog(self) -> None:
        template_curve = self._curve_by_id(self._selected_curve_id)
        if template_curve is None:
            self.statusBar().showMessage("Select a template curve before batch export.")
            return

        selected_files = self.controls_panel.selected_files()
        if not selected_files:
            self.statusBar().showMessage("Select at least one file before batch export.")
            return

        dialog = BatchExportDialog(self)
        dialog.start_requested.connect(lambda: self._run_batch_export(dialog))
        dialog.exec()

    def _run_batch_export(self, dialog: BatchExportDialog) -> None:
        output_directory = dialog.output_directory()
        filename_pattern = dialog.filename_pattern()
        if not output_directory:
            dialog.set_error("Choose an output directory before starting export.")
            return
        if not filename_pattern:
            dialog.set_error("Enter a filename pattern before starting export.")
            return

        template_curve = self._curve_by_id(self._selected_curve_id)
        if template_curve is None:
            dialog.set_error("Select a template curve before starting export.")
            return

        selected_files = self.controls_panel.selected_files()
        if not selected_files:
            dialog.set_error("Select at least one file before starting export.")
            return

        dialog.prepare_for_export(len(selected_files))
        plot_template = self._batch_export_template(
            template_curve,
            selected_files,
            output_directory,
            filename_pattern,
            dialog.auto_axis_ranges_per_file(),
        )

        def update_progress(completed: int, total: int, _result: dict) -> None:
            dialog.update_progress(completed, total)
            QApplication.processEvents()

        results = self.backend.batch_export_svg(plot_template, update_progress)
        dialog.set_summary(results)
        exported = sum(1 for result in results if result["success"])
        self.statusBar().showMessage(f"Batch export complete: {exported} of {len(results)} exported.")

    def _batch_export_template(
        self,
        template_curve: CurveState,
        selected_files: list[dict],
        output_directory: str,
        filename_pattern: str,
        auto_axis_ranges_per_file: bool,
    ) -> dict:
        plot_style = self._plot_style.to_dict()
        if auto_axis_ranges_per_file:
            plot_style["x_range"]["auto"] = True
            plot_style["y_range"]["auto"] = True
        else:
            plot_style.update(self.plot_panel.axis_ranges())

        return {
            "files": [
                {"path": str(file_info["path"]), "filename": str(file_info["filename"])}
                for file_info in selected_files
            ],
            "output_directory": output_directory,
            "filename_pattern": filename_pattern,
            "auto_axis_ranges_per_file": auto_axis_ranges_per_file,
            "x_param": template_curve.x_source_param,
            "y_param": template_curve.y_source_param,
            "x_display": template_curve.x_param,
            "y_display": template_curve.y_param,
            "x_label": template_curve.x_label,
            "y_label": template_curve.y_label,
            "curve_label": template_curve.label,
            "curve_label_formula": template_curve.curve_label_formula,
            "name_row": template_curve.name_row,
            "unit_row": template_curve.unit_row,
            "label_row": template_curve.label_row,
            "data_start_row": template_curve.data_start_row,
            "y_column_index": template_curve.y_column_index,
            "curve_style": template_curve.style.to_dict(),
            "plot_style": plot_style,
            "figure_size_inches": [8.0, 5.0],
            "dpi": 100,
        }
