from __future__ import annotations

from pathlib import Path

try:
    from PySide6.QtCore import QObject, QThread, Signal, Slot
    from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog
except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency
    raise RuntimeError('PySide6 is required for the GUI runtime. Install it with: pip install PySide6') from exc

from app.backend import YtDLBackend


class DownloadWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(dict)
    failed = Signal(str)
    log = Signal(str)

    def __init__(self, url: str, output_dir: str):
        super().__init__()
        self.url = url
        self.output_dir = output_dir

    def _progress_hook(self, data: dict):
        if data.get('status') == 'downloading':
            total = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
            downloaded = data.get('downloaded_bytes', 0)
            pct = int(min((downloaded / total) * 100, 100)) if total else 0
            self.progress.emit(pct, f'Downloading: {pct}%')
        elif data.get('status') == 'finished':
            self.log.emit('Download completed; finalizing file...')

    @Slot()
    def run(self):
        try:
            self.log.emit(f'Starting download for: {self.url}')
            backend = YtDLBackend(output_dir=self.output_dir, verbose=True)
            info = backend.download(self.url, output_dir=self.output_dir, progress_callback=self._progress_hook)
            self.finished.emit(info)
            self.log.emit(f'Finished: {info.get("title", "video")}')
        except Exception as exc:  # pragma: no cover - UI surface
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Yt-RivoGUI')
        self.resize(900, 600)
        self.output_dir = str(Path.cwd() / 'downloads')
        self.thread = None
        self.worker = None

        container = QWidget(self)
        self.setCentralWidget(container)

        layout = QVBoxLayout(container)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText('Paste a video URL')

        self.status_label = QLabel('Ready')
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        self.download_button = QPushButton('Download')
        self.download_button.clicked.connect(self.on_download_clicked)

        self.choose_dir_button = QPushButton('Choose output folder')
        self.choose_dir_button.clicked.connect(self.choose_output_dir)

        layout.addWidget(self.url_input)
        layout.addWidget(self.choose_dir_button)
        layout.addWidget(self.download_button)
        layout.addWidget(self.status_label)
        layout.addWidget(self.log_view)

    def log(self, message: str) -> None:
        self.log_view.append(message)
        self.status_label.setText(message)

    def choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, 'Select output folder', self.output_dir)
        if directory:
            self.output_dir = directory
            self.log(f'Output folder: {directory}')

    def on_download_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self.log('URL is required')
            return

        if self.thread and self.thread.isRunning():
            self.log('A download is already in progress.')
            return

        self.worker = DownloadWorker(url, self.output_dir)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)

        self.worker.log.connect(self.log)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_download_finished)
        self.worker.failed.connect(self.on_download_failed)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.start()

        self.download_button.setEnabled(False)
        self.log(f'Queued: {url}')

    def update_progress(self, percentage: int, message: str) -> None:
        self.status_label.setText(message)

    def on_download_finished(self, info: dict) -> None:
        self.download_button.setEnabled(True)
        title = info.get('title', 'download')
        self.log(f'Finished: {title}')

    def on_download_failed(self, message: str) -> None:
        self.download_button.setEnabled(True)
        self.log(f'Error: {message}')


def run_gui() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
