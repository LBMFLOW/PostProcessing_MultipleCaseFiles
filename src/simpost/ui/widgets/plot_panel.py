"""Matplotlib plot canvas scaffold."""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QVBoxLayout, QWidget


class PlotPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.figure = Figure(figsize=(8, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.axes = self.figure.add_subplot(111)
        self._set_empty_state()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    def _set_empty_state(self) -> None:
        self.axes.set_title("No dataset loaded")
        self.axes.set_xlabel("X")
        self.axes.set_ylabel("Y")
        self.axes.grid(True, alpha=0.3)
