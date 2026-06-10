from __future__ import annotations

import unittest
import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from simpost.backend.export import _legend_label, batch_export_svg
from simpost.backend.ingestion import get_plot_data, parse_file_headers, scan_directory
from simpost.backend.label_formula import DEFAULT_CURVE_LABEL_FORMULA, format_curve_label


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / "test_tmp"


@contextmanager
def temporary_directory() -> Iterator[str]:
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    directory = TEST_TMP_ROOT / f"case_{uuid.uuid4().hex}"
    directory.mkdir()
    try:
        yield str(directory)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


class ScanDirectoryTests(unittest.TestCase):
    def test_scans_non_standard_extensions_recursively(self) -> None:
        with temporary_directory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()

            (root / "run_a.dat").write_text("time,pressure\n0,10\n1,11\n", encoding="utf-8")
            (nested / "run_b.OUT").write_text("0,1,2\n1,2,3\n", encoding="utf-8")
            (root / "ignored.csv").write_text("x,y\n1,2\n", encoding="utf-8")

            results = scan_directory(directory, ["dat", "out"])

        filenames = {result["filename"] for result in results}
        self.assertEqual(filenames, {"run_a.dat", "run_b.OUT"})

        by_name = {result["filename"]: result for result in results}
        self.assertEqual(by_name["run_a.dat"]["row_count"], 2)
        self.assertEqual(by_name["run_a.dat"]["column_count"], 2)
        self.assertEqual(by_name["run_b.OUT"]["row_count"], 2)
        self.assertEqual(by_name["run_b.OUT"]["column_count"], 3)

    def test_reports_parse_warning_for_inconsistent_columns(self) -> None:
        with temporary_directory() as directory:
            root = Path(directory)
            (root / "bad.res").write_text("x,y,z\n1,2\n3,4,5\n", encoding="utf-8")

            results = scan_directory(directory, [".res"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["row_count"], 2)
        self.assertEqual(results[0]["column_count"], 3)
        self.assertEqual(results[0]["parse_warning"], "Rows have inconsistent column counts.")
        self.assertIsNone(results[0]["parse_error"])

    def test_empty_file_is_returned_with_parse_error(self) -> None:
        with temporary_directory() as directory:
            root = Path(directory)
            (root / "empty.txt").write_text("", encoding="utf-8")

            results = scan_directory(directory, ["txt"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["row_count"], 0)
        self.assertEqual(results[0]["column_count"], 0)
        self.assertEqual(results[0]["parse_error"], "File contains no comma-separated rows.")


class ParseFileHeadersTests(unittest.TestCase):
    def test_parses_parameter_names_units_and_data_row_count(self) -> None:
        with temporary_directory() as directory:
            path = Path(directory) / "case.dat"
            path.write_text(
                " time , pressure , temperature \n s , Pa , K \n0,101325,300\n1,101500,301\n",
                encoding="utf-8",
            )

            result = parse_file_headers(str(path))

        self.assertEqual(result["parameters"], ["time", "pressure", "temperature"])
        self.assertEqual(result["units"], ["s", "Pa", "K"])
        self.assertEqual(result["plot_labels"], ["", "", ""])
        self.assertEqual(result["data_start_row"], 2)
        self.assertEqual(result["num_data_rows"], 2)
        self.assertEqual(result["warnings"], [])

    def test_parses_headers_without_units_row(self) -> None:
        with temporary_directory() as directory:
            path = Path(directory) / "case.out"
            path.write_text("time,pressure\n0,101325\n1,101500\n", encoding="utf-8")

            result = parse_file_headers(str(path), name_row=0, unit_row=None)

        self.assertEqual(result["parameters"], ["time", "pressure"])
        self.assertEqual(result["units"], ["", ""])
        self.assertEqual(result["plot_labels"], ["", ""])
        self.assertEqual(result["data_start_row"], 1)
        self.assertEqual(result["num_data_rows"], 2)

    def test_parses_optional_plot_label_row(self) -> None:
        with temporary_directory() as directory:
            path = Path(directory) / "case.dat"
            path.write_text(
                "time,pressure,temperature\n"
                "s,Pa,K\n"
                "elapsed,Case A pressure,Case A temperature\n"
                "0,101325,300\n"
                "1,101500,301\n",
                encoding="utf-8",
            )

            result = parse_file_headers(str(path), name_row=0, unit_row=1, label_row=2)

        self.assertEqual(
            result["plot_labels"],
            ["elapsed", "Case A pressure", "Case A temperature"],
        )
        self.assertEqual(result["data_start_row"], 3)
        self.assertEqual(result["num_data_rows"], 2)

    def test_reuses_single_cell_label_row_for_all_parameters(self) -> None:
        with temporary_directory() as directory:
            path = Path(directory) / "case.trn"
            path.write_text(
                "| T_amb39.52C_T_target45.33C.trn\n"
                "|Time,Pressure,Temperature\n"
                "|sec,Pa,C\n"
                "0,101325,45\n"
                "1,101500,46\n",
                encoding="utf-8",
            )

            result = parse_file_headers(str(path), name_row=1, unit_row=2, label_row=0)

        self.assertEqual(result["parameters"], ["Time", "Pressure", "Temperature"])
        self.assertEqual(result["units"], ["sec", "Pa", "C"])
        self.assertEqual(
            result["plot_labels"],
            [
                "T_amb39.52C_T_target45.33C.trn",
                "T_amb39.52C_T_target45.33C.trn",
                "T_amb39.52C_T_target45.33C.trn",
            ],
        )
        self.assertEqual(result["data_start_row"], 3)

    def test_warns_for_empty_and_numeric_parameter_names(self) -> None:
        with temporary_directory() as directory:
            path = Path(directory) / "case.res"
            path.write_text("time,,123\ns,Pa,K\n0,1,2\n", encoding="utf-8")

            result = parse_file_headers(str(path))

        self.assertEqual(result["parameters"], ["time", "", "123"])
        warnings = {(warning["column"], warning["message"]) for warning in result["warnings"]}
        self.assertEqual(
            warnings,
            {
                (1, "Parameter name is empty."),
                (2, "Parameter name is numeric."),
            },
        )


class GetPlotDataTests(unittest.TestCase):
    def test_returns_numeric_series_and_axis_labels(self) -> None:
        with temporary_directory() as directory:
            path = Path(directory) / "case.dat"
            path.write_text(
                "time,pressure,temperature\ns,Pa,K\n0,101325,300\n1,101500,301\n",
                encoding="utf-8",
            )

            result = get_plot_data(
                str(path),
                x_param="time",
                y_param="pressure",
                name_row=0,
                unit_row=1,
                data_start_row=2,
            )

        self.assertEqual(result["x"], [0.0, 1.0])
        self.assertEqual(result["y"], [101325.0, 101500.0])
        self.assertEqual(result["x_label"], "time (s)")
        self.assertEqual(result["y_label"], "pressure (Pa)")

    def test_returns_axis_labels_without_units(self) -> None:
        with temporary_directory() as directory:
            path = Path(directory) / "case.out"
            path.write_text("time,pressure\n0,101325\n1,101500\n", encoding="utf-8")

            result = get_plot_data(
                str(path),
                x_param="time",
                y_param="pressure",
                name_row=0,
                unit_row=None,
                data_start_row=1,
            )

        self.assertEqual(result["x_label"], "time")
        self.assertEqual(result["y_label"], "pressure")

    def test_rejects_non_numeric_data_values(self) -> None:
        with temporary_directory() as directory:
            path = Path(directory) / "case.res"
            path.write_text("time,pressure\ns,Pa\n0,abc\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "non-numeric value"):
                get_plot_data(
                    str(path),
                    x_param="time",
                    y_param="pressure",
                    name_row=0,
                    unit_row=1,
                    data_start_row=2,
                )


class CurveLabelFormulaTests(unittest.TestCase):
    def test_formats_curve_label_with_removals_and_parameter(self) -> None:
        result = format_curve_label(
            DEFAULT_CURVE_LABEL_FORMULA,
            curve_label="| T_amb39.52C_T_target45.33C.trn",
            parameter="T_cell_mean",
            fallback="fallback",
        )

        self.assertEqual(result, "T_amb39.52C_T_target45.33C_T_cell_mean")

    def test_uses_fallback_when_formula_requires_missing_curve_label(self) -> None:
        result = format_curve_label(
            DEFAULT_CURVE_LABEL_FORMULA,
            curve_label="",
            parameter="Pressure",
            fallback="Pressure",
        )

        self.assertEqual(result, "Pressure")


class LegendLayoutTests(unittest.TestCase):
    def test_wraps_outside_top_long_labels(self) -> None:
        label = "T_amb18.24C_T_target43.66C_T_coolant-19.15C_CoolantFR40.00LPM_T_cell_mean"

        wrapped = _legend_label("outside top", label)

        self.assertIn("\n", wrapped)
        self.assertLessEqual(max(len(line) for line in wrapped.splitlines()), 72)


class BatchExportSvgTests(unittest.TestCase):
    def test_exports_one_svg_per_file(self) -> None:
        with temporary_directory() as directory:
            root = Path(directory)
            output = root / "out"
            file_paths = []
            for index in range(2):
                path = root / f"case_{index}.dat"
                path.write_text(
                    "time,pressure\ns,Pa\n0,100\n1,110\n",
                    encoding="utf-8",
                )
                file_paths.append(path)

            template = _batch_template(file_paths, output)
            results = batch_export_svg(template)

            self.assertEqual([result["success"] for result in results], [True, True])
            for result in results:
                svg_path = Path(result["output_path"])
                self.assertTrue(svg_path.exists())
                self.assertIn("<svg", svg_path.read_text(encoding="utf-8"))

    def test_reports_export_failures_per_file(self) -> None:
        with temporary_directory() as directory:
            root = Path(directory)
            output = root / "out"
            good = root / "good.dat"
            bad = root / "bad.dat"
            good.write_text("time,pressure\ns,Pa\n0,100\n", encoding="utf-8")
            bad.write_text("time,temperature\ns,K\n0,300\n", encoding="utf-8")

            results = batch_export_svg(_batch_template([good, bad], output))

        self.assertEqual(results[0]["success"], True)
        self.assertEqual(results[1]["success"], False)
        self.assertIn("Parameter not found", results[1]["error"])

    def test_exports_gt_style_label_row_with_outside_legend(self) -> None:
        with temporary_directory() as directory:
            root = Path(directory)
            output = root / "out"
            path = root / "case.trn"
            path.write_text(
                "| T_amb39.52C_T_target45.33C.trn\n"
                "|Time,Pressure\n"
                "|sec,Pa\n"
                "0,101325\n"
                "1,101500\n",
                encoding="utf-8",
            )
            template = _batch_template([path], output)
            template["name_row"] = 1
            template["unit_row"] = 2
            template["label_row"] = 0
            template["data_start_row"] = 3
            template["x_param"] = "Time"
            template["y_param"] = "Pressure"
            template["x_label"] = "Time (sec)"
            template["y_label"] = "Pressure (Pa)"
            template["plot_style"]["legend"]["location"] = "outside right"

            results = batch_export_svg(template)

            self.assertEqual([result["success"] for result in results], [True])
            self.assertTrue(Path(results[0]["output_path"]).exists())


def _batch_template(file_paths: list[Path], output: Path) -> dict:
    return {
        "files": [{"path": str(path), "filename": path.name} for path in file_paths],
        "output_directory": str(output),
        "filename_pattern": "{casename}_pressure_vs_time.svg",
        "auto_axis_ranges_per_file": True,
        "x_param": "time",
        "y_param": "pressure",
        "x_display": "time",
        "y_display": "pressure",
        "x_label": "time (s)",
        "y_label": "pressure (Pa)",
        "curve_label": "pressure",
        "curve_label_formula": DEFAULT_CURVE_LABEL_FORMULA,
        "name_row": 0,
        "unit_row": 1,
        "label_row": None,
        "data_start_row": 2,
        "y_column_index": 1,
        "figure_size_inches": [6.0, 4.0],
        "dpi": 100,
        "curve_style": {
            "color": "#0072B2",
            "line_style": "dashed",
            "line_weight": 2.0,
            "marker_style": "circle",
            "marker_size": 5.0,
            "opacity": 0.8,
        },
        "plot_style": {
            "x_range": {"auto": True, "minimum": 0.0, "maximum": 1.0},
            "y_range": {"auto": True, "minimum": 0.0, "maximum": 1.0},
            "plot_title": "",
            "x_axis_title": "",
            "y_axis_title": "",
            "font_size": 10,
            "grid": {"enabled": True, "color": "#b0b0b0", "opacity": 0.3},
            "legend": {
                "visible": True,
                "location": "best",
                "frame_enabled": True,
                "background_color": "#ffffff",
                "border_color": "#808080",
                "opacity": 0.8,
            },
        },
    }


if __name__ == "__main__":
    unittest.main()
