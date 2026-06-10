"""Batch SVG export dialog."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class BatchExportDialog(QDialog):
    start_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Batch Export")
        self.resize(620, 420)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.output_directory_input = QLineEdit()
        self.output_directory_input.setPlaceholderText("Select output directory")
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_output_directory)

        output_row = QHBoxLayout()
        output_row.addWidget(self.output_directory_input, stretch=1)
        output_row.addWidget(browse_button)

        self.filename_pattern_input = QLineEdit("{casename}_{y_param}_vs_{x_param}.svg")
        self.auto_ranges_checkbox = QCheckBox("Use auto axis ranges per file")
        self.auto_ranges_checkbox.setChecked(True)

        form.addRow("Output directory", output_row)
        form.addRow("Filename pattern", self.filename_pattern_input)
        form.addRow("Axis ranges", self.auto_ranges_checkbox)
        layout.addLayout(form)

        self.progress_label = QLabel("0 of 0 complete")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlaceholderText("Export results will appear here.")

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.start_button = QPushButton("Start Export")
        self.start_button.clicked.connect(self.start_requested.emit)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.close_button)

        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.summary_text, stretch=1)
        layout.addLayout(button_row)

    def output_directory(self) -> str:
        return self.output_directory_input.text().strip()

    def filename_pattern(self) -> str:
        return self.filename_pattern_input.text().strip()

    def auto_axis_ranges_per_file(self) -> bool:
        return self.auto_ranges_checkbox.isChecked()

    def prepare_for_export(self, total: int) -> None:
        self.start_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"0 of {total} complete")
        self.summary_text.clear()

    def update_progress(self, completed: int, total: int) -> None:
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(completed)
        self.progress_label.setText(f"{completed} of {total} complete")

    def set_summary(self, results: list[dict]) -> None:
        exported = [result for result in results if result["success"]]
        failed = [result for result in results if not result["success"]]

        lines = [f"Exported {len(exported)} of {len(results)} file(s)."]
        if exported:
            lines.append("")
            lines.append("Exported:")
            lines.extend(f"- {Path(result['output_path']).name}" for result in exported)
        if failed:
            lines.append("")
            lines.append("Failed:")
            lines.extend(
                f"- {Path(result['filepath']).name}: {result['error']}" for result in failed
            )

        self.summary_text.setPlainText("\n".join(lines))
        self.start_button.setEnabled(True)
        self.close_button.setEnabled(True)

    def set_error(self, message: str) -> None:
        self.summary_text.setPlainText(message)
        self.start_button.setEnabled(True)
        self.close_button.setEnabled(True)

    def _browse_output_directory(self) -> None:
        start = self.output_directory() or str(Path.home())
        directory = QFileDialog.getExistingDirectory(self, "Select output directory", start)
        if directory:
            self.output_directory_input.setText(directory)
