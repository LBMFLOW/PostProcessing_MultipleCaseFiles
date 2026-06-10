"""Main application window scaffold."""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QStatusBar,
)

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
        self.controls_panel.curve_label_changed.connect(self._rename_curve)
        self.controls_panel.curve_delete_requested.connect(self._delete_curve)
        self.controls_panel.curve_selected.connect(self._select_curve)
        self.controls_panel.curve_style_changed.connect(self._update_curve_style)
        self.controls_panel.plot_style_changed.connect(self._update_plot_style)
        self.controls_panel.reset_all_styles_requested.connect(self._reset_all_styles)
        self.controls_panel.apply_uniform_style_requested.connect(self._apply_uniform_style)
        self.controls_panel.batch_export_requested.connect(self._open_batch_export_dialog)
        self.controls_panel.selection_changed.connect(self._update_selection_status)
        self.controls_panel.file_highlighted.connect(self._parse_highlighted_file_headers)
        self.controls_panel.header_config_changed.connect(self._parse_selected_file_headers)

    def _browse_directory(self) -> None:
        start_directory = self.controls_panel.directory_path() or str(Path.home())
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

    def _add_curve(self) -> None:
        selections = self.controls_panel.plot_selections_for_current_file()
        if not selections:
            self.statusBar().showMessage("Select a file and plot axes before adding a curve.")
            return

        added = 0
        for selection in selections:
            curve_label = str(selection["curve_label"] or selection["y_display"])
            if self._add_curve_from_selection(selection, curve_label):
                added += 1

        if added:
            self._refresh_curve_views()
            self.statusBar().showMessage(f"Added {added} curve(s).")

    def _add_curves_for_selected_files(self) -> None:
        base_selection = self.controls_panel.plot_selection()
        selected_files = self.controls_panel.selected_files()
        if base_selection is None:
            self.statusBar().showMessage("Select x and y parameters before adding curves.")
            return
        if not selected_files:
            self.statusBar().showMessage("Select at least one file before adding curves.")
            return

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
        else:
            self.statusBar().showMessage(f"Added {added} curve(s) from selected files.")

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
        self.plot_panel.render_curves(self._curves, self._plot_style)

    def _select_curve(self, curve_id: str) -> None:
        self._selected_curve_id = curve_id
        self.controls_panel.set_selected_curve(self._curve_by_id(curve_id))

    def _update_curve_style(self, curve_id: str, style: CurveStyle) -> None:
        curve = self._curve_by_id(curve_id)
        if curve is None:
            return
        curve.style = style
        self._refresh_curve_views()

    def _update_plot_style(self, plot_style: PlotStyleState) -> None:
        self._plot_style = plot_style
        self.plot_panel.render_curves(self._curves, self._plot_style)

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
        fallback: str,
    ) -> str:
        labels = header_info.get("plot_labels", [])
        if 0 <= column_index < len(labels):
            label = str(labels[column_index]).strip()
            if label:
                return label
        return fallback

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
