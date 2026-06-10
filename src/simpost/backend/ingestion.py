"""File discovery and lightweight comma-separated shape parsing."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


ScanResult = dict[str, Any]


def scan_directory(directory_path: str, extensions: list[str]) -> list[ScanResult]:
    """Recursively scan a directory for comma-separated result files.

    The file extension is only used for discovery. Matching files are parsed as
    comma-separated text regardless of whether they use .csv, .dat, .out, .res,
    .txt, or another user-provided suffix.
    """

    root = Path(directory_path).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Directory does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    normalized_extensions = _normalize_extensions(extensions)
    if not normalized_extensions:
        raise ValueError("At least one file extension is required.")

    results: list[ScanResult] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item).lower()):
        if not path.is_file() or not _matches_extension(path, normalized_extensions):
            continue

        stat = path.stat()
        shape = _parse_comma_separated_shape(path)
        results.append(
            {
                "path": str(path.resolve()),
                "filename": path.name,
                "size_bytes": stat.st_size,
                "modified_timestamp": stat.st_mtime,
                "row_count": shape["row_count"],
                "column_count": shape["column_count"],
                "parse_warning": shape["parse_warning"],
                "parse_error": shape["parse_error"],
            }
        )

    return results


def parse_file_headers(
    filepath: str,
    name_row: int = 0,
    unit_row: int | None = 1,
    label_row: int | None = None,
) -> dict:
    """Parse parameter names and units from a comma-separated simulation file.

    Row indexes are zero-based. Set unit_row to None when the file does not
    contain a dedicated units row. Set label_row to a row that contains
    preferred curve labels.
    """

    path = Path(filepath).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    if name_row < 0:
        raise ValueError("name_row must be zero or greater.")
    if unit_row is not None and unit_row < 0:
        raise ValueError("unit_row must be zero or greater when provided.")
    if label_row is not None and label_row < 0:
        raise ValueError("label_row must be zero or greater when provided.")

    try:
        rows = _read_csv_rows(path, include_empty_rows=True)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"Could not parse comma-separated data: {exc}") from exc

    if name_row >= len(rows):
        raise ValueError(f"Parameter name row {name_row + 1} is outside the file.")

    parameters = [cell.strip() for cell in rows[name_row]]
    units = _read_units_row(rows, unit_row, len(parameters))
    plot_labels = _read_label_row(rows, label_row, len(parameters))
    data_start_row = _data_start_row(name_row, unit_row, label_row)
    warnings = _parameter_warnings(parameters)

    if unit_row is not None and unit_row >= len(rows):
        warnings.append(
            {
                "column": None,
                "parameter": "",
                "message": f"Units row {unit_row + 1} is outside the file.",
            }
        )
    if label_row is not None and label_row >= len(rows):
        warnings.append(
            {
                "column": None,
                "parameter": "",
                "message": f"Label row {label_row + 1} is outside the file.",
            }
        )

    return {
        "parameters": parameters,
        "units": units,
        "plot_labels": plot_labels,
        "data_start_row": data_start_row,
        "num_data_rows": _count_data_rows(rows, data_start_row),
        "warnings": warnings,
    }


def get_plot_data(
    filepath: str,
    x_param: str,
    y_param: str,
    name_row: int,
    unit_row: int | None,
    data_start_row: int,
) -> dict:
    """Return numeric x/y data and axis labels for two file parameters."""

    path = Path(filepath).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    if name_row < 0:
        raise ValueError("name_row must be zero or greater.")
    if unit_row is not None and unit_row < 0:
        raise ValueError("unit_row must be zero or greater when provided.")
    if data_start_row < 0:
        raise ValueError("data_start_row must be zero or greater.")

    try:
        rows = _read_csv_rows(path, include_empty_rows=True)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"Could not parse comma-separated data: {exc}") from exc

    if name_row >= len(rows):
        raise ValueError(f"Parameter name row {name_row + 1} is outside the file.")

    parameters = [cell.strip() for cell in rows[name_row]]
    units = _read_units_row(rows, unit_row, len(parameters))
    x_index = _parameter_index(parameters, x_param)
    y_index = _parameter_index(parameters, y_param)

    x_values: list[float] = []
    y_values: list[float] = []
    for row_number, row in enumerate(rows[data_start_row:], start=data_start_row + 1):
        if not any(cell.strip() for cell in row):
            continue

        x_values.append(_numeric_cell(row, x_index, row_number, x_param))
        y_values.append(_numeric_cell(row, y_index, row_number, y_param))

    return {
        "x": x_values,
        "y": y_values,
        "x_label": _format_axis_label(parameters[x_index], units[x_index]),
        "y_label": _format_axis_label(parameters[y_index], units[y_index]),
    }


def _normalize_extensions(extensions: list[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for extension in extensions:
        cleaned = extension.strip().lower()
        if not cleaned:
            continue
        if cleaned.startswith("*."):
            cleaned = cleaned[1:]
        elif not cleaned.startswith("."):
            cleaned = f".{cleaned}"
        normalized.add(cleaned)
    return tuple(sorted(normalized))


def _matches_extension(path: Path, extensions: tuple[str, ...]) -> bool:
    name = path.name.lower()
    return any(name.endswith(extension) for extension in extensions)


def _parse_comma_separated_shape(path: Path) -> ScanResult:
    try:
        rows = _read_csv_rows(path)
    except (OSError, UnicodeError, csv.Error) as exc:
        return {
            "row_count": 0,
            "column_count": 0,
            "parse_warning": None,
            "parse_error": f"Could not parse comma-separated data: {exc}",
        }

    if not rows:
        return {
            "row_count": 0,
            "column_count": 0,
            "parse_warning": None,
            "parse_error": "File contains no comma-separated rows.",
        }

    column_counts = [len(row) for row in rows]
    column_count = max(column_counts)
    data_rows = rows[1:] if _looks_like_header(rows) else rows
    parse_warning = None

    if len(set(column_counts)) > 1:
        parse_warning = "Rows have inconsistent column counts."

    return {
        "row_count": len(data_rows),
        "column_count": column_count,
        "parse_warning": parse_warning,
        "parse_error": None,
    }


def _read_units_row(rows: list[list[str]], unit_row: int | None, parameter_count: int) -> list[str]:
    if unit_row is None or unit_row >= len(rows):
        return [""] * parameter_count

    units = [cell.strip() for cell in rows[unit_row]]
    if len(units) < parameter_count:
        units.extend([""] * (parameter_count - len(units)))
    return units[:parameter_count]


def _read_label_row(rows: list[list[str]], label_row: int | None, parameter_count: int) -> list[str]:
    if label_row is None or label_row >= len(rows):
        return [""] * parameter_count

    labels = [cell.strip() for cell in rows[label_row]]
    non_empty_labels = [label for label in labels if label]
    if len(non_empty_labels) == 1:
        return [non_empty_labels[0]] * parameter_count
    if len(labels) < parameter_count:
        labels.extend([""] * (parameter_count - len(labels)))
    return labels[:parameter_count]


def _data_start_row(name_row: int, unit_row: int | None, label_row: int | None = None) -> int:
    configured_rows = [name_row]
    if unit_row is not None:
        configured_rows.append(unit_row)
    if label_row is not None:
        configured_rows.append(label_row)
    return max(configured_rows) + 1


def _count_data_rows(rows: list[list[str]], data_start_row: int) -> int:
    return sum(1 for row in rows[data_start_row:] if any(cell.strip() for cell in row))


def _parameter_warnings(parameters: list[str]) -> list[dict]:
    warnings: list[dict] = []
    for index, parameter in enumerate(parameters):
        if not parameter:
            warnings.append(
                {
                    "column": index,
                    "parameter": parameter,
                    "message": "Parameter name is empty.",
                }
            )
        elif _is_number(parameter):
            warnings.append(
                {
                    "column": index,
                    "parameter": parameter,
                    "message": "Parameter name is numeric.",
                }
            )
    return warnings


def _parameter_index(parameters: list[str], parameter: str) -> int:
    target = parameter.strip()
    for index, candidate in enumerate(parameters):
        if candidate.strip() == target:
            return index
    raise ValueError(f"Parameter not found in file header: {parameter}")


def _numeric_cell(row: list[str], column_index: int, row_number: int, parameter: str) -> float:
    if column_index >= len(row):
        raise ValueError(f"Row {row_number} does not contain parameter {parameter}.")

    value = row[column_index].strip()
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(
            f"Row {row_number} has non-numeric value for {parameter}: {value!r}"
        ) from exc


def _format_axis_label(parameter: str, unit: str) -> str:
    parameter = parameter.strip()
    unit = unit.strip()
    return f"{parameter} ({unit})" if unit else parameter


def _read_csv_rows(path: Path, include_empty_rows: bool = False) -> list[list[str]]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                reader = csv.reader(file)
                rows = [[_clean_cell(cell) for cell in row] for row in reader]
                if include_empty_rows:
                    return rows
                return [row for row in rows if any(cell.strip() for cell in row)]
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    return []


def _clean_cell(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("|"):
        cleaned = cleaned[1:].strip()
    return cleaned


def _looks_like_header(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False

    first_row_has_text = any(cell and not _is_number(cell) for cell in rows[0])
    later_row_has_numeric_data = any(_row_has_numeric_data(row) for row in rows[1:])
    return first_row_has_text and later_row_has_numeric_data


def _row_has_numeric_data(row: list[str]) -> bool:
    values = [cell for cell in row if cell]
    return bool(values) and all(_is_number(cell) for cell in values)


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True
