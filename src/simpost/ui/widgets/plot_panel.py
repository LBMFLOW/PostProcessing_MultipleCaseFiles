"""Matplotlib plot canvas scaffold."""

from __future__ import annotations

import bisect
import math
import textwrap

import matplotlib.patheffects as path_effects
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.transforms import blended_transform_factory
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
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
        self._selected_curve_id: str | None = None
        self._trace_enabled = False
        self._trace_dragging = False
        self._trace_x_value: float | None = None
        self._trace_artists: dict[str, object] = {}
        self._trace_action = self._add_trace_action()
        self._set_empty_state()
        self.canvas.mpl_connect("pick_event", self._handle_pick)
        self.canvas.mpl_connect("button_press_event", self._handle_trace_press)
        self.canvas.mpl_connect("motion_notify_event", self._handle_trace_motion)
        self.canvas.mpl_connect("button_release_event", self._handle_trace_release)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    def _add_trace_action(self):
        self.toolbar.addSeparator()
        action = self.toolbar.addAction(
            self._trace_icon(),
            "Trace selected curve",
            self._handle_trace_action_toggled,
        )
        action.setCheckable(True)
        action.setToolTip("Trace selected curve values")
        return action

    def _trace_icon(self) -> QIcon:
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#3b5fd8"), 1.6))
        painter.drawLine(12, 4, 12, 20)
        painter.drawLine(4, 12, 20, 12)
        painter.setBrush(QColor("#fff36a"))
        painter.setPen(QPen(QColor("#a89a00"), 1.0))
        painter.drawRoundedRect(3, 15, 10, 6, 1, 1)
        painter.drawRoundedRect(13, 3, 8, 6, 1, 1)
        painter.end()

        return QIcon(pixmap)

    def _set_empty_state(self) -> None:
        self._clear_trace_overlay(draw=False)
        self.axes.set_title("No dataset loaded")
        self.axes.set_xlabel("X")
        self.axes.set_ylabel("Y")
        self.axes.grid(True, alpha=0.3)
        self.canvas.draw_idle()

    def reset_curve_visibility(self) -> None:
        self._curve_visibility.clear()

    def render_curves(
        self,
        curves: list[CurveState],
        plot_style: PlotStyleState,
        selected_curve_id: str | None = None,
    ) -> None:
        self._clear_trace_overlay(draw=False)
        self.axes.clear()
        self._lines = []
        self._legend_artist_to_line.clear()
        self._line_to_curve_id.clear()
        self._selected_curve_id = selected_curve_id

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
        self._refresh_trace_overlay()
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
        self._refresh_trace_overlay()
        self.canvas.draw_idle()

    def _handle_trace_action_toggled(self, checked: bool) -> None:
        self._trace_enabled = checked
        self._trace_dragging = False
        if checked:
            self._refresh_trace_overlay()
        else:
            self._clear_trace_overlay()

    def _handle_trace_press(self, event: object) -> None:
        if not self._can_handle_trace_mouse_event(event):
            return
        if getattr(event, "button", None) not in (1, None):
            return
        self._trace_dragging = True
        self._update_trace_overlay(float(getattr(event, "xdata")))

    def _handle_trace_motion(self, event: object) -> None:
        if not self._trace_dragging or not self._can_handle_trace_mouse_event(event):
            return
        self._update_trace_overlay(float(getattr(event, "xdata")))

    def _handle_trace_release(self, event: object) -> None:
        if self._trace_dragging and self._can_handle_trace_mouse_event(event):
            self._update_trace_overlay(float(getattr(event, "xdata")))
        self._trace_dragging = False

    def _can_handle_trace_mouse_event(self, event: object) -> bool:
        if not self._trace_enabled:
            return False
        if getattr(event, "inaxes", None) is not self.axes:
            return False
        if getattr(event, "xdata", None) is None:
            return False
        if self._toolbar_mode_active():
            return False
        return self._trace_curve_line() is not None

    def _toolbar_mode_active(self) -> bool:
        mode = getattr(self.toolbar, "mode", "")
        return bool(str(mode))

    def _refresh_trace_overlay(self) -> None:
        if not self._trace_enabled:
            return

        line = self._trace_curve_line()
        if line is None:
            self._clear_trace_overlay()
            return

        x_values = self._clean_trace_points(line)[0]
        if not x_values:
            self._clear_trace_overlay()
            return

        if self._trace_x_value is None:
            x_min, x_max = self.axes.get_xlim()
            self._trace_x_value = min(max((x_min + x_max) / 2.0, x_values[0]), x_values[-1])

        self._update_trace_overlay(self._trace_x_value)

    def _trace_curve_line(self) -> Line2D | None:
        if self._selected_curve_id is not None:
            for line in self._lines:
                if self._line_to_curve_id.get(line) == self._selected_curve_id and line.get_visible():
                    return line

        for line in self._lines:
            if line.get_visible():
                return line
        return None

    def _update_trace_overlay(self, x_value: float) -> None:
        line = self._trace_curve_line()
        if line is None:
            self._clear_trace_overlay()
            return

        x_values, y_values = self._clean_trace_points(line)
        if not x_values:
            self._clear_trace_overlay()
            return

        x_value = min(max(x_value, x_values[0]), x_values[-1])
        y_value = self._interpolate_y_value(x_values, y_values, x_value)
        self._trace_x_value = x_value

        if not self._trace_artists:
            self._create_trace_artists(line, x_value, y_value)
        else:
            self._set_trace_artist_values(x_value, y_value)

        self.canvas.draw_idle()

    def _create_trace_artists(self, line: Line2D, x_value: float, y_value: float) -> None:
        guide_color = "#666666"
        label_box = {
            "boxstyle": "square,pad=0.18",
            "facecolor": "#fff36a",
            "edgecolor": "#b7aa00",
            "linewidth": 0.8,
        }

        vline = self.axes.axvline(
            x_value,
            color=guide_color,
            linestyle=(0, (4, 3)),
            linewidth=0.8,
            zorder=40,
        )
        hline = self.axes.axhline(
            y_value,
            color=guide_color,
            linestyle=(0, (4, 3)),
            linewidth=0.8,
            zorder=40,
        )
        (marker,) = self.axes.plot(
            [x_value],
            [y_value],
            marker="o",
            markersize=4.5,
            color="#fff36a",
            markeredgecolor=line.get_color(),
            markeredgewidth=1.0,
            linestyle="none",
            zorder=45,
        )

        x_label = self.axes.text(
            x_value,
            -0.045,
            self._format_trace_value(x_value),
            transform=blended_transform_factory(self.axes.transData, self.axes.transAxes),
            ha="center",
            va="top",
            fontsize=8,
            color="#111111",
            bbox=label_box,
            clip_on=False,
            zorder=46,
        )
        y_label = self.axes.text(
            -0.025,
            y_value,
            self._format_trace_value(y_value),
            transform=blended_transform_factory(self.axes.transAxes, self.axes.transData),
            ha="right",
            va="center",
            fontsize=8,
            color="#111111",
            bbox=label_box,
            clip_on=False,
            zorder=46,
        )

        self._trace_artists = {
            "vline": vline,
            "hline": hline,
            "marker": marker,
            "x_label": x_label,
            "y_label": y_label,
        }

    def _set_trace_artist_values(self, x_value: float, y_value: float) -> None:
        vline = self._trace_artists["vline"]
        hline = self._trace_artists["hline"]
        marker = self._trace_artists["marker"]
        x_label = self._trace_artists["x_label"]
        y_label = self._trace_artists["y_label"]

        vline.set_xdata([x_value, x_value])
        hline.set_ydata([y_value, y_value])
        marker.set_data([x_value], [y_value])
        x_label.set_position((x_value, -0.045))
        x_label.set_text(self._format_trace_value(x_value))
        y_label.set_position((-0.025, y_value))
        y_label.set_text(self._format_trace_value(y_value))

    def _clear_trace_overlay(self, draw: bool = True) -> None:
        for artist in self._trace_artists.values():
            try:
                artist.remove()
            except (NotImplementedError, ValueError):
                pass
        self._trace_artists.clear()
        if draw:
            self.canvas.draw_idle()

    def _clean_trace_points(self, line: Line2D) -> tuple[list[float], list[float]]:
        points: list[tuple[float, float]] = []
        for raw_x, raw_y in zip(line.get_xdata(), line.get_ydata()):
            try:
                x_value = float(raw_x)
                y_value = float(raw_y)
            except (TypeError, ValueError):
                continue
            if math.isfinite(x_value) and math.isfinite(y_value):
                points.append((x_value, y_value))

        if not points:
            return [], []

        points.sort(key=lambda point: point[0])
        return [point[0] for point in points], [point[1] for point in points]

    def _interpolate_y_value(
        self,
        x_values: list[float],
        y_values: list[float],
        x_value: float,
    ) -> float:
        if x_value <= x_values[0]:
            return y_values[0]
        if x_value >= x_values[-1]:
            return y_values[-1]

        right_index = bisect.bisect_left(x_values, x_value)
        left_index = max(0, right_index - 1)
        x_left = x_values[left_index]
        x_right = x_values[right_index]
        y_left = y_values[left_index]
        y_right = y_values[right_index]
        if x_right == x_left:
            return y_left
        fraction = (x_value - x_left) / (x_right - x_left)
        return y_left + fraction * (y_right - y_left)

    def _format_trace_value(self, value: float) -> str:
        magnitude = abs(value)
        if magnitude >= 1000:
            text = f"{value:.1f}"
        elif magnitude >= 10:
            text = f"{value:.2f}"
        elif magnitude >= 1:
            text = f"{value:.3f}"
        else:
            text = f"{value:.4g}"
        return text.rstrip("0").rstrip(".") if "." in text else text
