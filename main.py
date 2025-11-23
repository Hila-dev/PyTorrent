import os
import sys

from PySide6.QtCore import Qt, QTimer, QUrl, QEvent
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QLabel,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
)

from torrent_engine import TorrentEngine
from tray import create_tray


def human_size(num_bytes: int) -> str:
    n = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def human_speed(num_bytes_per_sec: int) -> str:
    if num_bytes_per_sec <= 0:
        return "0 B/s"
    return human_size(num_bytes_per_sec) + "/s"


def human_progress(progress: float) -> str:
    return f"{progress * 100:.1f} %"


def human_eta(seconds: int) -> str:
    if seconds < 0 or seconds > 365 * 24 * 3600:
        return "—"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyTorrent")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "ico/ico.ico")
        self.setWindowIcon(QIcon(icon_path))
        self.tray = None
        home_dir = os.path.expanduser("~")
        self.download_path = os.path.join(home_dir, "Downloads")
        os.makedirs(self.download_path, exist_ok=True)
        self.engine = TorrentEngine(self.download_path)
        self._status_by_id = {}
        self._init_ui()
        self._init_timer()

    def _init_ui(self) -> None:
        central = QWidget(self)
        central.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)
        central.setLayout(root_layout)
        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)
        path_label = QLabel("Download folder:")
        self.download_path_edit = QLineEdit(self.download_path)
        self.download_path_edit.setReadOnly(True)
        path_button = QPushButton("Change...")
        path_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        path_button.clicked.connect(self.change_download_path)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.download_path_edit)
        path_layout.addWidget(path_button)
        root_layout.addLayout(path_layout)
        magnet_layout = QHBoxLayout()
        magnet_layout.setSpacing(8)
        magnet_label = QLabel("Magnet:")
        self.magnet_edit = QLineEdit()
        self.magnet_edit.setPlaceholderText("Paste magnet link and press \"Add magnet\"")
        magnet_button = QPushButton("Add magnet")
        magnet_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        magnet_button.clicked.connect(self.add_magnet)
        magnet_layout.addWidget(magnet_label)
        magnet_layout.addWidget(self.magnet_edit)
        magnet_layout.addWidget(magnet_button)
        root_layout.addLayout(magnet_layout)
        control_layout = QHBoxLayout()
        control_layout.setSpacing(8)
        add_torrent_button = QPushButton("Add .torrent")
        add_torrent_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        add_torrent_button.clicked.connect(self.add_torrent_file)
        self.pause_resume_button = QPushButton("Pause / Resume")
        self.pause_resume_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.pause_resume_button.clicked.connect(self.toggle_pause_resume)
        delete_button = QPushButton("Delete")
        delete_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        delete_button.clicked.connect(self.delete_selected)
        open_folder_button = QPushButton("Open folder")
        open_folder_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        open_folder_button.clicked.connect(self.open_download_folder)
        control_layout.addWidget(add_torrent_button)
        control_layout.addWidget(self.pause_resume_button)
        control_layout.addWidget(delete_button)
        control_layout.addWidget(open_folder_button)
        control_layout.addStretch()
        root_layout.addLayout(control_layout)
        self.table = QTableWidget(0, 9, self)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Name",
                "Size",
                "Progress",
                "Download",
                "Upload",
                "Peers",
                "ETA",
                "Status",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(2, 9):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnHidden(0, True)
        vheader = self.table.verticalHeader()
        vheader.setVisible(False)
        vheader.setDefaultSectionSize(26)
        self.table.installEventFilter(self)
        root_layout.addWidget(self.table)
        self.resize(1000, 600)

    def _init_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start()

    def change_download_path(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select download folder", self.download_path)
        if directory:
            self.download_path = directory
            self.download_path_edit.setText(directory)
            self.engine.download_path = directory

    def add_torrent_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select .torrent file",
            "",
            "Torrent files (*.torrent);;All files (*)",
        )
        if not path:
            return
        try:
            self.engine.add_torrent_file(path)
            self.refresh_status()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to add torrent:\n{exc}")

    def add_magnet(self) -> None:
        magnet = self.magnet_edit.text().strip()
        if not magnet:
            QMessageBox.information(self, "Magnet", "Enter magnet link.")
            return
        try:
            self.engine.add_magnet(magnet)
            self.magnet_edit.clear()
            self.refresh_status()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to add magnet link:\n{exc}")

    def current_torrent_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return item.text()

    def toggle_pause_resume(self) -> None:
        tid = self.current_torrent_id()
        if not tid:
            QMessageBox.information(self, "Torrent", "Select torrent in the list.")
            return
        status = self._status_by_id.get(tid)
        if status and status.get("is_paused"):
            self.engine.resume(tid)
        else:
            self.engine.pause(tid)
        self.refresh_status()

    def delete_selected(self) -> None:
        tid = self.current_torrent_id()
        if not tid:
            QMessageBox.information(self, "Torrent", "Select torrent in the list.")
            return
        answer = QMessageBox.question(
            self,
            "Delete torrent",
            "Delete files from disk together with the torrent?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return
        delete_files = answer == QMessageBox.StandardButton.Yes
        try:
            self.engine.remove(tid, delete_files=delete_files)
            self.refresh_status()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to delete torrent:\n{exc}")

    def open_download_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.download_path))

    def refresh_status(self) -> None:
        statuses = self.engine.get_status_list()
        self._status_by_id = {s["id"]: s for s in statuses}
        self.table.setRowCount(len(statuses))
        for row, s in enumerate(statuses):
            values = [
                s["id"],
                s["name"],
                human_size(s["total_size"]) if s["total_size"] > 0 else "",
                human_progress(s["progress"]),
                human_speed(int(s["download_rate"])),
                human_speed(int(s["upload_rate"])),
                str(s["num_peers"]),
                human_eta(int(s["eta"])) if s["eta"] >= 0 else "—",
                s["state"],
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif col in (2, 4, 5, 6, 7):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, col, item)

    def eventFilter(self, obj, event):  # type: ignore[override]
        if obj is self.table and event.type() == QEvent.Type.FocusOut:
            self.table.clearSelection()
        return super().eventFilter(obj, event)

    def changeEvent(self, event):  # type: ignore[override]
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized() and self.tray is not None:
                event.ignore()
                self.hide()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.tray is not None:
            box = QMessageBox(self)
            box.setWindowTitle("Exit")
            box.setText("Do you want to close the program or minimize it to the tray?")
            close_button = box.addButton("Close program", QMessageBox.ButtonRole.AcceptRole)
            minimize_button = box.addButton("Minimize to tray", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(minimize_button)
            box.exec()

            if box.clickedButton() is minimize_button:
                event.ignore()
                self.hide()
                return

        self.timer.stop()
        try:
            self.engine.close()
        except Exception:
            pass
        super().closeEvent(event)


def load_styles(app: QApplication) -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    qss_path = os.path.join(base_dir, "styles.qss")
    if os.path.exists(qss_path):
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        except Exception:
            pass


def main() -> None:
    app = QApplication(sys.argv)
    load_styles(app)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "ico/ico.ico")
    app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    tray_icon_path = os.path.join(base_dir, "ico", "ico.ico")

    def on_quit() -> None:
        window.tray = None
        window.close()

    window.tray = create_tray(app, window, icon_path=tray_icon_path, on_quit=on_quit)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
