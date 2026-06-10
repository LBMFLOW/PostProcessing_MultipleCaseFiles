"""Plot and dataset controls scaffold."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
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

    def __init__(self) -> None:
        super().__init__()

        self._directory_path = ""
        self._files: list[dict] = []
        self._updating_table = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        layout.addWidget(self._build_data_group())
        layout.addWidget(self._build_file_list_group(), stretch=1)
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
        self.file_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.file_table.itemChanged.connect(self._handle_file_selection_changed)

        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.file_table)
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
        self._update_summary()

    def selected_files(self) -> list[dict]:
        selected: list[dict] = []
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    def _handle_file_selection_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_table or item.column() != 0:
            return
        self._update_summary()

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
