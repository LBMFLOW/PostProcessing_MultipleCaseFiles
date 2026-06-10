from __future__ import annotations

import unittest
import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from simpost.backend.ingestion import scan_directory


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


if __name__ == "__main__":
    unittest.main()
