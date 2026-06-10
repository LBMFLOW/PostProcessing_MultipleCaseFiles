"""Smoke test the Qt frontend stack used by the scaffold."""

from __future__ import annotations

import matplotlib
from PyQt6.QtCore import QTimer, qVersion
from PyQt6.QtWidgets import QApplication

from simpost.ui.main_window import MainWindow


def main() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()

    QTimer.singleShot(100, app.quit)

    print(f"Qt version: {qVersion()}")
    print(f"Matplotlib version: {matplotlib.__version__}")
    print("MainWindow smoke test ok")

    result = app.exec()
    print("QApplication event loop ok")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
