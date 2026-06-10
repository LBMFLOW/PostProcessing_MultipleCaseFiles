"""Batch SVG export for simulation plots."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("svg", force=True)
from matplotlib import pyplot as plt  # noqa: E402

from simpost.backend.ingestion import get_plot_data, parse_file_headers


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
        "adjust": {"left": 0.10, "right": 0.76, "bottom": 0.12, "top": 0.90},
    },
    "outside left": {
        "loc": "center right",
        "bbox_to_anchor": (-0.08, 0.5),
        "adjust": {"left": 0.30, "right": 0.96, "bottom": 0.12, "top": 0.90},
    },
    "outside top": {
        "loc": "lower center",
        "bbox_to_anchor": (0.5, 1.12),
        "adjust": {"left": 0.12, "right": 0.96, "bottom": 0.12, "top": 0.76},
    },
    "outside bottom": {
        "loc": "upper center",
        "bbox_to_anchor": (0.5, -0.18),
        "adjust": {"left": 0.12, "right": 0.96, "bottom": 0.28, "top": 0.90},
    },
}


def batch_export_svg(
    plot_template: dict,
    progress_callback: Callable[[int, int, dict], None] | None = None,
) -> list[dict]:
    """Export one SVG per selected file using a serialized plot template."""

    output_directory = Path(plot_template["output_directory"]).expanduser()
    files = list(plot_template["files"])
    total = len(files)
    results: list[dict] = []

    try:
        output_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return [
            {
                "filepath": str(file_info.get("path", "")),
                "output_path": "",
                "success": False,
                "error": f"Could not prepare output directory: {exc}",
            }
            for file_info in files
        ]

    with plt.rc_context(
        {
            "svg.fonttype": "path",
            "font.family": "DejaVu Sans",
        }
    ):
        for index, file_info in enumerate(files, start=1):
            result = _export_one_file(plot_template, file_info, output_directory)
            results.append(result)
            if progress_callback is not None:
                progress_callback(index, total, result)

    return results


def _export_one_file(plot_template: dict, file_info: dict, output_directory: Path) -> dict:
    filepath = str(file_info["path"])
    output_path = output_directory / _render_filename(plot_template, file_info)

    try:
        header_info = parse_file_headers(
            filepath,
            name_row=int(plot_template["name_row"]),
            unit_row=plot_template.get("unit_row"),
            label_row=plot_template.get("label_row"),
        )
        plot_data = get_plot_data(
            filepath,
            x_param=str(plot_template["x_param"]),
            y_param=str(plot_template["y_param"]),
            name_row=int(plot_template["name_row"]),
            unit_row=plot_template.get("unit_row"),
            data_start_row=int(header_info["data_start_row"]),
        )

        plot_style = plot_template["plot_style"]
        plot_data["x_label"] = str(
            plot_style.get("x_axis_title") or plot_template.get("x_label") or plot_data["x_label"]
        )
        plot_data["y_label"] = str(
            plot_style.get("y_axis_title") or plot_template.get("y_label") or plot_data["y_label"]
        )
        plot_data["curve_label"] = _curve_label(plot_template, header_info)
        _save_svg(plot_template, plot_data, output_path)
        return {"filepath": filepath, "output_path": str(output_path), "success": True, "error": ""}
    except Exception as exc:
        return {"filepath": filepath, "output_path": str(output_path), "success": False, "error": str(exc)}


def _save_svg(plot_template: dict, plot_data: dict, output_path: Path) -> None:
    figure_size = plot_template.get("figure_size_inches", [8.0, 5.0])
    dpi = int(plot_template.get("dpi", 100))
    figure, axes = plt.subplots(figsize=figure_size, dpi=dpi)

    try:
        style = plot_template["curve_style"]
        axes.plot(
            plot_data["x"],
            plot_data["y"],
            label=str(plot_data.get("curve_label") or plot_template["y_label"]),
            color=style.get("color", "#0072B2"),
            linestyle=LINE_STYLE_MAP.get(style.get("line_style", "solid"), "-"),
            linewidth=float(style.get("line_weight", 1.5)),
            marker=MARKER_STYLE_MAP.get(style.get("marker_style", "none")),
            markersize=float(style.get("marker_size", 6.0)),
            alpha=float(style.get("opacity", 1.0)),
        )

        plot_style = plot_template["plot_style"]
        font_size = int(plot_style.get("font_size", 10))
        axes.set_title(str(plot_style.get("plot_title") or ""), fontsize=font_size + 2)
        axes.set_xlabel(plot_data["x_label"], fontsize=font_size)
        axes.set_ylabel(plot_data["y_label"], fontsize=font_size)
        axes.tick_params(axis="both", labelsize=font_size)

        grid = plot_style.get("grid") or {}
        if grid.get("enabled", True):
            axes.grid(
                True,
                color=grid.get("color", "#b0b0b0"),
                alpha=float(grid.get("opacity", 0.3)),
            )
        else:
            axes.grid(False)

        if not plot_template.get("auto_axis_ranges_per_file", True):
            x_range = plot_style.get("x_range") or {}
            y_range = plot_style.get("y_range") or {}
            if _has_valid_range(x_range):
                axes.set_xlim(float(x_range["minimum"]), float(x_range["maximum"]))
            if _has_valid_range(y_range):
                axes.set_ylim(float(y_range["minimum"]), float(y_range["maximum"]))

        legend_style = plot_style.get("legend") or {}
        if legend_style.get("visible", True):
            frame_enabled = legend_style.get("frame_enabled", True)
            legend_kwargs = _legend_kwargs(
                figure,
                str(legend_style.get("location", "best")),
                frame_enabled,
                font_size,
            )
            try:
                legend = axes.legend(**legend_kwargs)
            except ValueError:
                legend = axes.legend(loc="best", frameon=frame_enabled, fontsize=font_size)
            if legend is not None and legend_style.get("frame_enabled", True):
                frame = legend.get_frame()
                frame.set_facecolor(legend_style.get("background_color", "#ffffff"))
                frame.set_edgecolor(legend_style.get("border_color", "#808080"))
                frame.set_alpha(float(legend_style.get("opacity", 0.8)))
        figure.savefig(output_path, format="svg", bbox_inches="tight")
    finally:
        plt.close(figure)


def _has_valid_range(range_state: dict) -> bool:
    minimum = float(range_state.get("minimum", 0.0))
    maximum = float(range_state.get("maximum", 0.0))
    return minimum < maximum


def _legend_kwargs(figure, location: str, frame_enabled: bool, font_size: int) -> dict:
    outside_layout = OUTSIDE_LEGEND_LAYOUTS.get(location)
    if outside_layout is None:
        return {"loc": location, "frameon": frame_enabled, "fontsize": font_size}

    figure.subplots_adjust(**outside_layout["adjust"])
    kwargs = {
        "loc": outside_layout["loc"],
        "bbox_to_anchor": outside_layout["bbox_to_anchor"],
        "borderaxespad": 0.0,
        "frameon": frame_enabled,
        "fontsize": font_size,
    }
    if location in {"outside top", "outside bottom"}:
        kwargs["ncol"] = 1
    return kwargs


def _curve_label(plot_template: dict, header_info: dict) -> str:
    label_row = plot_template.get("label_row")
    if label_row is not None:
        column_index = int(plot_template.get("y_column_index", -1))
        labels = header_info.get("plot_labels", [])
        if 0 <= column_index < len(labels):
            label = str(labels[column_index]).strip()
            if label:
                return label
    return str(plot_template.get("curve_label") or plot_template["y_label"])


def _render_filename(plot_template: dict, file_info: dict) -> str:
    source_path = Path(str(file_info["path"]))
    replacements = {
        "casename": source_path.stem,
        "filename": source_path.name,
        "x_param": str(plot_template.get("x_display") or plot_template["x_param"]),
        "y_param": str(plot_template.get("y_display") or plot_template["y_param"]),
    }
    filename = str(plot_template["filename_pattern"])
    for key, value in replacements.items():
        filename = filename.replace(f"{{{key}}}", _safe_filename_part(value))

    if not filename.lower().endswith(".svg"):
        filename = f"{filename}.svg"
    return _safe_filename(filename)


def _safe_filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._") or "plot"


def _safe_filename(filename: str) -> str:
    stem = Path(filename).stem
    suffix = Path(filename).suffix or ".svg"
    return f"{_safe_filename_part(stem)}{suffix}"
