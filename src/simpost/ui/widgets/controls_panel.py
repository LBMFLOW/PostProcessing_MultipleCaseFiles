"""Plot and dataset controls scaffold."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ControlsPanel(QWidget):
    browse_requested = pyqtSignal()
    scan_requested = pyqtSignal()
    selection_changed = pyqtSignal(int, int)
    file_highlighted = pyqtSignal(dict)
    header_config_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        self._directory_path = ""
        self._files: list[dict] = []
        self._current_file: dict | None = None
        self._current_header_config: tuple[int, int | None] | None = None
        self._header_overrides: dict[str, dict] = {}
        self._updating_table = False
        self._updating_header = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        layout.addWidget(self._build_data_group())
        layout.addWidget(self._build_file_list_group(), stretch=1)
        layout.addWidget(self._build_header_group(), stretch=1)
        layout.addWidget(self._build_axes_group())
        layout.addWidget(self._build_style_group())

    def _build_data_group(self) -> QGroupBox:
        group = QGroupBox("Scan")
        layout = QVBoxLayout(group)

        self.directory_label = QLabel("No directory selected")
        self.directory_label.setWordWrap(True)

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_requested.emit)

        directory_row = QHBoxLayout()
        directory_row.addWidget(self.directory_label, stretch=1)
        directory_row.addWidget(self.browse_button)

        self.extensions_input = QLineEdit("dat, out, res, txt")
        self.extensions_input.setPlaceholderText("dat, out, res")

        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self.scan_requested.emit)

        form = QFormLayout()
        form.addRow("Directory", directory_row)
        form.addRow("Extensions", self.extensions_input)
        form.addRow("", self.scan_button)

        self.scan_summary_label = QLabel("0 files found, 0 selected")

        layout.addLayout(form)
        layout.addWidget(self.scan_summary_label)
        return group

    def _build_file_list_group(self) -> QGroupBox:
        group = QGroupBox("Files")
        layout = QVBoxLayout(group)

        self.file_table = QTableWidget(0, 6)
        self.file_table.setHorizontalHeaderLabels(["Use", "", "Filename", "Rows", "Columns", "Size"])
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.file_table.itemChanged.connect(self._handle_file_selection_changed)
        self.file_table.itemSelectionChanged.connect(self._emit_highlighted_file)

        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.file_table)
        return group

    def _build_header_group(self) -> QGroupBox:
        group = QGroupBox("Header Configuration")
        layout = QVBoxLayout(group)

        self.name_row_spin = QSpinBox()
        self.name_row_spin.setRange(1, 999_999)
        self.name_row_spin.setValue(1)
        self.name_row_spin.valueChanged.connect(self.header_config_changed.emit)

        self.unit_row_checkbox = QCheckBox("Use units row")
        self.unit_row_checkbox.setChecked(True)
        self.unit_row_checkbox.stateChanged.connect(self._handle_unit_row_enabled_changed)

        self.unit_row_spin = QSpinBox()
        self.unit_row_spin.setRange(1, 999_999)
        self.unit_row_spin.setValue(2)
        self.unit_row_spin.valueChanged.connect(self.header_config_changed.emit)

        row_form = QFormLayout()
        row_form.addRow("Parameter row", self.name_row_spin)
        row_form.addRow(self.unit_row_checkbox, self.unit_row_spin)

        self.header_summary_label = QLabel("Select a file to preview headers")

        self.header_preview_table = QTableWidget(0, 3)
        self.header_preview_table.setHorizontalHeaderLabels(["", "Parameter", "Unit"])
        self.header_preview_table.verticalHeader().setVisible(False)
        self.header_preview_table.setAlternatingRowColors(True)
        self.header_preview_table.itemChanged.connect(self._handle_header_item_changed)

        header = self.header_preview_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        layout.addLayout(row_form)
        layout.addWidget(self.header_summary_label)
        layout.addWidget(self.header_preview_table)
        return group

    def _build_axes_group(self) -> QGroupBox:
        group = QGroupBox("Axes")
        form = QFormLayout(group)

        self.x_axis_selector = QComboBox()
        self.x_axis_selector.addItem("Select x variable")
        self.x_axis_selector.setEnabled(False)

        self.y_axis_selector = QComboBox()
        self.y_axis_selector.addItem("Select y variable")
        self.y_axis_selector.setEnabled(False)

        form.addRow("X", self.x_axis_selector)
        form.addRow("Y", self.y_axis_selector)
        return group

    def _build_style_group(self) -> QGroupBox:
        group = QGroupBox("Style")
        form = QFormLayout(group)

        self.color_button = QPushButton("Color")
        self.color_button.setEnabled(False)

        self.line_style_selector = QComboBox()
        self.line_style_selector.addItems(["Solid", "Dashed", "Dotted", "Dash-dot"])
        self.line_style_selector.setEnabled(False)

        self.line_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.line_width_slider.setRange(1, 80)
        self.line_width_slider.setValue(15)
        self.line_width_slider.setEnabled(False)

        form.addRow("Line color", self.color_button)
        form.addRow("Line style", self.line_style_selector)
        form.addRow("Line width", self.line_width_slider)
        return group

    def directory_path(self) -> str:
        return self._directory_path

    def set_directory_path(self, directory_path: str) -> None:
        self._directory_path = directory_path
        self.directory_label.setText(directory_path or "No directory selected")

    def extensions(self) -> list[str]:
        return [
            extension.strip()
            for extension in self.extensions_input.text().split(",")
            if extension.strip()
        ]

    def set_files(self, files: list[dict]) -> None:
        self._files = files
        self._current_file = None
        self._updating_table = True
        self.file_table.setRowCount(len(files))

        warning_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
        for row, file_info in enumerate(files):
            warning_text = file_info.get("parse_error") or file_info.get("parse_warning") or ""
            include_item = QTableWidgetItem()
            include_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            include_item.setCheckState(
                Qt.CheckState.Unchecked if warning_text else Qt.CheckState.Checked
            )
            include_item.setData(Qt.ItemDataRole.UserRole, file_info)
            self.file_table.setItem(row, 0, include_item)

            warning_item = QTableWidgetItem()
            warning_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            if warning_text:
                warning_item.setIcon(warning_icon)
                warning_item.setToolTip(str(warning_text))
            self.file_table.setItem(row, 1, warning_item)

            self.file_table.setItem(row, 2, self._read_only_item(str(file_info["filename"])))
            self.file_table.setItem(row, 3, self._read_only_item(str(file_info["row_count"])))
            self.file_table.setItem(row, 4, self._read_only_item(str(file_info["column_count"])))
            self.file_table.setItem(
                row,
                5,
                self._read_only_item(self._format_size(int(file_info["size_bytes"]))),
            )

        self._updating_table = False
        if files:
            self.file_table.selectRow(0)
        else:
            self.clear_header_preview()
        self._update_summary()

    def selected_files(self) -> list[dict]:
        selected: list[dict] = []
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    def selected_file(self) -> dict | None:
        selected_rows = self.file_table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        item = self.file_table.item(selected_rows[0].row(), 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def header_config(self) -> tuple[int, int | None]:
        name_row = self.name_row_spin.value() - 1
        unit_row = self.unit_row_spin.value() - 1 if self.unit_row_checkbox.isChecked() else None
        return name_row, unit_row

    def set_header_preview(self, file_info: dict, header_info: dict) -> None:
        self._current_file = file_info
        self._current_header_config = self.header_config()

        path = str(file_info["path"])
        parameters = list(header_info["parameters"])
        units = list(header_info["units"])
        override = self._header_overrides.get(path)
        if (
            override
            and override.get("config") == self._current_header_config
            and len(override.get("parameters", [])) == len(parameters)
        ):
            parameters = list(override["parameters"])
            units = list(override["units"])

        general_warnings: list[str] = []
        for warning in header_info.get("warnings", []):
            column = warning.get("column")
            if not isinstance(column, int):
                general_warnings.append(str(warning["message"]))

        self._updating_header = True
        self.header_preview_table.setRowCount(len(parameters))

        for row, parameter in enumerate(parameters):
            warning_item = QTableWidgetItem()
            warning_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.header_preview_table.setItem(row, 0, warning_item)

            parameter_item = QTableWidgetItem(parameter)
            parameter_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEditable
            )
            self.header_preview_table.setItem(row, 1, parameter_item)

            unit_item = QTableWidgetItem(units[row] if row < len(units) else "")
            unit_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEditable
            )
            self.header_preview_table.setItem(row, 2, unit_item)
            self._refresh_parameter_warning(row)

        summary = (
            f"{len(parameters)} parameters, {header_info['num_data_rows']} data rows "
            f"(data starts at row {header_info['data_start_row'] + 1})"
        )
        if general_warnings:
            summary = f"{summary}. {' '.join(general_warnings)}"
        self.header_summary_label.setText(summary)

        self._updating_header = False
        self._store_current_header_overrides()
        self._populate_axis_selectors(parameters)

    def clear_header_preview(self) -> None:
        self._current_file = None
        self._current_header_config = None
        self.header_summary_label.setText("Select a file to preview headers")
        self.header_preview_table.setRowCount(0)
        self._populate_axis_selectors([])

    def _emit_highlighted_file(self) -> None:
        if self._updating_table:
            return
        file_info = self.selected_file()
        if file_info is None:
            self.clear_header_preview()
            return
        self.file_highlighted.emit(file_info)

    def _handle_file_selection_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_table or item.column() != 0:
            return
        self._update_summary()

    def _handle_unit_row_enabled_changed(self) -> None:
        self.unit_row_spin.setEnabled(self.unit_row_checkbox.isChecked())
        self.header_config_changed.emit()

    def _handle_header_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_header or item.column() not in (1, 2):
            return
        if item.column() == 1:
            self._refresh_parameter_warning(item.row())
        self._store_current_header_overrides()
        self._populate_axis_selectors(self._current_parameters())

    def _store_current_header_overrides(self) -> None:
        if self._current_file is None or self._current_header_config is None:
            return

        self._header_overrides[str(self._current_file["path"])] = {
            "config": self._current_header_config,
            "parameters": self._current_parameters(),
            "units": self._current_units(),
        }

    def _current_parameters(self) -> list[str]:
        parameters: list[str] = []
        for row in range(self.header_preview_table.rowCount()):
            item = self.header_preview_table.item(row, 1)
            parameters.append(item.text().strip() if item is not None else "")
        return parameters

    def _current_units(self) -> list[str]:
        units: list[str] = []
        for row in range(self.header_preview_table.rowCount()):
            item = self.header_preview_table.item(row, 2)
            units.append(item.text().strip() if item is not None else "")
        return units

    def _populate_axis_selectors(self, parameters: list[str]) -> None:
        display_parameters = [
            parameter if parameter else f"Column {index + 1}"
            for index, parameter in enumerate(parameters)
        ]

        self.x_axis_selector.clear()
        self.y_axis_selector.clear()
        if not display_parameters:
            self.x_axis_selector.addItem("Select x variable")
            self.y_axis_selector.addItem("Select y variable")
            self.x_axis_selector.setEnabled(False)
            self.y_axis_selector.setEnabled(False)
            return

        self.x_axis_selector.addItems(display_parameters)
        self.y_axis_selector.addItems(display_parameters)
        self.x_axis_selector.setEnabled(True)
        self.y_axis_selector.setEnabled(True)

    def _refresh_parameter_warning(self, row: int) -> None:
        parameter_item = self.header_preview_table.item(row, 1)
        parameter = parameter_item.text().strip() if parameter_item is not None else ""
        warning_text = self._parameter_warning_text(parameter)

        warning_item = self.header_preview_table.item(row, 0)
        if warning_item is None:
            warning_item = QTableWidgetItem()
            warning_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.header_preview_table.setItem(row, 0, warning_item)

        if warning_text:
            warning_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
            warning_item.setIcon(warning_icon)
            warning_item.setToolTip(warning_text)
        else:
            warning_item.setIcon(QIcon())
            warning_item.setToolTip("")

    def _parameter_warning_text(self, parameter: str) -> str:
        if not parameter:
            return "Parameter name is empty."
        try:
            float(parameter)
        except ValueError:
            return ""
        return "Parameter name is numeric."

    def _update_summary(self) -> None:
        total = len(self._files)
        selected = len(self.selected_files())
        self.scan_summary_label.setText(f"{total} files found, {selected} selected")
        self.selection_changed.emit(total, selected)

    def _read_only_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        return item

    def _format_size(self, size_bytes: int) -> str:
        value = float(size_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{size_bytes} B"
