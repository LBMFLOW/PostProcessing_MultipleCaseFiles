"""Matplotlib plot canvas scaffold."""

from __future__ import annotations

import textwrap

import matplotlib.patheffects as path_effects
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from simpost.ui.plot_models import CurveState, LegendStyle, PlotStyleState


LINE_STYLE_MAP = {
    "solid": "-",
    "dashed": "--",
    "dotted": ":",
    "dashdot": "-.",
}

MARKER_STYLE_MAP = {
    "none": None,
    "circle": "o",
    "square": "s",
    "triangle": "^",
    "cross": "x",
}

OUTSIDE_LEGEND_LAYOUTS = {
    "outside right": {
        "loc": "center left",
        "bbox_to_anchor": (1.02, 0.5),
        "wrap_width": 42,
        "adjust": {"left": 0.10, "right": 0.76, "bottom": 0.12, "top": 0.90},
    },
    "outside left": {
        "loc": "center right",
        "bbox_to_anchor": (-0.08, 0.5),
        "wrap_width": 42,
        "adjust": {"left": 0.30, "right": 0.96, "bottom": 0.12, "top": 0.90},
    },
    "outside top": {
        "loc": "upper center",
        "bbox_to_anchor": (0.5, 0.98),
        "wrap_width": 72,
        "adjust": {"left": 0.12, "right": 0.96, "bottom": 0.12, "top": 0.76},
    },
    "outside bottom": {
        "loc": "lower center",
        "bbox_to_anchor": (0.5, 0.02),
        "wrap_width": 72,
        "adjust": {"left": 0.12, "right": 0.96, "bottom": 0.28, "top": 0.90},
    },
}


