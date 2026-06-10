"""Matplotlib plot canvas scaffold."""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from PyQt6.QtWidgets import QVBoxLayout, QWidget


class PlotPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.figure = Figure(figsize=(8, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.axes = self.figure.add_subplot(111)
        self._lines: list[Line2D] = []
        self._legend_artist_to_line: dict[object, Line2D] = {}
        self._set_empty_state()
        self.canvas.mpl_connect("pick_event", self._handle_pick)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    def _set_empty_state(self) -> None:
        self.axes.set_title("No dataset loaded")
        self.axes.set_xlabel("X")
        self.axes.set_ylabel("Y")
        self.axes.grid(True, alpha=0.3)
        self.canvas.draw_idle()

    def add_curve(self, plot_data: dict, curve_label: str) -> None:
        if not self._lines:
            self.axes.clear()
            self.axes.grid(True, alpha=0.3)

        (line,) = self.axes.plot(plot_data["x"], plot_data["y"], label=curve_label)
        self._lines.append(line)
        self.axes.set_xlabel(plot_data["x_label"])
        self.axes.set_ylabel(plot_data["y_label"])
        self._refresh_legend()
        self.canvas.draw_idle()

    def _refresh_legend(self) -> None:
        self._legend_artist_to_line.clear()
        legend = self.axes.legend()
        if legend is None:
            return

        for legend_line, original_line in zip(legend.get_lines(), self._lines):
            legend_line.set_picker(True)
            legend_line.set_pickradius(6)
            legend_line.set_alpha(1.0 if original_line.get_visible() else 0.25)
            self._legend_artist_to_line[legend_line] = original_line

        for legend_text, original_line in zip(legend.get_texts(), self._lines):
            legend_text.set_picker(True)
            legend_text.set_alpha(1.0 if original_line.get_visible() else 0.25)
            self._legend_artist_to_line[legend_text] = original_line

    def _handle_pick(self, event: object) -> None:
        artist = getattr(event, "artist", None)
        line = self._legend_artist_to_line.get(artist)
        if line is None:
            return

        line.set_visible(not line.get_visible())
        self._refresh_legend()
        self.canvas.draw_idle()
