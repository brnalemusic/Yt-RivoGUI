from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

try:
    from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer, QUrl
    from PySide6.QtGui import QIcon, QPixmap, QImage, QDesktopServices, QFont
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QComboBox,
        QCheckBox, QProgressBar, QFrame, QScrollArea, QButtonGroup, QRadioButton
    )
except ModuleNotFoundError as exc:  # pragma: no cover
    raise RuntimeError('PySide6 is required for the GUI runtime. Install it with: pip install PySide6') from exc

from app import __version__
from app.backend import YtDLBackend, DownloadOptions, ProgressInfo, get_default_download_dir, clean_ansi
from app.i18n import I18nManager

logger = logging.getLogger(__name__)


def get_logo_path() -> Path | None:
    """Finds the official Yt-RivoGUI-Logo.png across standard project locations."""
    candidates = [
        Path(__file__).resolve().parent / 'assets' / 'Yt-RivoGUI-Logo.png',
        Path(__file__).resolve().parent.parent / 'Yt-RivoGUI-Logo.png',
        Path.cwd() / 'Yt-RivoGUI-Logo.png',
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


class MetadataWorker(QThread):
    metadata_ready = Signal(dict, object)
    metadata_failed = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            backend = YtDLBackend()
            info = backend.extract_metadata(self.url)
            if self._is_cancelled:
                return

            pixmap = None
            thumb_url = info.get('thumbnail_url')
            if thumb_url:
                try:
                    req = Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urlopen(req, timeout=8) as response:
                        img_data = response.read()
                        image = QImage()
                        if image.loadFromData(img_data):
                            pixmap = QPixmap.fromImage(image)
                except Exception as thumb_err:
                    logger.debug('thumbnail preview fetch failed: %s', thumb_err)

            if not self._is_cancelled:
                self.metadata_ready.emit(info, pixmap)
        except Exception as exc:
            if not self._is_cancelled:
                self.metadata_failed.emit(str(exc))


class DownloadWorker(QThread):
    progress = Signal(object)
    finished = Signal(dict)
    failed = Signal(str)
    log = Signal(str)

    def __init__(self, url: str, options: DownloadOptions):
        super().__init__()
        self.url = url
        self.options = options
        self.backend = YtDLBackend(options.output_dir, verbose=True)

    def cancel(self):
        self.backend.cancel()

    def run(self):
        try:
            self.log.emit(f'> download iniciado: {self.url}')
            info = self.backend.download(
                url=self.url,
                options=self.options,
                progress_callback=self.progress.emit,
                log_callback=self.log.emit,
            )
            self.finished.emit(info)
        except Exception as exc:
            clean_err = clean_ansi(str(exc)).strip()
            self.failed.emit(clean_err or 'falha durante a execução do download')


MINIMAL_MONO_STYLESHEET = """
* {
    font-family: 'Cascadia Code', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
}

QMainWindow, QWidget#CentralWidget {
    background-color: #060809;
}

QScrollArea {
    background-color: transparent;
    border: none;
}
QScrollBar:vertical {
    background-color: #090D0B;
    width: 6px;
    border-radius: 3px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #16241D;
    min-height: 20px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background-color: #10B981;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* CARDS */
QFrame.Card {
    background-color: #0B0F0D;
    border: 1px solid #142019;
    border-radius: 8px;
}
QFrame.Card:hover {
    border-color: #1D3327;
}

/* INPUTS */
QLineEdit {
    background-color: #080C0A;
    color: #E2E8F0;
    border: 1px solid #15221B;
    border-radius: 6px;
    padding: 8px 12px;
    selection-background-color: #10B981;
    selection-color: #060B08;
}
QLineEdit:focus {
    border: 1px solid #10B981;
    background-color: #0B120E;
}

/* COMBOBOX */
QComboBox {
    background-color: #080C0A;
    color: #E2E8F0;
    border: 1px solid #15221B;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 18px;
}
QComboBox:hover {
    border-color: #213A2C;
}
QComboBox:focus {
    border-color: #10B981;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
}
QComboBox QAbstractItemView {
    background-color: #0B0F0D;
    color: #E2E8F0;
    border: 1px solid #1D3327;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #10B981;
    selection-color: #060B08;
}

/* BUTTONS */
QPushButton {
    background-color: #101713;
    color: #CBD5E1;
    border: 1px solid #1B2B22;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #16241D;
    border-color: #264233;
    color: #FFFFFF;
}
QPushButton:pressed {
    background-color: #0D1410;
}
QPushButton:disabled {
    background-color: #080C0A;
    color: #2C3E34;
    border-color: #121C16;
}

/* PRIMARY BUTTON (GREEN ACCENT) */
QPushButton#PrimaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #22C55E);
    color: #050A07;
    border: 1px solid #34D399;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: 700;
}
QPushButton#PrimaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #16A34A);
    border-color: #10B981;
    color: #FFFFFF;
}
QPushButton#PrimaryButton:pressed {
    background: #047857;
    color: #FFFFFF;
}
QPushButton#PrimaryButton:disabled {
    background: #0C1611;
    border-color: #14241B;
    color: #2B4737;
}

/* CANCEL BUTTON */
QPushButton#CancelButton {
    background-color: #1A0D10;
    color: #F87171;
    border: 1px solid #36171E;
    border-radius: 6px;
    padding: 10px 16px;
}
QPushButton#CancelButton:hover {
    background-color: #261116;
    border-color: #EF4444;
}

/* RADIO TABS (SEGMENTED) */
QRadioButton {
    color: #64748B;
    spacing: 6px;
    padding: 4px 8px;
    border-radius: 4px;
}
QRadioButton:hover {
    color: #CBD5E1;
}
QRadioButton:checked {
    color: #34D399;
    font-weight: 600;
    background-color: #0B1C13;
}
QRadioButton::indicator {
    width: 12px;
    height: 12px;
    border-radius: 6px;
    border: 1px solid #1C3325;
    background-color: #080C0A;
}
QRadioButton::indicator:checked {
    border-color: #10B981;
    background-color: #10B981;
}

/* CHECKBOX */
QCheckBox {
    color: #94A3B8;
    spacing: 8px;
}
QCheckBox:hover {
    color: #F1F5F9;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid #1A2D22;
    background-color: #080C0A;
}
QCheckBox::indicator:hover {
    border-color: #10B981;
}
QCheckBox::indicator:checked {
    border-color: #10B981;
    background-color: #10B981;
}

/* PROGRESS BAR */
QProgressBar {
    background-color: #080C0A;
    border: 1px solid #15221B;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #43F4B2);
    border-radius: 3px;
}

/* LOG VIEW */
QTextEdit#LogView {
    background-color: #040605;
    color: #34D399;
    border: 1px solid #102619;
    border-radius: 6px;
    padding: 8px;
    font-size: 11px;
    line-height: 1.4;
}

/* LABELS */
QLabel {
    color: #CBD5E1;
}
QLabel#AppTitle {
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: -0.5px;
}
QLabel#AppSubtitle {
    color: #10B981;
    font-size: 11px;
}
QLabel#SecondaryText {
    color: #64748B;
    font-size: 11px;
}
QLabel#MetricValue {
    color: #E2E8F0;
    font-size: 12px;
    font-weight: 600;
}
QLabel#MetricLabel {
    color: #475569;
    font-size: 10px;
}
QLabel#VersionBadge {
    background-color: #0A1C12;
    color: #34D399;
    border: 1px solid #10B981;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 10px;
    font-weight: 600;
}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.i18n = I18nManager()
        self.logo_path = get_logo_path()

        # Window configuration
        self.setWindowTitle(self.i18n('app_title'))
        self.resize(960, 720)
        self.setMinimumSize(820, 600)

        # Set taskbar and window icon
        if self.logo_path and self.logo_path.exists():
            app_icon = QIcon(str(self.logo_path))
            self.setWindowIcon(app_icon)
            QApplication.setWindowIcon(app_icon)

        # State variables
        self.output_dir = str(get_default_download_dir())
        self.download_thread: DownloadWorker | None = None
        self.metadata_thread: MetadataWorker | None = None
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._fetch_metadata)
        self.last_fetched_url = ''
        self.last_downloaded_file = ''

        self._build_ui()
        self.setStyleSheet(MINIMAL_MONO_STYLESHEET)
        self.apply_translations()

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        central_widget.setObjectName('CentralWidget')
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(10)

        # 1. HEADER BAR
        header_card = QFrame()
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(0, 0, 0, 4)
        header_layout.setSpacing(10)

        # Logo image
        self.logo_label = QLabel()
        if self.logo_path and self.logo_path.exists():
            pix = QPixmap(str(self.logo_path)).scaled(
                34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.logo_label.setPixmap(pix)
        else:
            self.logo_label.setText('▶')
            self.logo_label.setStyleSheet('font-size: 20px; color: #10B981;')
        header_layout.addWidget(self.logo_label)

        # App Title and Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self.app_title_label = QLabel(self.i18n('app_title'))
        self.app_title_label.setObjectName('AppTitle')
        title_row.addWidget(self.app_title_label)

        self.version_badge = QLabel(f'v{__version__}')
        self.version_badge.setObjectName('VersionBadge')
        title_row.addWidget(self.version_badge)
        title_row.addStretch()
        title_box.addLayout(title_row)

        self.app_subtitle_label = QLabel(self.i18n('app_subtitle'))
        self.app_subtitle_label.setObjectName('AppSubtitle')
        title_box.addWidget(self.app_subtitle_label)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Language selector in header
        lang_box = QHBoxLayout()
        lang_box.setSpacing(6)
        self.lang_label = QLabel(self.i18n('language_label'))
        self.lang_label.setObjectName('SecondaryText')
        lang_box.addWidget(self.lang_label)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem('pt-br', 'pt_BR')
        self.lang_combo.addItem('en-us', 'en_US')
        idx = 0 if self.i18n.current_lang == 'pt_BR' else 1
        self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_box.addWidget(self.lang_combo)
        header_layout.addLayout(lang_box)

        root_layout.addWidget(header_card)

        # SCROLL AREA FOR BODY
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        body_layout = QVBoxLayout(scroll_content)
        body_layout.setContentsMargins(0, 2, 6, 2)
        body_layout.setSpacing(10)

        # 2. URL & DESTINATION CARD
        url_card = QFrame()
        url_card.setProperty('class', 'Card')
        url_layout = QVBoxLayout(url_card)
        url_layout.setContentsMargins(12, 12, 12, 12)
        url_layout.setSpacing(8)

        # URL row
        url_input_row = QHBoxLayout()
        url_input_row.setSpacing(6)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(self.i18n('url_placeholder'))
        self.url_input.textChanged.connect(self._on_url_text_changed)
        url_input_row.addWidget(self.url_input)

        self.btn_paste = QPushButton(self.i18n('paste_button'))
        self.btn_paste.clicked.connect(self._paste_clipboard)
        url_input_row.addWidget(self.btn_paste)

        self.btn_clear = QPushButton(self.i18n('clear_button'))
        self.btn_clear.clicked.connect(self._clear_url)
        url_input_row.addWidget(self.btn_clear)
        url_layout.addLayout(url_input_row)

        # Destination Folder row
        dest_row = QHBoxLayout()
        dest_row.setSpacing(6)

        self.dest_label = QLabel(self.i18n('destination_folder'))
        self.dest_label.setObjectName('SecondaryText')
        dest_row.addWidget(self.dest_label)

        self.dest_path_input = QLineEdit(self.output_dir)
        self.dest_path_input.setReadOnly(True)
        dest_row.addWidget(self.dest_path_input)

        self.btn_browse = QPushButton(self.i18n('browse_folder'))
        self.btn_browse.clicked.connect(self._choose_output_dir)
        dest_row.addWidget(self.btn_browse)

        self.btn_open_folder = QPushButton(self.i18n('open_folder'))
        self.btn_open_folder.clicked.connect(self._open_output_dir)
        dest_row.addWidget(self.btn_open_folder)

        url_layout.addLayout(dest_row)
        body_layout.addWidget(url_card)

        # 3. PREVIEW CARD
        self.preview_card = QFrame()
        self.preview_card.setProperty('class', 'Card')
        preview_layout = QHBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        preview_layout.setSpacing(12)

        # Thumbnail Label
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(140, 78)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet('background-color: #08090E; border: 1px solid #1A1D29; border-radius: 6px;')
        self.thumb_label.setText('preview')
        preview_layout.addWidget(self.thumb_label)

        # Video Meta details
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(3)
        self.preview_title = QLabel(self.i18n('preview_empty'))
        self.preview_title.setWordWrap(True)
        self.preview_title.setStyleSheet('font-size: 12px; font-weight: 600; color: #F1F5F9;')
        meta_layout.addWidget(self.preview_title)

        meta_info_row = QHBoxLayout()
        meta_info_row.setSpacing(12)

        self.preview_channel = QLabel('')
        self.preview_channel.setObjectName('SecondaryText')
        meta_info_row.addWidget(self.preview_channel)

        self.preview_duration = QLabel('')
        self.preview_duration.setObjectName('SecondaryText')
        meta_info_row.addWidget(self.preview_duration)

        self.preview_playlist_badge = QLabel('')
        self.preview_playlist_badge.setStyleSheet('color: #34D399; font-weight: 500;')
        meta_info_row.addWidget(self.preview_playlist_badge)

        meta_info_row.addStretch()
        meta_layout.addLayout(meta_info_row)
        preview_layout.addLayout(meta_layout)
        body_layout.addWidget(self.preview_card)

        # 4. DOWNLOAD OPTIONS CARD
        options_card = QFrame()
        options_card.setProperty('class', 'Card')
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(12, 12, 12, 12)
        options_layout.setSpacing(10)

        # Mode Selection Row (Segmented Radio)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.mode_group = QButtonGroup(self)

        self.radio_video = QRadioButton(self.i18n('mode_video'))
        self.radio_video.setChecked(True)
        self.mode_group.addButton(self.radio_video, 0)
        mode_row.addWidget(self.radio_video)

        self.radio_audio = QRadioButton(self.i18n('mode_audio'))
        self.mode_group.addButton(self.radio_audio, 1)
        mode_row.addWidget(self.radio_audio)

        self.radio_thumbnail = QRadioButton(self.i18n('mode_thumbnail'))
        self.mode_group.addButton(self.radio_thumbnail, 2)
        mode_row.addWidget(self.radio_thumbnail)

        mode_row.addStretch()
        options_layout.addLayout(mode_row)
        self.mode_group.idToggled.connect(self._on_mode_changed)

        # Grid of Format & Quality options
        self.settings_grid = QGridLayout()
        self.settings_grid.setHorizontalSpacing(12)
        self.settings_grid.setVerticalSpacing(8)

        # Video Quality & Format Controls
        self.quality_label = QLabel(self.i18n('quality_label'))
        self.quality_combo = QComboBox()
        self.quality_combo.addItem(self.i18n('quality_best'), 'best')
        self.quality_combo.addItem(self.i18n('quality_2160p'), '2160p')
        self.quality_combo.addItem(self.i18n('quality_1440p'), '1440p')
        self.quality_combo.addItem(self.i18n('quality_1080p'), '1080p')
        self.quality_combo.addItem(self.i18n('quality_720p'), '720p')
        self.quality_combo.addItem(self.i18n('quality_480p'), '480p')
        self.quality_combo.addItem(self.i18n('quality_360p'), '360p')

        self.format_label = QLabel(self.i18n('format_label'))
        self.format_combo = QComboBox()
        self.format_combo.addItem('mp4', 'mp4')
        self.format_combo.addItem('mkv', 'mkv')

        # Audio Format & Quality Controls
        self.audio_format_label = QLabel(self.i18n('audio_format_label'))
        self.audio_format_combo = QComboBox()
        self.audio_format_combo.addItem('mp3', 'mp3')
        self.audio_format_combo.addItem('m4a', 'm4a')
        self.audio_format_combo.addItem('flac', 'flac')
        self.audio_format_combo.addItem('wav', 'wav')
        self.audio_format_combo.addItem('opus', 'opus')

        self.audio_quality_label = QLabel(self.i18n('audio_quality_label'))
        self.audio_quality_combo = QComboBox()
        self.audio_quality_combo.addItem(self.i18n('audio_quality_best'), 'best')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_320'), '320')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_256'), '256')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_192'), '192')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_128'), '128')

        # Add to Grid
        self.settings_grid.addWidget(self.quality_label, 0, 0)
        self.settings_grid.addWidget(self.quality_combo, 0, 1)
        self.settings_grid.addWidget(self.format_label, 0, 2)
        self.settings_grid.addWidget(self.format_combo, 0, 3)

        self.settings_grid.addWidget(self.audio_format_label, 1, 0)
        self.settings_grid.addWidget(self.audio_format_combo, 1, 1)
        self.settings_grid.addWidget(self.audio_quality_label, 1, 2)
        self.settings_grid.addWidget(self.audio_quality_combo, 1, 3)

        options_layout.addLayout(self.settings_grid)

        # Checkbox Row 1: Embeds
        check_row_1 = QHBoxLayout()
        check_row_1.setSpacing(16)
        self.chk_embed_thumb = QCheckBox(self.i18n('opt_embed_thumbnail'))
        self.chk_embed_thumb.setChecked(True)
        check_row_1.addWidget(self.chk_embed_thumb)

        self.chk_embed_meta = QCheckBox(self.i18n('opt_embed_metadata'))
        self.chk_embed_meta.setChecked(True)
        check_row_1.addWidget(self.chk_embed_meta)
        check_row_1.addStretch()
        options_layout.addLayout(check_row_1)

        # Checkbox Row 2: Subtitles
        check_row_2 = QHBoxLayout()
        check_row_2.setSpacing(10)
        self.chk_subtitles = QCheckBox(self.i18n('opt_subtitles'))
        self.chk_subtitles.setChecked(False)
        self.chk_subtitles.toggled.connect(self._on_subtitles_toggled)
        check_row_2.addWidget(self.chk_subtitles)

        self.sub_lang_label = QLabel(self.i18n('sub_lang_label'))
        self.sub_lang_label.setObjectName('SecondaryText')
        check_row_2.addWidget(self.sub_lang_label)

        self.sub_lang_combo = QComboBox()
        self.sub_lang_combo.addItem(self.i18n('sub_lang_pt'), 'pt')
        self.sub_lang_combo.addItem(self.i18n('sub_lang_en'), 'en')
        self.sub_lang_combo.addItem(self.i18n('sub_lang_all'), 'all')
        self.sub_lang_combo.setEnabled(False)
        check_row_2.addWidget(self.sub_lang_combo)
        check_row_2.addStretch()
        options_layout.addLayout(check_row_2)

        # Checkbox Row 3: Playlist Option
        check_row_3 = QVBoxLayout()
        check_row_3.setSpacing(2)
        self.chk_playlist = QCheckBox(self.i18n('opt_playlist'))
        self.chk_playlist.setChecked(False)
        check_row_3.addWidget(self.chk_playlist)

        self.playlist_tip = QLabel(self.i18n('playlist_notice'))
        self.playlist_tip.setStyleSheet('color: #64748B; font-size: 10px; margin-left: 22px;')
        check_row_3.addWidget(self.playlist_tip)
        options_layout.addLayout(check_row_3)

        body_layout.addWidget(options_card)

        # 5. PROGRESS & ACTIONS CARD
        progress_card = QFrame()
        progress_card.setProperty('class', 'Card')
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(12, 12, 12, 12)
        progress_layout.setSpacing(10)

        # Status Label and Action Buttons
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.status_dot = QLabel('●')
        self.status_dot.setStyleSheet('color: #10B981; font-size: 13px;')
        action_row.addWidget(self.status_dot)

        self.status_label = QLabel(self.i18n('status_ready'))
        self.status_label.setStyleSheet('font-size: 12px; font-weight: 500; color: #E2E8F0;')
        action_row.addWidget(self.status_label)
        action_row.addStretch()

        self.btn_open_file = QPushButton(self.i18n('open_file'))
        self.btn_open_file.setVisible(False)
        self.btn_open_file.clicked.connect(self._open_downloaded_file)
        action_row.addWidget(self.btn_open_file)

        self.btn_cancel = QPushButton(self.i18n('btn_cancel'))
        self.btn_cancel.setObjectName('CancelButton')
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_download)
        action_row.addWidget(self.btn_cancel)

        self.btn_download = QPushButton(self.i18n('btn_download'))
        self.btn_download.setObjectName('PrimaryButton')
        self.btn_download.clicked.connect(self._start_download)
        action_row.addWidget(self.btn_download)

        progress_layout.addLayout(action_row)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        # Metrics Row
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(8)

        # Percentage
        self.pct_box = self._create_metric_widget(self.i18n('status_downloading'), '0%')
        metrics_row.addWidget(self.pct_box)

        # Speed
        self.speed_box = self._create_metric_widget(self.i18n('speed_label'), '--')
        metrics_row.addWidget(self.speed_box)

        # ETA
        self.eta_box = self._create_metric_widget(self.i18n('eta_label'), '--:--')
        metrics_row.addWidget(self.eta_box)

        # Size
        self.size_box = self._create_metric_widget(self.i18n('size_label'), '0 mb / 0 mb')
        metrics_row.addWidget(self.size_box)

        progress_layout.addLayout(metrics_row)
        body_layout.addWidget(progress_card)

        # 6. LOGS (COLLAPSIBLE)
        log_header_layout = QHBoxLayout()
        self.btn_toggle_logs = QPushButton(self.i18n('toggle_logs_show'))
        self.btn_toggle_logs.setStyleSheet('border: none; background: transparent; color: #10B981; text-align: left; font-size: 11px;')
        self.btn_toggle_logs.clicked.connect(self._toggle_logs)
        log_header_layout.addWidget(self.btn_toggle_logs)
        log_header_layout.addStretch()
        body_layout.addLayout(log_header_layout)

        self.log_view = QTextEdit()
        self.log_view.setObjectName('LogView')
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(130)
        self.log_view.setVisible(False)
        body_layout.addWidget(self.log_view)

        scroll_area.setWidget(scroll_content)
        root_layout.addWidget(scroll_area)

        self._update_controls_visibility()

    def _create_metric_widget(self, label_text: str, default_val: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet('background-color: #08090E; border: 1px solid #141722; border-radius: 4px; padding: 2px 6px;')
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(1)

        lbl = QLabel(label_text.lower())
        lbl.setObjectName('MetricLabel')
        layout.addWidget(lbl)

        val = QLabel(default_val.lower())
        val.setObjectName('MetricValue')
        layout.addWidget(val)

        frame.label_widget = lbl
        frame.val_widget = val
        return frame

    def apply_translations(self) -> None:
        """Updates all strings according to current language (all lowercase)."""
        self.setWindowTitle(self.i18n('app_title').lower())
        self.app_title_label.setText(self.i18n('app_title').lower())
        self.app_subtitle_label.setText(self.i18n('app_subtitle').lower())
        self.version_badge.setText(f'v{__version__}')
        self.lang_label.setText(self.i18n('language_label').lower())

        self.url_input.setPlaceholderText(self.i18n('url_placeholder').lower())
        self.btn_paste.setText(self.i18n('paste_button').lower())
        self.btn_clear.setText(self.i18n('clear_button').lower())
        self.dest_label.setText(self.i18n('destination_folder').lower())
        self.btn_browse.setText(self.i18n('browse_folder').lower())
        self.btn_open_folder.setText(self.i18n('open_folder').lower())

        self.radio_video.setText(self.i18n('mode_video').lower())
        self.radio_audio.setText(self.i18n('mode_audio').lower())
        self.radio_thumbnail.setText(self.i18n('mode_thumbnail').lower())

        self.quality_label.setText(self.i18n('quality_label').lower())
        self.format_label.setText(self.i18n('format_label').lower())
        self.audio_format_label.setText(self.i18n('audio_format_label').lower())
        self.audio_quality_label.setText(self.i18n('audio_quality_label').lower())

        self.chk_embed_thumb.setText(self.i18n('opt_embed_thumbnail').lower())
        self.chk_embed_meta.setText(self.i18n('opt_embed_metadata').lower())
        self.chk_subtitles.setText(self.i18n('opt_subtitles').lower())
        self.sub_lang_label.setText(self.i18n('sub_lang_label').lower())
        self.chk_playlist.setText(self.i18n('opt_playlist').lower())
        self.playlist_tip.setText(self.i18n('playlist_notice').lower())

        self.btn_download.setText(self.i18n('btn_download').lower())
        self.btn_cancel.setText(self.i18n('btn_cancel').lower())
        self.btn_open_file.setText(self.i18n('open_file').lower())

        self.pct_box.label_widget.setText(self.i18n('status_downloading').lower())
        self.speed_box.label_widget.setText(self.i18n('speed_label').lower())
        self.eta_box.label_widget.setText(self.i18n('eta_label').lower())
        self.size_box.label_widget.setText(self.i18n('size_label').lower())

        if self.log_view.isVisible():
            self.btn_toggle_logs.setText(self.i18n('toggle_logs_hide').lower())
        else:
            self.btn_toggle_logs.setText(self.i18n('toggle_logs_show').lower())

        # Update quality combo text
        cur_q = self.quality_combo.currentData()
        self.quality_combo.clear()
        self.quality_combo.addItem(self.i18n('quality_best').lower(), 'best')
        self.quality_combo.addItem(self.i18n('quality_2160p').lower(), '2160p')
        self.quality_combo.addItem(self.i18n('quality_1440p').lower(), '1440p')
        self.quality_combo.addItem(self.i18n('quality_1080p').lower(), '1080p')
        self.quality_combo.addItem(self.i18n('quality_720p').lower(), '720p')
        self.quality_combo.addItem(self.i18n('quality_480p').lower(), '480p')
        self.quality_combo.addItem(self.i18n('quality_360p').lower(), '360p')
        idx = self.quality_combo.findData(cur_q)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)

        # Update audio quality combo text
        cur_aq = self.audio_quality_combo.currentData()
        self.audio_quality_combo.clear()
        self.audio_quality_combo.addItem(self.i18n('audio_quality_best').lower(), 'best')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_320').lower(), '320')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_256').lower(), '256')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_192').lower(), '192')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_128').lower(), '128')
        idx = self.audio_quality_combo.findData(cur_aq)
        if idx >= 0:
            self.audio_quality_combo.setCurrentIndex(idx)

        # Update subtitle lang combo text
        cur_sl = self.sub_lang_combo.currentData()
        self.sub_lang_combo.clear()
        self.sub_lang_combo.addItem(self.i18n('sub_lang_pt').lower(), 'pt')
        self.sub_lang_combo.addItem(self.i18n('sub_lang_en').lower(), 'en')
        self.sub_lang_combo.addItem(self.i18n('sub_lang_all').lower(), 'all')
        idx = self.sub_lang_combo.findData(cur_sl)
        if idx >= 0:
            self.sub_lang_combo.setCurrentIndex(idx)

    def _on_language_changed(self, index: int) -> None:
        lang_code = self.lang_combo.itemData(index)
        self.i18n.set_language(lang_code)
        self.apply_translations()

    def _on_mode_changed(self) -> None:
        self._update_controls_visibility()

    def _update_controls_visibility(self) -> None:
        is_video = self.radio_video.isChecked()
        is_audio = self.radio_audio.isChecked()
        is_thumb = self.radio_thumbnail.isChecked()

        self.quality_label.setVisible(is_video)
        self.quality_combo.setVisible(is_video)
        self.format_label.setVisible(is_video)
        self.format_combo.setVisible(is_video)

        self.audio_format_label.setVisible(is_audio)
        self.audio_format_combo.setVisible(is_audio)
        self.audio_quality_label.setVisible(is_audio)
        self.audio_quality_combo.setVisible(is_audio)

        self.chk_embed_thumb.setVisible(not is_thumb)
        self.chk_embed_meta.setVisible(not is_thumb)
        self.chk_subtitles.setVisible(is_video)
        self.sub_lang_label.setVisible(is_video)
        self.sub_lang_combo.setVisible(is_video)

    def _on_subtitles_toggled(self, checked: bool) -> None:
        self.sub_lang_combo.setEnabled(checked)

    def _on_url_text_changed(self, text: str) -> None:
        url = text.strip()
        if not url or not (url.startswith('http://') or url.startswith('https://')):
            self.debounce_timer.stop()
            if not url:
                self.preview_title.setText(self.i18n('preview_empty').lower())
                self.preview_channel.setText('')
                self.preview_duration.setText('')
                self.preview_playlist_badge.setText('')
                self.thumb_label.setPixmap(QPixmap())
                self.thumb_label.setText('preview')
            return

        if url != self.last_fetched_url:
            self.debounce_timer.stop()
            self.debounce_timer.start(500)

    def _fetch_metadata(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return

        self.last_fetched_url = url
        self.preview_title.setText(self.i18n('preview_loading').lower())
        self.preview_channel.setText('')
        self.preview_duration.setText('')
        self.preview_playlist_badge.setText('')

        if self.metadata_thread and self.metadata_thread.isRunning():
            self.metadata_thread.cancel()
            self.metadata_thread.wait(200)

        self.metadata_thread = MetadataWorker(url)
        self.metadata_thread.metadata_ready.connect(self._on_metadata_ready)
        self.metadata_thread.metadata_failed.connect(self._on_metadata_failed)
        self.metadata_thread.start()

    @Slot(dict, object)
    def _on_metadata_ready(self, info: dict, pixmap: QPixmap | None) -> None:
        self.preview_title.setText(info.get('title', ''))
        uploader = info.get('uploader', '')
        if uploader:
            self.preview_channel.setText(f'canal: {uploader}')

        dur = info.get('duration_str', '')
        if dur and dur != '--:--':
            self.preview_duration.setText(f'tempo: {dur}')

        if info.get('is_playlist'):
            count = info.get('playlist_count', 0)
            self.preview_playlist_badge.setText(f'playlist: {count} itens' if count else 'playlist')
            self.chk_playlist.setChecked(True)
        else:
            self.preview_playlist_badge.setText('')

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                140, 78, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
            self.thumb_label.setPixmap(scaled)
            self.thumb_label.setText('')
        else:
            self.thumb_label.setPixmap(QPixmap())
            self.thumb_label.setText('preview')

        self.status_label.setText(self.i18n('preview_ready').lower())
        self.status_dot.setStyleSheet('color: #10B981; font-size: 13px;')

    @Slot(str)
    def _on_metadata_failed(self, error: str) -> None:
        self.preview_title.setText(self.i18n('preview_error').lower())
        self.log(f'[aviso preview] {clean_ansi(error)}')

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if text:
            self.url_input.setText(text.strip())

    def _clear_url(self) -> None:
        self.url_input.clear()
        self.last_fetched_url = ''
        self.preview_title.setText(self.i18n('preview_empty').lower())
        self.preview_channel.setText('')
        self.preview_duration.setText('')
        self.preview_playlist_badge.setText('')
        self.thumb_label.setPixmap(QPixmap())
        self.thumb_label.setText('preview')

    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, self.i18n('browse_folder').lower(), self.output_dir)
        if directory:
            self.output_dir = directory
            self.dest_path_input.setText(directory)
            self.log(f'> pasta de saída: {directory}')

    def _open_output_dir(self) -> None:
        folder = Path(self.output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _open_downloaded_file(self) -> None:
        if self.last_downloaded_file and Path(self.last_downloaded_file).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_downloaded_file)))
        else:
            self._open_output_dir()

    def _toggle_logs(self) -> None:
        is_visible = not self.log_view.isVisible()
        self.log_view.setVisible(is_visible)
        self.btn_toggle_logs.setText(self.i18n('toggle_logs_hide').lower() if is_visible else self.i18n('toggle_logs_show').lower())

    def log(self, message: str) -> None:
        clean = clean_ansi(message)
        self.log_view.append(clean)

    def _start_download(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText(self.i18n('alert_no_url').lower())
            self.status_dot.setStyleSheet('color: #EF4444; font-size: 13px;')
            return

        if self.download_thread and self.download_thread.isRunning():
            self.status_label.setText(self.i18n('alert_already_running').lower())
            return

        # Prepare Options
        options = DownloadOptions()
        options.output_dir = self.output_dir

        if self.radio_audio.isChecked():
            options.mode = 'audio'
            options.audio_format = self.audio_format_combo.currentData()
            options.audio_quality = self.audio_quality_combo.currentData()
        elif self.radio_thumbnail.isChecked():
            options.mode = 'thumbnail_only'
        else:
            options.mode = 'video'
            options.video_quality = self.quality_combo.currentData()
            options.video_format = self.format_combo.currentData()
            options.download_subs = self.chk_subtitles.isChecked()
            options.sub_lang = self.sub_lang_combo.currentData()

        options.embed_thumbnail = self.chk_embed_thumb.isChecked()
        options.embed_metadata = self.chk_embed_meta.isChecked()
        options.is_playlist = self.chk_playlist.isChecked()

        # UI state during download
        self.btn_download.setEnabled(False)
        self.btn_download.setText(self.i18n('btn_downloading').lower())
        self.btn_cancel.setEnabled(True)
        self.btn_open_file.setVisible(False)
        self.progress_bar.setValue(0)
        self.status_label.setText(self.i18n('status_connecting').lower())
        self.status_dot.setStyleSheet('color: #10B981; font-size: 13px;')

        self.pct_box.val_widget.setText('0%')
        self.speed_box.val_widget.setText('--')
        self.eta_box.val_widget.setText('--:--')
        self.size_box.val_widget.setText('0 mb / 0 mb')

        self.download_thread = DownloadWorker(url, options)
        self.download_thread.log.connect(self.log)
        self.download_thread.progress.connect(self._on_download_progress)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.failed.connect(self._on_download_failed)
        self.download_thread.start()

    def _cancel_download(self) -> None:
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.cancel()
            self.status_label.setText(self.i18n('status_cancelled').lower())
            self.status_dot.setStyleSheet('color: #F59E0B; font-size: 13px;')
            self.btn_cancel.setEnabled(False)
            self.btn_download.setEnabled(True)
            self.btn_download.setText(self.i18n('btn_download').lower())

    @Slot(object)
    def _on_download_progress(self, info: ProgressInfo) -> None:
        pct = int(info.percent)
        self.progress_bar.setValue(pct)
        self.pct_box.val_widget.setText(f'{pct}%')
        self.speed_box.val_widget.setText(info.speed_str.lower())
        self.eta_box.val_widget.setText(info.eta_str)
        self.size_box.val_widget.setText(f'{info.downloaded_str.lower()} / {info.total_str.lower()}')

        if info.status == 'processing':
            self.status_label.setText(self.i18n('status_processing').lower())
            self.status_dot.setStyleSheet('color: #F59E0B; font-size: 13px;')
        else:
            self.status_label.setText(self.i18n('status_downloading').lower())
            self.status_dot.setStyleSheet('color: #10B981; font-size: 13px;')

    @Slot(dict)
    def _on_download_finished(self, info: dict) -> None:
        self.btn_download.setEnabled(True)
        self.btn_download.setText(self.i18n('btn_download').lower())
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(100)
        self.pct_box.val_widget.setText('100%')
        self.status_label.setText(self.i18n('status_finished').lower())
        self.status_dot.setStyleSheet('color: #10B981; font-size: 13px;')

        filename = info.get('_filename') or info.get('filename')
        if filename and Path(filename).exists():
            self.last_downloaded_file = str(filename)
            self.btn_open_file.setVisible(True)

        title = info.get('title', 'arquivo')
        self.log(f'✔ concluído com sucesso: {title}')

    @Slot(str)
    def _on_download_failed(self, error: str) -> None:
        self.btn_download.setEnabled(True)
        self.btn_download.setText(self.i18n('btn_download').lower())
        self.btn_cancel.setEnabled(False)
        self.status_label.setText(self.i18n('status_failed').lower())
        self.status_dot.setStyleSheet('color: #EF4444; font-size: 13px;')
        self.log(f'✖ erro: {error}')


def run_gui() -> int:
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ytrivo.desktop.gui.1.2')
        except Exception:
            pass

    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
