"""Plot and dataset controls scaffold."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
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

from simpost.backend.label_formula import DEFAULT_CURVE_LABEL_FORMULA, format_curve_label
from simpost.ui.plot_models import (
    AxisRangeState,
    CurveState,
    CurveStyle,
    GridStyle,
    LegendStyle,
    PlotStyleState,
)


class ControlsPanel(QWidget):
    browse_requested = pyqtSignal()
    scan_requested = pyqtSignal()
    add_curve_requested = pyqtSignal()
    add_selected_files_curves_requested = pyqtSignal()
    apply_uniform_style_requested = pyqtSignal()
    batch_export_requested = pyqtSignal()
    curve_highlighted = pyqtSignal(str)
    curve_selected = pyqtSignal(str)
    curve_label_changed = pyqtSignal(str, str)
    curve_delete_requested = pyqtSignal(str)
    curve_style_changed = pyqtSignal(str, object)
    plot_style_changed = pyqtSignal(object)
    reset_all_styles_requested = pyqtSignal()
    selection_changed = pyqtSignal(int, int)
    file_highlighted = pyqtSignal(dict)
    header_config_changed = pyqtSignal()
    curve_label_formula_changed = pyqtSignal(str)
    settings_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        self._directory_path = ""
        self._files: list[dict] = []
        self._current_file: dict | None = None
        self._current_header_config: tuple[int, int | None, int | None] | None = None
        self._current_header_info: dict | None = None
        self._current_raw_parameters: list[str] = []
        self._current_raw_units: list[str] = []
        self._current_raw_labels: list[str] = []
        self._header_overrides: dict[str, dict] = {}
        self._updating_table = False
        self._updating_select_all = False
        self._updating_header = False
        self._updating_curve_table = False
        self._updating_curve_selector = False
        self._updating_style_controls = False
        self._updating_plot_style_controls = False
        self._selected_curve_id: str | None = None
        self._grid_color = "#b0b0b0"
        self._legend_background_color = "#ffffff"
        self._legend_border_color = "#808080"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        layout.addWidget(self._build_data_group())
        layout.addWidget(self._build_file_list_group(), stretch=1)
        layout.addWidget(self._build_header_group(), stretch=1)
        layout.addWidget(self._build_plot_group())
        layout.addWidget(self._build_curve_list_group(), stretch=1)
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
        self.extensions_input.textChanged.connect(lambda _text: self.settings_changed.emit())

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

        self.select_all_files_checkbox = QCheckBox("Select all files")
        self.select_all_files_checkbox.setTristate(True)
        self.select_all_files_checkbox.stateChanged.connect(self._handle_select_all_files_changed)
        layout.addWidget(self.select_all_files_checkbox)

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
        self.name_row_spin.valueChanged.connect(lambda _value: self._emit_header_config_changed())

        self.unit_row_checkbox = QCheckBox("Use units row")
        self.unit_row_checkbox.setChecked(True)
        self.unit_row_checkbox.stateChanged.connect(self._handle_unit_row_enabled_changed)

        self.unit_row_spin = QSpinBox()
        self.unit_row_spin.setRange(1, 999_999)
        self.unit_row_spin.setValue(2)
        self.unit_row_spin.valueChanged.connect(lambda _value: self._emit_header_config_changed())

        self.label_row_checkbox = QCheckBox("Use curve label row")
        self.label_row_checkbox.setChecked(False)
        self.label_row_checkbox.stateChanged.connect(self._handle_label_row_enabled_changed)

        self.label_row_spin = QSpinBox()
        self.label_row_spin.setRange(1, 999_999)
        self.label_row_spin.setValue(3)
        self.label_row_spin.setEnabled(False)
        self.label_row_spin.valueChanged.connect(lambda _value: self._emit_header_config_changed())

        self.curve_label_formula_input = QLineEdit(DEFAULT_CURVE_LABEL_FORMULA)
        self.curve_label_formula_input.setToolTip(
            "Supported variables: curve_label, parameter, file_name"
        )
        self.curve_label_formula_input.textChanged.connect(self._handle_label_formula_changed)

        row_form = QFormLayout()
        row_form.addRow("Parameter row", self.name_row_spin)
        row_form.addRow(self.unit_row_checkbox, self.unit_row_spin)
        row_form.addRow(self.label_row_checkbox, self.label_row_spin)
        row_form.addRow("Curve label formula", self.curve_label_formula_input)

        self.header_summary_label = QLabel("Select a file to preview headers")

        self.header_preview_table = QTableWidget(0, 4)
        self.header_preview_table.setHorizontalHeaderLabels(["", "Parameter", "Unit", "Curve label"])
        self.header_preview_table.verticalHeader().setVisible(False)
        self.header_preview_table.setAlternatingRowColors(True)
        self.header_preview_table.itemChanged.connect(self._handle_header_item_changed)

        header = self.header_preview_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        layout.addLayout(row_form)
        layout.addWidget(self.header_summary_label)
        layout.addWidget(self.header_preview_table)
        return group

    def _build_plot_group(self) -> QGroupBox:
        group = QGroupBox("Plot Configuration")
        layout = QVBoxLayout(group)

        self.x_axis_selector = QComboBox()
        self.x_axis_selector.addItem("Select x variable")
        self.x_axis_selector.setEnabled(False)

        self.y_axis_selector = QComboBox()
        self.y_axis_selector.addItem("Select y variable")
        self.y_axis_selector.setEnabled(False)

        self.add_y_variable_button = QPushButton("+ Add Y variable")
        self.add_y_variable_button.setEnabled(False)
        self.add_y_variable_button.clicked.connect(self._add_selected_y_variable)

        self.selected_y_table = QTableWidget(0, 2)
        self.selected_y_table.setHorizontalHeaderLabels(["Y variables", ""])
        self.selected_y_table.verticalHeader().setVisible(False)
        self.selected_y_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.selected_y_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.selected_y_table.setMaximumHeight(92)
        y_header = self.selected_y_table.horizontalHeader()
        y_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        y_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        self.add_curve_button = QPushButton("Add curve(s)")
        self.add_curve_button.setEnabled(False)
        self.add_curve_button.clicked.connect(self.add_curve_requested.emit)

        self.add_selected_files_button = QPushButton("Add curves for all selected files")
        self.add_selected_files_button.setEnabled(False)
        self.add_selected_files_button.clicked.connect(self.add_selected_files_curves_requested.emit)

        form = QFormLayout()
        form.addRow("X", self.x_axis_selector)
        form.addRow("Y", self.y_axis_selector)
        form.addRow("", self.add_y_variable_button)
        layout.addLayout(form)
        layout.addWidget(self.selected_y_table)
        layout.addWidget(self.add_curve_button)
        layout.addWidget(self.add_selected_files_button)
        return group

    def _build_curve_list_group(self) -> QGroupBox:
        group = QGroupBox("Curves")
        layout = QVBoxLayout(group)

        self.curve_table = QTableWidget(0, 5)
        self.curve_table.setHorizontalHeaderLabels(["Label", "Source", "X", "Y", ""])
        self.curve_table.verticalHeader().setVisible(False)
        self.curve_table.setAlternatingRowColors(True)
        self.curve_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.curve_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.curve_table.itemChanged.connect(self._handle_curve_label_changed)
        self.curve_table.itemSelectionChanged.connect(self._handle_curve_selection_changed)

        header = self.curve_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.curve_table)
        return group

    def _build_style_group(self) -> QGroupBox:
        group = QGroupBox("Style")
        layout = QVBoxLayout(group)

        layout.addWidget(self._build_axis_range_group())
        layout.addWidget(self._build_curve_style_group())
        layout.addWidget(self._build_global_style_group())
        return group

    def _build_axis_range_group(self) -> QGroupBox:
        group = QGroupBox("Axis Ranges")
        form = QFormLayout(group)

        self.x_auto_checkbox = QCheckBox("Auto")
        self.x_auto_checkbox.setChecked(True)
        self.x_auto_checkbox.stateChanged.connect(lambda _state: self._handle_range_auto_changed())

        self.x_min_spin = self._range_spin_box()
        self.x_max_spin = self._range_spin_box(default=1.0)
        self.x_min_spin.valueChanged.connect(lambda _value: self._emit_plot_style_changed())
        self.x_max_spin.valueChanged.connect(lambda _value: self._emit_plot_style_changed())

        self.y_auto_checkbox = QCheckBox("Auto")
        self.y_auto_checkbox.setChecked(True)
        self.y_auto_checkbox.stateChanged.connect(lambda _state: self._handle_range_auto_changed())

        self.y_min_spin = self._range_spin_box()
        self.y_max_spin = self._range_spin_box(default=1.0)
        self.y_min_spin.valueChanged.connect(lambda _value: self._emit_plot_style_changed())
        self.y_max_spin.valueChanged.connect(lambda _value: self._emit_plot_style_changed())

        form.addRow("X range", self.x_auto_checkbox)
        form.addRow("X min", self.x_min_spin)
        form.addRow("X max", self.x_max_spin)
        form.addRow("Y range", self.y_auto_checkbox)
        form.addRow("Y min", self.y_min_spin)
        form.addRow("Y max", self.y_max_spin)
        self._handle_range_auto_changed(emit=False)
        return group

    def _build_curve_style_group(self) -> QGroupBox:
        group = QGroupBox("Selected Curve")
        form = QFormLayout(group)

        self.curve_label_input = QComboBox()
        self.curve_label_input.setEditable(True)
        self.curve_label_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.curve_label_input.setEnabled(False)
        self.curve_label_input.currentIndexChanged.connect(self._handle_curve_selector_changed)
        self.curve_label_input.highlighted.connect(self._handle_curve_selector_highlighted)
        self.curve_label_input.lineEdit().editingFinished.connect(
            self._handle_curve_label_input_changed
        )

        self.curve_color_button = QPushButton("Color")
        self.curve_color_button.setEnabled(False)
        self.curve_color_button.clicked.connect(self._choose_curve_color)

        self.curve_line_style_selector = QComboBox()
        self.curve_line_style_selector.addItem("Solid", "solid")
        self.curve_line_style_selector.addItem("Dashed", "dashed")
        self.curve_line_style_selector.addItem("Dotted", "dotted")
        self.curve_line_style_selector.addItem("Dash-dot", "dashdot")
        self.curve_line_style_selector.setEnabled(False)
        self.curve_line_style_selector.currentIndexChanged.connect(
            lambda _index: self._emit_curve_style_changed()
        )

        self.curve_line_weight_spin = QDoubleSpinBox()
        self.curve_line_weight_spin.setRange(0.5, 5.0)
        self.curve_line_weight_spin.setSingleStep(0.5)
        self.curve_line_weight_spin.setDecimals(1)
        self.curve_line_weight_spin.setSuffix(" px")
        self.curve_line_weight_spin.setEnabled(False)
        self.curve_line_weight_spin.valueChanged.connect(
            lambda _value: self._emit_curve_style_changed()
        )

        self.curve_marker_selector = QComboBox()
        self.curve_marker_selector.addItem("None", "none")
        self.curve_marker_selector.addItem("Circle", "circle")
        self.curve_marker_selector.addItem("Square", "square")
        self.curve_marker_selector.addItem("Triangle", "triangle")
        self.curve_marker_selector.addItem("Cross", "cross")
        self.curve_marker_selector.setEnabled(False)
        self.curve_marker_selector.currentIndexChanged.connect(
            lambda _index: self._emit_curve_style_changed()
        )

        self.curve_marker_size_spin = QDoubleSpinBox()
        self.curve_marker_size_spin.setRange(1.0, 20.0)
        self.curve_marker_size_spin.setSingleStep(0.5)
        self.curve_marker_size_spin.setDecimals(1)
        self.curve_marker_size_spin.setEnabled(False)
        self.curve_marker_size_spin.valueChanged.connect(
            lambda _value: self._emit_curve_style_changed()
        )

        self.curve_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.curve_opacity_slider.setRange(0, 100)
        self.curve_opacity_slider.setEnabled(False)
        self.curve_opacity_slider.valueChanged.connect(
            lambda _value: self._emit_curve_style_changed()
        )

        form.addRow("Label", self.curve_label_input)
        form.addRow("Color", self.curve_color_button)
        form.addRow("Line style", self.curve_line_style_selector)
        form.addRow("Line weight", self.curve_line_weight_spin)
        form.addRow("Marker", self.curve_marker_selector)
        form.addRow("Marker size", self.curve_marker_size_spin)
        form.addRow("Opacity", self.curve_opacity_slider)
        return group

    def _build_global_style_group(self) -> QGroupBox:
        group = QGroupBox("Global")
        form = QFormLayout(group)

        self.plot_title_input = QLineEdit()
        self.plot_title_input.setPlaceholderText("Auto/blank")
        self.plot_title_input.textChanged.connect(lambda _text: self._emit_plot_style_changed())

        self.x_axis_title_input = QLineEdit()
        self.x_axis_title_input.setPlaceholderText("Auto from selected X parameter")
        self.x_axis_title_input.textChanged.connect(lambda _text: self._emit_plot_style_changed())

        self.y_axis_title_input = QLineEdit()
        self.y_axis_title_input.setPlaceholderText("Auto from selected Y parameter")
        self.y_axis_title_input.textChanged.connect(lambda _text: self._emit_plot_style_changed())

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 32)
        self.font_size_spin.setValue(10)
        self.font_size_spin.valueChanged.connect(lambda _value: self._emit_plot_style_changed())

        self.grid_checkbox = QCheckBox("Show grid")
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.stateChanged.connect(lambda _state: self._emit_plot_style_changed())

        self.grid_color_button = QPushButton("Grid color")
        self._set_color_button(self.grid_color_button, self._grid_color)
        self.grid_color_button.clicked.connect(self._choose_grid_color)

        self.grid_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.grid_opacity_slider.setRange(0, 100)
        self.grid_opacity_slider.setValue(30)
        self.grid_opacity_slider.valueChanged.connect(lambda _value: self._emit_plot_style_changed())

        self.legend_checkbox = QCheckBox("Show legend")
        self.legend_checkbox.setChecked(True)
        self.legend_checkbox.stateChanged.connect(lambda _state: self._emit_plot_style_changed())

        self.legend_location_selector = QComboBox()
        for text, value in (
            ("Best", "best"),
            ("Upper right", "upper right"),
            ("Upper left", "upper left"),
            ("Lower left", "lower left"),
            ("Lower right", "lower right"),
            ("Right", "right"),
            ("Center left", "center left"),
            ("Center right", "center right"),
            ("Lower center", "lower center"),
            ("Upper center", "upper center"),
            ("Center", "center"),
            ("Outside right", "outside right"),
            ("Outside left", "outside left"),
            ("Outside top", "outside top"),
            ("Outside bottom", "outside bottom"),
        ):
            self.legend_location_selector.addItem(text, value)
        self.legend_location_selector.currentIndexChanged.connect(
            lambda _index: self._emit_plot_style_changed()
        )

        self.legend_frame_checkbox = QCheckBox("Frame")
        self.legend_frame_checkbox.setChecked(True)
        self.legend_frame_checkbox.stateChanged.connect(
            lambda _state: self._emit_plot_style_changed()
        )

        self.legend_background_button = QPushButton("Legend background")
        self._set_color_button(self.legend_background_button, self._legend_background_color)
        self.legend_background_button.clicked.connect(self._choose_legend_background_color)

        self.legend_border_button = QPushButton("Legend border")
        self._set_color_button(self.legend_border_button, self._legend_border_color)
        self.legend_border_button.clicked.connect(self._choose_legend_border_color)

        self.legend_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.legend_opacity_slider.setRange(0, 100)
        self.legend_opacity_slider.setValue(80)
        self.legend_opacity_slider.valueChanged.connect(
            lambda _value: self._emit_plot_style_changed()
        )

        self.reset_styles_button = QPushButton("Reset all styles")
        self.reset_styles_button.clicked.connect(self.reset_all_styles_requested.emit)

        self.apply_uniform_style_button = QPushButton("Apply uniform style to all curves")
        self.apply_uniform_style_button.clicked.connect(self.apply_uniform_style_requested.emit)

        self.batch_export_button = QPushButton("Batch Export")
        self.batch_export_button.clicked.connect(self.batch_export_requested.emit)

        form.addRow("Plot title", self.plot_title_input)
        form.addRow("X title", self.x_axis_title_input)
        form.addRow("Y title", self.y_axis_title_input)
        form.addRow("Font size", self.font_size_spin)
        form.addRow("Grid", self.grid_checkbox)
        form.addRow("Grid color", self.grid_color_button)
        form.addRow("Grid opacity", self.grid_opacity_slider)
        form.addRow("Legend", self.legend_checkbox)
        form.addRow("Legend location", self.legend_location_selector)
        form.addRow("Legend frame", self.legend_frame_checkbox)
        form.addRow("Legend background", self.legend_background_button)
        form.addRow("Legend border", self.legend_border_button)
        form.addRow("Legend opacity", self.legend_opacity_slider)
        form.addRow("", self.reset_styles_button)
        form.addRow("", self.apply_uniform_style_button)
        form.addRow("", self.batch_export_button)
        return group

    def directory_path(self) -> str:
        return self._directory_path

    def set_directory_path(self, directory_path: str) -> None:
        self._directory_path = directory_path
        self.directory_label.setText(directory_path or "No directory selected")
        self.settings_changed.emit()

    def extensions_text(self) -> str:
        return self.extensions_input.text().strip()

    def set_extensions_text(self, extensions_text: str) -> None:
        self.extensions_input.setText(extensions_text)

    def extensions(self) -> list[str]:
        return [
            extension.strip()
            for extension in self.extensions_input.text().split(",")
            if extension.strip()
        ]

    def header_settings(self) -> dict:
        return {
            "name_row": self.name_row_spin.value(),
            "use_unit_row": self.unit_row_checkbox.isChecked(),
            "unit_row": self.unit_row_spin.value(),
            "use_label_row": self.label_row_checkbox.isChecked(),
            "label_row": self.label_row_spin.value(),
            "curve_label_formula": self.curve_label_formula_input.text().strip(),
        }

    def set_header_settings(self, settings: dict) -> None:
        def row_value(key: str, default: int) -> int:
            try:
                return max(1, int(settings.get(key, default)))
            except (TypeError, ValueError):
                return default

        def bool_value(key: str, default: bool) -> bool:
            value = settings.get(key, default)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)

        widgets = (
            self.name_row_spin,
            self.unit_row_checkbox,
            self.unit_row_spin,
            self.label_row_checkbox,
            self.label_row_spin,
            self.curve_label_formula_input,
        )
        previous_blocks = [widget.blockSignals(True) for widget in widgets]
        try:
            self.name_row_spin.setValue(row_value("name_row", 1))
            self.unit_row_checkbox.setChecked(bool_value("use_unit_row", True))
            self.unit_row_spin.setValue(row_value("unit_row", 2))
            self.unit_row_spin.setEnabled(self.unit_row_checkbox.isChecked())
            self.label_row_checkbox.setChecked(bool_value("use_label_row", False))
            self.label_row_spin.setValue(row_value("label_row", 3))
            self.label_row_spin.setEnabled(self.label_row_checkbox.isChecked())
            self.curve_label_formula_input.setText(
                str(settings.get("curve_label_formula") or DEFAULT_CURVE_LABEL_FORMULA)
            )
        finally:
            for widget, blocked in zip(widgets, previous_blocks):
                widget.blockSignals(blocked)
        self.settings_changed.emit()

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
        self._sync_select_all_checkbox()
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

    def header_config(self) -> tuple[int, int | None, int | None]:
        name_row = self.name_row_spin.value() - 1
        unit_row = self.unit_row_spin.value() - 1 if self.unit_row_checkbox.isChecked() else None
        label_row = self.label_row_spin.value() - 1 if self.label_row_checkbox.isChecked() else None
        return name_row, unit_row, label_row

    def set_header_preview(self, file_info: dict, header_info: dict) -> None:
        self._current_file = file_info
        self._current_header_config = self.header_config()
        self._current_header_info = header_info

        path = str(file_info["path"])
        raw_parameters = list(header_info["parameters"])
        raw_units = list(header_info["units"])
        raw_labels = list(header_info.get("plot_labels", []))
        parameters = list(raw_parameters)
        units = list(raw_units)
        labels = list(raw_labels)
        override = self._header_overrides.get(path)
        if (
            override
            and override.get("config") == self._current_header_config
            and len(override.get("parameters", [])) == len(parameters)
        ):
            parameters = list(override["parameters"])
            units = list(override["units"])
            labels = list(override.get("labels", labels))

        self._current_raw_parameters = raw_parameters
        self._current_raw_units = raw_units
        self._current_raw_labels = raw_labels

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

            label_item = QTableWidgetItem(labels[row] if row < len(labels) else "")
            label_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEditable
            )
            self.header_preview_table.setItem(row, 3, label_item)
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
        self._populate_axis_selectors(parameters, units, labels)

    def clear_header_preview(self) -> None:
        self._current_file = None
        self._current_header_config = None
        self._current_header_info = None
        self._current_raw_parameters = []
        self._current_raw_units = []
        self._current_raw_labels = []
        self.header_summary_label.setText("Select a file to preview headers")
        self.header_preview_table.setRowCount(0)
        self._populate_axis_selectors([], [], [])

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
        self._sync_select_all_checkbox()
        self._update_summary()

    def _handle_select_all_files_changed(self, state: int) -> None:
        if self._updating_select_all or self._updating_table:
            return
        if state == Qt.CheckState.PartiallyChecked.value:
            return

        self._updating_table = True
        check_state = (
            Qt.CheckState.Checked
            if state == Qt.CheckState.Checked.value
            else Qt.CheckState.Unchecked
        )
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item is not None:
                item.setCheckState(check_state)
        self._updating_table = False
        self._sync_select_all_checkbox()
        self._update_summary()

    def _sync_select_all_checkbox(self) -> None:
        total = self.file_table.rowCount()
        selected = len(self.selected_files())
        self._updating_select_all = True
        if total == 0 or selected == 0:
            self.select_all_files_checkbox.setCheckState(Qt.CheckState.Unchecked)
        elif selected == total:
            self.select_all_files_checkbox.setCheckState(Qt.CheckState.Checked)
        else:
            self.select_all_files_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
        self._updating_select_all = False

    def _handle_unit_row_enabled_changed(self, _state: int) -> None:
        self.unit_row_spin.setEnabled(self.unit_row_checkbox.isChecked())
        self._emit_header_config_changed()

    def _handle_label_row_enabled_changed(self, _state: int) -> None:
        self.label_row_spin.setEnabled(self.label_row_checkbox.isChecked())
        self._emit_header_config_changed()

    def _emit_header_config_changed(self) -> None:
        self.header_config_changed.emit()
        self.settings_changed.emit()

    def _handle_label_formula_changed(self, _text: str) -> None:
        self.settings_changed.emit()
        self.curve_label_formula_changed.emit(self.curve_label_formula_input.text().strip())
        if self._current_header_info is None:
            return
        self._populate_axis_selectors(
            self._current_parameters(),
            self._current_units(),
            self._current_labels(),
        )

    def _handle_header_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_header or item.column() not in (1, 2, 3):
            return
        if item.column() == 1:
            self._refresh_parameter_warning(item.row())
        self._store_current_header_overrides()
        self._populate_axis_selectors(
            self._current_parameters(),
            self._current_units(),
            self._current_labels(),
        )

    def _store_current_header_overrides(self) -> None:
        if self._current_file is None or self._current_header_config is None:
            return

        self._header_overrides[str(self._current_file["path"])] = {
            "config": self._current_header_config,
            "parameters": self._current_parameters(),
            "units": self._current_units(),
            "labels": self._current_labels(),
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

    def _current_labels(self) -> list[str]:
        labels: list[str] = []
        for row in range(self.header_preview_table.rowCount()):
            item = self.header_preview_table.item(row, 3)
            labels.append(item.text().strip() if item is not None else "")
        return labels

    def plot_selection(self) -> dict | None:
        if self._current_file is None or self._current_header_config is None:
            return None
        if self._current_header_info is None:
            return None

        x_data = self.x_axis_selector.currentData(Qt.ItemDataRole.UserRole)
        y_data = self.y_axis_selector.currentData(Qt.ItemDataRole.UserRole)
        if not isinstance(x_data, dict) or not isinstance(y_data, dict):
            return None

        name_row, unit_row, label_row = self._current_header_config
        return {
            "filepath": str(self._current_file["path"]),
            "filename": str(self._current_file["filename"]),
            "x_param": x_data["raw_parameter"],
            "y_param": y_data["raw_parameter"],
            "x_column_index": x_data["column_index"],
            "y_column_index": y_data["column_index"],
            "x_display": x_data["display_parameter"],
            "y_display": y_data["display_parameter"],
            "x_label": x_data["axis_label"],
            "y_label": y_data["axis_label"],
            "curve_label": y_data["curve_label"],
            "curve_label_formula": self.curve_label_formula_input.text().strip(),
            "name_row": name_row,
            "unit_row": unit_row,
            "label_row": label_row,
            "data_start_row": int(self._current_header_info["data_start_row"]),
        }

    def _populate_axis_selectors(
        self,
        parameters: list[str],
        units: list[str],
        labels: list[str],
    ) -> None:
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
            self.add_y_variable_button.setEnabled(False)
            self.add_curve_button.setEnabled(False)
            self.add_selected_files_button.setEnabled(False)
            self._clear_selected_y_variables()
            return

        self._clear_selected_y_variables()
        for index, display_parameter in enumerate(display_parameters):
            unit = units[index].strip() if index < len(units) else ""
            raw_parameter = (
                self._current_raw_parameters[index]
                if index < len(self._current_raw_parameters)
                else display_parameter
            )
            axis_data = {
                "raw_parameter": raw_parameter,
                "column_index": index,
                "display_parameter": display_parameter,
                "display_unit": unit,
                "axis_label": self._format_axis_label(display_parameter, unit),
                "curve_label": self._format_curve_label(
                    labels[index].strip() if index < len(labels) else "",
                    display_parameter,
                    display_parameter,
                ),
            }
            self.x_axis_selector.addItem(display_parameter, axis_data)
            self.y_axis_selector.addItem(display_parameter, axis_data)

        self.x_axis_selector.setEnabled(True)
        self.y_axis_selector.setEnabled(True)
        self.add_y_variable_button.setEnabled(True)
        self.add_curve_button.setEnabled(True)
        self.add_selected_files_button.setEnabled(True)

    def plot_selections_for_current_file(self) -> list[dict]:
        y_items = self._selected_y_axis_data()
        if not y_items:
            current_y = self.y_axis_selector.currentData(Qt.ItemDataRole.UserRole)
            y_items = [current_y] if isinstance(current_y, dict) else []

        selections: list[dict] = []
        for y_data in y_items:
            selection = self._plot_selection_for_y_data(y_data)
            if selection is not None:
                selections.append(selection)
        return selections

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

    def _format_axis_label(self, parameter: str, unit: str) -> str:
        parameter = parameter.strip()
        unit = unit.strip()
        return f"{parameter} ({unit})" if unit else parameter

    def _format_curve_label(self, curve_label: str, parameter: str, fallback: str) -> str:
        file_name = ""
        if self._current_file is not None:
            file_name = str(self._current_file["filename"])
        return format_curve_label(
            self.curve_label_formula_input.text(),
            curve_label=curve_label,
            parameter=parameter,
            fallback=fallback,
            file_name=file_name,
        )

    def _add_selected_y_variable(self) -> None:
        y_data = self.y_axis_selector.currentData(Qt.ItemDataRole.UserRole)
        if not isinstance(y_data, dict):
            return

        raw_parameter = str(y_data["raw_parameter"])
        existing = {
            self.selected_y_table.item(row, 0).data(Qt.ItemDataRole.UserRole)["raw_parameter"]
            for row in range(self.selected_y_table.rowCount())
            if self.selected_y_table.item(row, 0) is not None
        }
        if raw_parameter in existing:
            return

        row = self.selected_y_table.rowCount()
        self.selected_y_table.insertRow(row)
        item = self._read_only_item(str(y_data["display_parameter"]))
        item.setData(Qt.ItemDataRole.UserRole, y_data)
        self.selected_y_table.setItem(row, 0, item)

        delete_button = QPushButton("\u00d7")
        delete_button.setFixedWidth(28)
        delete_button.clicked.connect(lambda _checked=False, target_row=row: self._remove_y_row(target_row))
        self.selected_y_table.setCellWidget(row, 1, delete_button)

    def _remove_y_row(self, row: int) -> None:
        if 0 <= row < self.selected_y_table.rowCount():
            self.selected_y_table.removeRow(row)
            self._rebind_y_delete_buttons()

    def _clear_selected_y_variables(self) -> None:
        self.selected_y_table.setRowCount(0)

    def _rebind_y_delete_buttons(self) -> None:
        for row in range(self.selected_y_table.rowCount()):
            delete_button = QPushButton("\u00d7")
            delete_button.setFixedWidth(28)
            delete_button.clicked.connect(
                lambda _checked=False, target_row=row: self._remove_y_row(target_row)
            )
            self.selected_y_table.setCellWidget(row, 1, delete_button)

    def _selected_y_axis_data(self) -> list[dict]:
        y_items: list[dict] = []
        for row in range(self.selected_y_table.rowCount()):
            item = self.selected_y_table.item(row, 0)
            if item is None:
                continue
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                y_items.append(data)
        return y_items

    def _plot_selection_for_y_data(self, y_data: dict) -> dict | None:
        if self._current_file is None or self._current_header_config is None:
            return None
        if self._current_header_info is None:
            return None

        x_data = self.x_axis_selector.currentData(Qt.ItemDataRole.UserRole)
        if not isinstance(x_data, dict):
            return None

        name_row, unit_row, label_row = self._current_header_config
        return {
            "filepath": str(self._current_file["path"]),
            "filename": str(self._current_file["filename"]),
            "x_param": x_data["raw_parameter"],
            "y_param": y_data["raw_parameter"],
            "x_column_index": x_data["column_index"],
            "y_column_index": y_data["column_index"],
            "x_display": x_data["display_parameter"],
            "y_display": y_data["display_parameter"],
            "x_label": x_data["axis_label"],
            "y_label": y_data["axis_label"],
            "curve_label": y_data["curve_label"],
            "curve_label_formula": self.curve_label_formula_input.text().strip(),
            "name_row": name_row,
            "unit_row": unit_row,
            "label_row": label_row,
            "data_start_row": int(self._current_header_info["data_start_row"]),
        }

    def set_curves(self, curves: list[CurveState], selected_curve_id: str | None = None) -> None:
        self._updating_curve_table = True
        self._updating_curve_selector = True
        self.curve_table.setRowCount(len(curves))
        self.curve_label_input.clear()
        selected_row = -1
        selected_combo_index = -1

        for row, curve in enumerate(curves):
            if curve.id == selected_curve_id:
                selected_row = row
                selected_combo_index = row

            self.curve_label_input.addItem(curve.label, curve.id)

            label_item = QTableWidgetItem(curve.label)
            label_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEditable
            )
            label_item.setData(Qt.ItemDataRole.UserRole, curve.id)
            self.curve_table.setItem(row, 0, label_item)

            source_item = self._read_only_item(self._truncate_source(curve.source_file))
            source_item.setToolTip(curve.source_path)
            self.curve_table.setItem(row, 1, source_item)
            self.curve_table.setItem(row, 2, self._read_only_item(curve.x_param))
            self.curve_table.setItem(row, 3, self._read_only_item(curve.y_param))

            delete_button = QPushButton("\u00d7")
            delete_button.setFixedWidth(28)
            curve_id = curve.id
            delete_button.clicked.connect(
                lambda _checked=False, target_id=curve_id: self.curve_delete_requested.emit(target_id)
            )
            self.curve_table.setCellWidget(row, 4, delete_button)

        if selected_row >= 0:
            self.curve_table.selectRow(selected_row)
        else:
            self.curve_table.clearSelection()
        self.curve_label_input.setCurrentIndex(selected_combo_index)

        self._updating_curve_selector = False
        self._updating_curve_table = False

    def _handle_curve_label_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_curve_table or item.column() != 0:
            return
        curve_id = item.data(Qt.ItemDataRole.UserRole)
        if curve_id is None:
            return
        self.curve_label_changed.emit(str(curve_id), item.text().strip())

    def _handle_curve_selection_changed(self) -> None:
        if self._updating_curve_table:
            return

        selected_rows = self.curve_table.selectionModel().selectedRows()
        if not selected_rows:
            self._selected_curve_id = None
            self.set_selected_curve(None)
            return

        item = self.curve_table.item(selected_rows[0].row(), 0)
        if item is None:
            return
        curve_id = str(item.data(Qt.ItemDataRole.UserRole))
        self._selected_curve_id = curve_id
        self.curve_selected.emit(curve_id)

    def _truncate_source(self, source: str, max_length: int = 24) -> str:
        if len(source) <= max_length:
            return source
        return f"...{source[-(max_length - 3):]}"

    def set_selected_curve(self, curve: CurveState | None, sync_selector: bool = True) -> None:
        self._updating_style_controls = True
        self._selected_curve_id = curve.id if curve is not None else None
        enabled = curve is not None

        for widget in (
            self.curve_label_input,
            self.curve_color_button,
            self.curve_line_style_selector,
            self.curve_line_weight_spin,
            self.curve_marker_selector,
            self.curve_marker_size_spin,
            self.curve_opacity_slider,
        ):
            widget.setEnabled(enabled)

        if curve is None:
            if sync_selector:
                self._sync_curve_selector(None)
            self.curve_label_input.setEditText("")
            self._set_color_button(self.curve_color_button, "#808080")
        else:
            if sync_selector:
                self._sync_curve_selector(curve.id)
            self.curve_label_input.setEditText(curve.label)
            if sync_selector:
                self._sync_curve_table_selection(curve.id)
            self._set_color_button(self.curve_color_button, curve.style.color)
            self._set_combo_to_data(self.curve_line_style_selector, curve.style.line_style)
            self.curve_line_weight_spin.setValue(curve.style.line_weight)
            self._set_combo_to_data(self.curve_marker_selector, curve.style.marker_style)
            self.curve_marker_size_spin.setValue(curve.style.marker_size)
            self.curve_opacity_slider.setValue(round(curve.style.opacity * 100))

        self._updating_style_controls = False

    def _sync_curve_selector(self, curve_id: str | None) -> None:
        if self._updating_curve_selector:
            return

        self._updating_curve_selector = True
        if curve_id is None:
            self.curve_label_input.setCurrentIndex(-1)
        else:
            index = self.curve_label_input.findData(curve_id)
            if index >= 0:
                self.curve_label_input.setCurrentIndex(index)
        self._updating_curve_selector = False

    def _sync_curve_table_selection(self, curve_id: str) -> None:
        if self._updating_curve_table:
            return

        self._updating_curve_table = True
        for row in range(self.curve_table.rowCount()):
            item = self.curve_table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == curve_id:
                self.curve_table.selectRow(row)
                break
        self._updating_curve_table = False

    def set_plot_style(self, plot_style: PlotStyleState) -> None:
        self._updating_plot_style_controls = True
        self.plot_title_input.setText(plot_style.plot_title)
        self.x_axis_title_input.setText(plot_style.x_axis_title)
        self.y_axis_title_input.setText(plot_style.y_axis_title)
        self.x_auto_checkbox.setChecked(plot_style.x_range.auto)
        self.x_min_spin.setValue(plot_style.x_range.minimum)
        self.x_max_spin.setValue(plot_style.x_range.maximum)
        self.y_auto_checkbox.setChecked(plot_style.y_range.auto)
        self.y_min_spin.setValue(plot_style.y_range.minimum)
        self.y_max_spin.setValue(plot_style.y_range.maximum)
        self.font_size_spin.setValue(plot_style.font_size)
        if plot_style.grid is not None:
            self.grid_checkbox.setChecked(plot_style.grid.enabled)
            self._grid_color = plot_style.grid.color
            self._set_color_button(self.grid_color_button, self._grid_color)
            self.grid_opacity_slider.setValue(round(plot_style.grid.opacity * 100))
        if plot_style.legend is not None:
            self.legend_checkbox.setChecked(plot_style.legend.visible)
            self._set_combo_to_data(self.legend_location_selector, plot_style.legend.location)
            self.legend_frame_checkbox.setChecked(plot_style.legend.frame_enabled)
            self._legend_background_color = plot_style.legend.background_color
            self._legend_border_color = plot_style.legend.border_color
            self._set_color_button(self.legend_background_button, self._legend_background_color)
            self._set_color_button(self.legend_border_button, self._legend_border_color)
            self.legend_opacity_slider.setValue(round(plot_style.legend.opacity * 100))
        self._handle_range_auto_changed(emit=False)
        self._updating_plot_style_controls = False

    def plot_style(self) -> PlotStyleState:
        return PlotStyleState(
            x_range=AxisRangeState(
                auto=self.x_auto_checkbox.isChecked(),
                minimum=self.x_min_spin.value(),
                maximum=self.x_max_spin.value(),
            ),
            y_range=AxisRangeState(
                auto=self.y_auto_checkbox.isChecked(),
                minimum=self.y_min_spin.value(),
                maximum=self.y_max_spin.value(),
            ),
            plot_title=self.plot_title_input.text().strip(),
            x_axis_title=self.x_axis_title_input.text().strip(),
            y_axis_title=self.y_axis_title_input.text().strip(),
            font_size=self.font_size_spin.value(),
            grid=GridStyle(
                enabled=self.grid_checkbox.isChecked(),
                color=self._grid_color,
                opacity=self.grid_opacity_slider.value() / 100.0,
            ),
            legend=LegendStyle(
                visible=self.legend_checkbox.isChecked(),
                location=self.legend_location_selector.currentData(Qt.ItemDataRole.UserRole)
                or "best",
                frame_enabled=self.legend_frame_checkbox.isChecked(),
                background_color=self._legend_background_color,
                border_color=self._legend_border_color,
                opacity=self.legend_opacity_slider.value() / 100.0,
            ),
        )

    def _range_spin_box(self, default: float = 0.0) -> QDoubleSpinBox:
        spin_box = QDoubleSpinBox()
        spin_box.setRange(-1.0e12, 1.0e12)
        spin_box.setDecimals(6)
        spin_box.setValue(default)
        return spin_box

    def _handle_range_auto_changed(self, emit: bool = True) -> None:
        x_manual = not self.x_auto_checkbox.isChecked()
        y_manual = not self.y_auto_checkbox.isChecked()
        self.x_min_spin.setEnabled(x_manual)
        self.x_max_spin.setEnabled(x_manual)
        self.y_min_spin.setEnabled(y_manual)
        self.y_max_spin.setEnabled(y_manual)
        if emit:
            self._emit_plot_style_changed()

    def _handle_curve_selector_changed(self, index: int) -> None:
        if self._updating_curve_selector or self._updating_style_controls or index < 0:
            return
        curve_id = self.curve_label_input.itemData(index, Qt.ItemDataRole.UserRole)
        if curve_id is not None:
            self._selected_curve_id = str(curve_id)
            self.curve_selected.emit(str(curve_id))

    def _handle_curve_selector_highlighted(self, index: int) -> None:
        if self._updating_curve_selector or self._updating_style_controls or index < 0:
            return
        curve_id = self.curve_label_input.itemData(index, Qt.ItemDataRole.UserRole)
        if curve_id is not None:
            self.curve_highlighted.emit(str(curve_id))

    def _handle_curve_label_input_changed(self) -> None:
        if (
            self._updating_style_controls
            or self._updating_curve_selector
            or self._selected_curve_id is None
        ):
            return
        self.curve_label_changed.emit(
            self._selected_curve_id,
            self.curve_label_input.currentText().strip(),
        )

    def _choose_curve_color(self) -> None:
        if self._selected_curve_id is None:
            return
        color = QColorDialog.getColor(QColor(self._current_curve_style().color), self)
        if not color.isValid():
            return
        self._set_color_button(self.curve_color_button, color.name())
        self._emit_curve_style_changed()

    def _choose_grid_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._grid_color), self)
        if not color.isValid():
            return
        self._grid_color = color.name()
        self._set_color_button(self.grid_color_button, self._grid_color)
        self._emit_plot_style_changed()

    def _choose_legend_background_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._legend_background_color), self)
        if not color.isValid():
            return
        self._legend_background_color = color.name()
        self._set_color_button(self.legend_background_button, self._legend_background_color)
        self._emit_plot_style_changed()

    def _choose_legend_border_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._legend_border_color), self)
        if not color.isValid():
            return
        self._legend_border_color = color.name()
        self._set_color_button(self.legend_border_button, self._legend_border_color)
        self._emit_plot_style_changed()

    def _emit_curve_style_changed(self) -> None:
        if self._updating_style_controls or self._selected_curve_id is None:
            return
        self.curve_style_changed.emit(self._selected_curve_id, self._current_curve_style())

    def _emit_plot_style_changed(self) -> None:
        if self._updating_plot_style_controls:
            return
        self.plot_style_changed.emit(self.plot_style())

    def _current_curve_style(self) -> CurveStyle:
        return CurveStyle(
            color=self.curve_color_button.property("color") or "#808080",
            line_style=self.curve_line_style_selector.currentData(Qt.ItemDataRole.UserRole)
            or "solid",
            line_weight=self.curve_line_weight_spin.value(),
            marker_style=self.curve_marker_selector.currentData(Qt.ItemDataRole.UserRole)
            or "none",
            marker_size=self.curve_marker_size_spin.value(),
            opacity=self.curve_opacity_slider.value() / 100.0,
        )

    def _set_color_button(self, button: QPushButton, color: str) -> None:
        button.setProperty("color", color)
        button.setText(color.upper())
        button.setStyleSheet(f"background-color: {color};")

    def _set_combo_to_data(self, combo_box: QComboBox, value: str) -> None:
        for index in range(combo_box.count()):
            if combo_box.itemData(index, Qt.ItemDataRole.UserRole) == value:
                combo_box.setCurrentIndex(index)
                return

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
