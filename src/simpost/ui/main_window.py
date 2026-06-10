"""Main application window scaffold."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFileDialog, QMainWindow, QSplitter, QStatusBar

from simpost.backend.controller import BackendController
from simpost.ui.widgets.controls_panel import ControlsPanel
from simpost.ui.widgets.plot_panel import PlotPanel


class MainWindow(QMainWindow):
    def __init__(self, backend: BackendController | None = None) -> None:
        super().__init__()

        self.backend = backend or BackendController()
        self.controls_panel = ControlsPanel()
        self.plot_panel = PlotPanel()

        self.setWindowTitle("Simulation Post Processor")
        self.resize(1280, 800)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.controls_panel)
        splitter.addWidget(self.plot_panel)
        splitter.setSizes([460, 820])

        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        self._build_menu()
        self._build_toolbar()
        self._connect_signals()

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

        name_row, unit_row = self.controls_panel.header_config()
        try:
            header_info = self.backend.parse_file_headers(
                str(file_info["path"]),
                name_row=name_row,
                unit_row=unit_row,
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
