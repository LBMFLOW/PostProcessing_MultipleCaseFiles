"""Application entry point."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from simpost.ui.main_window import MainWindow, SETTINGS_APPLICATION, SETTINGS_ORGANIZATION


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(SETTINGS_APPLICATION)
    app.setOrganizationName(SETTINGS_ORGANIZATION)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
