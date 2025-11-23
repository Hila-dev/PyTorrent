from __future__ import annotations

import os
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QWidget, QApplication


class TrayController:

    def __init__(
        self,
        app: QApplication,
        window: QWidget,
        icon_path: str | None = None,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self._app = app
        self._window = window
        self._on_quit = on_quit

        if icon_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base_dir, "ico", "ico.ico")

        self._tray_icon = QSystemTrayIcon(QIcon(icon_path), window)
        self._tray_icon.setToolTip(window.windowTitle() or "PyTorrent")

        self._menu = QMenu()

        self._show_action = QAction("Open", self._menu)
        self._show_action.triggered.connect(self._on_show_window)
        self._menu.addAction(self._show_action)

        self._menu.addSeparator()

        self._quit_action = QAction("Close", self._menu)
        self._quit_action.triggered.connect(self._on_quit_requested)
        self._menu.addAction(self._quit_action)

        self._tray_icon.setContextMenu(self._menu)
        self._tray_icon.activated.connect(self._on_activated)
        self._tray_icon.setVisible(True)

    def _on_show_window(self) -> None:
        self.restore_window_from_tray()

    def _on_quit_requested(self) -> None:
        if self._on_quit is not None:

            self._on_quit()


        self._tray_icon.hide()
        self._app.quit()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:  # type: ignore[name-defined]
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self._window.isVisible() and not self._window.isMinimized():
                self._window.hide()
            else:
                self.restore_window_from_tray()

    def show_message(self, title: str, message: str, timeout_ms: int = 3000) -> None:
        self._tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, timeout_ms)

    def minimize_to_tray(self) -> None:
        self._window.hide()

    def restore_window_from_tray(self) -> None:
        self._window.show()
        self._window.setWindowState(self._window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)  # type: ignore[name-defined]
        self._window.raise_()
        self._window.activateWindow()

    def hide(self) -> None:
        self._tray_icon.hide()


def create_tray(app: QApplication, window: QWidget, icon_path: str | None = None, on_quit: Callable[[], None] | None = None) -> TrayController:
    return TrayController(app=app, window=window, icon_path=icon_path, on_quit=on_quit)
