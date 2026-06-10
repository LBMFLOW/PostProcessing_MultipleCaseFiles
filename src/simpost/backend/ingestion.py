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


def _read_csv_rows(path: Path) -> list[list[str]]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                reader = csv.reader(file)
                return [
                    [cell.strip() for cell in row]
                    for row in reader
                    if any(cell.strip() for cell in row)
                ]
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    return []


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