class PlotPanel(QWidget):
    curve_selected = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()

        self.figure = Figure(figsize=(8, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.axes = self.figure.add_subplot(111)
        self._lines: list[Line2D] = []
        self._legend_artist_to_line: dict[object, Line2D] = {}
        self._line_to_curve_id: dict[Line2D, str] = {}
        self._curve_visibility: dict[str, bool] = {}
        self._last_legend_style: LegendStyle | None = None
        self._last_font_size = 10
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

    def render_curves(
        self,
        curves: list[CurveState],
        plot_style: PlotStyleState,
        selected_curve_id: str | None = None,
    ) -> None:
        self.axes.clear()
        self._lines = []
        self._legend_artist_to_line.clear()
        self._line_to_curve_id.clear()

        if not curves:
            self._set_empty_state()
            return

        active_ids = {curve.id for curve in curves}
        self._curve_visibility = {
            curve_id: visible
            for curve_id, visible in self._curve_visibility.items()
            if curve_id in active_ids
        }

        grid = plot_style.grid
        if grid is not None:
            if grid.enabled:
                self.axes.grid(True, color=grid.color, alpha=grid.opacity)
            else:
                self.axes.grid(False)
        first_curve = curves[0]
        x_label = plot_style.x_axis_title.strip() or first_curve.x_label
        y_label = plot_style.y_axis_title.strip() or first_curve.y_label
        self.axes.set_title(plot_style.plot_title.strip(), fontsize=plot_style.font_size + 2)
        self.axes.set_xlabel(x_label, fontsize=plot_style.font_size)
        self.axes.set_ylabel(y_label, fontsize=plot_style.font_size)
        self.axes.tick_params(axis="both", labelsize=plot_style.font_size)

        for curve in curves:
            curve_id = curve.id
            visible = self._curve_visibility.get(curve_id, True)
            selected = curve_id == selected_curve_id
            line_width = curve.style.line_weight + 2.0 if selected else curve.style.line_weight
            (line,) = self.axes.plot(
                curve.x,
                curve.y,
                label=curve.label,
                color=curve.style.color,
                linestyle=LINE_STYLE_MAP.get(curve.style.line_style, "-"),
                linewidth=line_width,
                marker=MARKER_STYLE_MAP.get(curve.style.marker_style),
                markersize=curve.style.marker_size + (2.0 if selected else 0.0),
                alpha=curve.style.opacity,
                visible=visible,
                zorder=20 if selected else 2,
            )
            line.set_picker(True)
            line.set_pickradius(8)
            if selected:
                line.set_path_effects(
                    [
                        path_effects.Stroke(
                            linewidth=line_width + 3.0,
                            foreground="#202020",
                            alpha=0.55,
                        ),
                        path_effects.Normal(),
                    ]
                )
            self._lines.append(line)
            self._line_to_curve_id[line] = curve_id
            self._curve_visibility[curve_id] = visible

        self.axes.relim()
        self.axes.autoscale_view()
        self._apply_axis_ranges(plot_style)
        self._last_legend_style = plot_style.legend
        self._last_font_size = plot_style.font_size
        self._refresh_legend(plot_style.legend, plot_style.font_size)
        self.canvas.draw_idle()

    def _apply_axis_ranges(self, plot_style: PlotStyleState) -> None:
        if not plot_style.x_range.auto and plot_style.x_range.minimum < plot_style.x_range.maximum:
            self.axes.set_xlim(plot_style.x_range.minimum, plot_style.x_range.maximum)
        if not plot_style.y_range.auto and plot_style.y_range.minimum < plot_style.y_range.maximum:
            self.axes.set_ylim(plot_style.y_range.minimum, plot_style.y_range.maximum)

    def axis_ranges(self) -> dict:
        x_min, x_max = self.axes.get_xlim()
        y_min, y_max = self.axes.get_ylim()
        return {
            "x_range": {"auto": False, "minimum": float(x_min), "maximum": float(x_max)},
            "y_range": {"auto": False, "minimum": float(y_min), "maximum": float(y_max)},
        }

    def _refresh_legend(self, legend_style: LegendStyle | None, font_size: int) -> None:
        self._legend_artist_to_line.clear()
        if legend_style is not None and not legend_style.visible:
            self.figure.set_tight_layout(True)
            legend = self.axes.get_legend()
            if legend is not None:
                legend.remove()
            return

        location = legend_style.location if legend_style is not None else "best"
        frame_enabled = legend_style.frame_enabled if legend_style is not None else True
        legend_labels = self._legend_labels(location)
        legend_kwargs = self._legend_kwargs(location, frame_enabled, font_size, legend_labels)
        try:
            legend = self.axes.legend(handles=self._lines, labels=legend_labels, **legend_kwargs)
        except ValueError:
            legend = self.axes.legend(
                handles=self._lines,
                labels=[line.get_label() for line in self._lines],
                loc="best",
                frameon=frame_enabled,
                fontsize=font_size,
            )
        if legend is None:
            return

        if legend_style is not None and frame_enabled:
            frame = legend.get_frame()
            frame.set_facecolor(legend_style.background_color)
            frame.set_edgecolor(legend_style.border_color)
            frame.set_alpha(legend_style.opacity)

        for legend_line, original_line in zip(legend.get_lines(), self._lines):
            legend_line.set_picker(True)
            legend_line.set_pickradius(6)
            legend_line.set_alpha(1.0 if original_line.get_visible() else 0.25)
            self._legend_artist_to_line[legend_line] = original_line

        for legend_text, original_line in zip(legend.get_texts(), self._lines):
            legend_text.set_picker(True)
            legend_text.set_alpha(1.0 if original_line.get_visible() else 0.25)
            self._legend_artist_to_line[legend_text] = original_line

    def _legend_labels(self, location: str) -> list[str]:
        outside_layout = OUTSIDE_LEGEND_LAYOUTS.get(location)
        labels = [line.get_label() for line in self._lines]
        if outside_layout is None:
            return labels

        wrap_width = int(outside_layout["wrap_width"])
        return [
            textwrap.fill(
                label,
                width=wrap_width,
                break_long_words=True,
                break_on_hyphens=False,
            )
            for label in labels
        ]

    def _legend_kwargs(
        self,
        location: str,
        frame_enabled: bool,
        font_size: int,
        legend_labels: list[str],
    ) -> dict:
        outside_layout = OUTSIDE_LEGEND_LAYOUTS.get(location)
        if outside_layout is None:
            self.figure.set_tight_layout(True)
            return {"loc": location, "frameon": frame_enabled, "fontsize": font_size}

        self.figure.set_tight_layout(False)
        adjust = dict(outside_layout["adjust"])
        if location in {"outside top", "outside bottom"}:
            legend_rows = sum(label.count("\n") + 1 for label in legend_labels)
            reserved = min(0.58, 0.10 + legend_rows * 0.040 * max(font_size, 8) / 10)
            if location == "outside top":
                adjust["top"] = max(0.30, 1.0 - reserved)
            else:
                adjust["bottom"] = min(0.60, reserved)
        self.figure.subplots_adjust(**adjust)
        kwargs = {
            "loc": outside_layout["loc"],
            "bbox_to_anchor": outside_layout["bbox_to_anchor"],
            "bbox_transform": self.figure.transFigure
            if location in {"outside top", "outside bottom"}
            else self.axes.transAxes,
            "borderaxespad": 0.0,
            "frameon": frame_enabled,
            "fontsize": font_size,
        }
        if location in {"outside top", "outside bottom"}:
            kwargs["ncol"] = 1
        return kwargs

    def _handle_pick(self, event: object) -> None:
        artist = getattr(event, "artist", None)
        line = self._legend_artist_to_line.get(artist)
        if line is None and isinstance(artist, Line2D):
            curve_id = self._line_to_curve_id.get(artist)
            if curve_id is not None:
                self.curve_selected.emit(curve_id)
            return
        if line is None:
            return

        line.set_visible(not line.get_visible())
        curve_id = self._line_to_curve_id.get(line)
        if curve_id is not None:
            self._curve_visibility[curve_id] = line.get_visible()
        self._refresh_legend(self._last_legend_style, self._last_font_size)
        self.canvas.draw_idle()
