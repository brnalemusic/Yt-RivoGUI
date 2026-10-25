from __future__ import annotations

import logging
import os
import re
import sys
import threading
from pathlib import Path
from urllib.request import Request, urlopen

try:
    from PySide6.QtCore import (
        Qt, QThread, Signal, Slot, QTimer, QUrl, QPoint,
        QPropertyAnimation, QEasingCurve,
    )
    from PySide6.QtGui import (
        QIcon, QPixmap, QImage, QDesktopServices, QColor, QFontMetrics,
    )
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QComboBox,
        QCheckBox, QProgressBar, QFrame, QScrollArea, QButtonGroup, QRadioButton,
        QMessageBox, QStackedWidget, QGraphicsDropShadowEffect,
    )
except ModuleNotFoundError as exc:  # pragma: no cover
    raise RuntimeError('PySide6 is required for the GUI runtime. Install it with: pip install PySide6') from exc

from app import __version__
from app.backend import YtDLBackend, DownloadOptions, ProgressInfo, get_default_download_dir, clean_ansi
from app.i18n import I18nManager
from app.styles import MINIMAL_MONO_STYLESHEET  # noqa: F401  (re-exported for compatibility)
from app.updater import (
    RELEASES_URL,
    CheckResult,
    SingleInstanceGuard,
    UpdateCancelled,
    UpdateError,
    UpdateSettings,
    apply_update,
    check_for_updates,
    cleanup_update_cache,
    download_asset,
    is_frozen,
    is_running_installed,
)

logger = logging.getLogger(__name__)

# Guided-flow phases rendered inside the main stack.
PHASE_HOME = 0       # hero: paste a link
PHASE_CONFIGURE = 1  # detected media + accordion settings
PHASE_PROGRESS = 2   # download progress & logs

_QWIDGETSIZE_MAX = 16777215


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


def _repolish(widget: QWidget) -> None:
    """Forces a Qt stylesheet re-evaluation after an objectName/property change."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


class _SectionHead(QFrame):
    """Clickable accordion header that emits ``clicked`` on left-click release."""

    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        event.accept()


class _DrawerOverlay(QFrame):
    """Full-window translucent surface behind the drawer; clicking it closes the drawer."""

    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.clicked.emit()
        event.accept()


class CollapsibleSection(QFrame):
    """Accordion section: a clickable summary header that expands a settings area.

    The header always shows the current value of the section (the "summary"),
    so the interface stays compact when the smart defaults are enough and only
    expands when the user wants to customize something.
    """

    def __init__(self, title: str, summary: str = '', parent=None):
        super().__init__(parent)
        self.setObjectName('SectionCard')

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = _SectionHead()
        self.header.setObjectName('SectionHead')
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.clicked.connect(self.toggle)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 9, 12, 9)
        header_layout.setSpacing(8)

        self.arrow_label = QLabel('▸')
        self.arrow_label.setObjectName('SectionArrow')
        self.title_label = QLabel(title)
        self.title_label.setObjectName('SectionName')
        self.summary_label = QLabel(summary)
        self.summary_label.setObjectName('SectionValue')

        for lbl in (self.arrow_label, self.title_label, self.summary_label):
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        header_layout.addWidget(self.arrow_label)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.summary_label)
        outer.addWidget(self.header)

        self.content = QWidget()
        self.content.setObjectName('SectionContent')
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(14, 2, 14, 12)
        self.content_layout.setSpacing(8)
        self.content.setMaximumHeight(0)
        self.content.setVisible(False)
        outer.addWidget(self.content)

        self._expanded = False
        self._animation = QPropertyAnimation(self.content, b'maximumHeight', self)
        self._animation.setDuration(170)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._on_animation_finished)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expand: bool) -> None:
        if expand == self._expanded:
            return
        self._expanded = expand
        self.arrow_label.setText('▾' if expand else '▸')
        self._animation.stop()
        if expand:
            self.content.setVisible(True)
            self._animation.setStartValue(0)
            self._animation.setEndValue(self._content_height())
        else:
            self._animation.setStartValue(self.content.height())
            self._animation.setEndValue(0)
        self._animation.start()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_summary(self, summary: str) -> None:
        self.summary_label.setText(summary)

    def _content_height(self) -> int:
        margins = self.content_layout.contentsMargins()
        return self.content_layout.sizeHint().height() + margins.top() + margins.bottom()

    def _on_animation_finished(self) -> None:
        if self._expanded:
            self.content.setMaximumHeight(_QWIDGETSIZE_MAX)
        else:
            self.content.setVisible(False)


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


class UpdateCheckWorker(QThread):
    """Checks the stable release channel without blocking the UI."""

    checked = Signal(object)

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version

    def run(self) -> None:
        try:
            result = check_for_updates(self.current_version)
        except Exception as exc:  # defensive: never kill a QThread silently
            logger.debug('update check failed', exc_info=True)
            result = CheckResult(
                status='error',
                current_version=self.current_version,
                error_code='unknown',
                error=str(exc),
            )
        self.checked.emit(result)


class UpdateDownloadWorker(QThread):
    """Downloads and verifies an update asset."""

    progress = Signal(int, int)
    downloaded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, asset):
        super().__init__()
        self.asset = asset
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            path = download_asset(
                self.asset,
                progress=self.progress.emit,
                cancel=self.cancel_event,
            )
        except UpdateCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:
            logger.debug('update download failed', exc_info=True)
            self.failed.emit(str(exc))
            return
        self.downloaded.emit(str(path))


class MainWindow(QMainWindow):
    def __init__(self, *, allow_update_check: bool = True) -> None:
        super().__init__()
        self.i18n = I18nManager()
        self.logo_path = get_logo_path()

        # Window configuration
        self.setWindowTitle(self.i18n('app_title'))
        self.resize(940, 700)
        self.setMinimumSize(840, 620)

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
        self._phase = PHASE_HOME
        self._playlist_count = 0

        # Update state
        self._allow_update_check = allow_update_check
        self.update_settings = UpdateSettings.load()
        self.update_check_thread: UpdateCheckWorker | None = None
        self.update_download_thread: UpdateDownloadWorker | None = None
        self._update_manual_check = False
        self._update_state = 'hidden'
        self._update_info = None
        self._update_asset = None
        self._update_path: Path | None = None
        self._update_error_code: str | None = None
        self._update_progress_value = 0
        self._update_progress_text = ''

        self.setAcceptDrops(True)
        self._build_ui()
        self.setStyleSheet(MINIMAL_MONO_STYLESHEET)
        self._set_phase(PHASE_HOME)
        self.apply_translations()

        # Convenience: when the app opens, a media link already sitting on the
        # clipboard is detected and prefilled. Guarded so it never runs while
        # the window is hidden (e.g. during offscreen tests).
        QTimer.singleShot(500, self._prefill_from_clipboard)

        self.auto_update_timer = QTimer(self)
        self.auto_update_timer.setInterval(12 * 60 * 60 * 1000)
        self.auto_update_timer.timeout.connect(self._maybe_auto_update_check)
        if self._allow_update_check:
            self.auto_update_timer.start()
            QTimer.singleShot(2500, self._maybe_auto_update_check)

    # ------------------------------------------------------------------
    # ui construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        central_widget.setObjectName('CentralWidget')
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(14, 10, 14, 12)
        root_layout.setSpacing(8)

        self._build_header(root_layout)
        self._build_update_banner(root_layout)
        self._build_stepper(root_layout)
        self._build_stack(root_layout)
        self._build_drawer()
        self._update_controls_visibility()

    def _build_header(self, root_layout: QVBoxLayout) -> None:
        header_card = QFrame()
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(0, 0, 0, 2)
        header_layout.setSpacing(10)

        # Hamburger that opens the preferences/actions drawer
        self.btn_menu = QPushButton('☰')
        self.btn_menu.setObjectName('MenuButton')
        self.btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_menu.clicked.connect(self._toggle_drawer)
        header_layout.addWidget(self.btn_menu)

        # Brand block
        self.logo_label = QLabel()
        if self.logo_path and self.logo_path.exists():
            pix = QPixmap(str(self.logo_path)).scaled(
                28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.logo_label.setPixmap(pix)
        else:
            self.logo_label.setText('▶')
            self.logo_label.setStyleSheet('font-size: 18px; color: #34d399;')
        header_layout.addWidget(self.logo_label)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self.app_title_label = QLabel(self.i18n('app_title').lower())
        self.app_title_label.setObjectName('AppTitle')
        title_row.addWidget(self.app_title_label)

        self.version_badge = QPushButton(f'v{__version__}')
        self.version_badge.setObjectName('VersionBadge')
        self.version_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_badge.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.version_badge.clicked.connect(self._manual_update_check)
        title_row.addWidget(self.version_badge)
        title_row.addStretch()
        header_layout.addLayout(title_row)

        header_layout.addStretch(1)
        root_layout.addWidget(header_card)

    def _build_update_banner(self, root_layout: QVBoxLayout) -> None:
        self.update_banner = QFrame()
        self.update_banner.setObjectName('UpdateBanner')
        update_layout = QVBoxLayout(self.update_banner)
        update_layout.setContentsMargins(14, 11, 14, 11)
        update_layout.setSpacing(7)

        update_top_row = QHBoxLayout()
        update_top_row.setSpacing(8)
        update_text_box = QVBoxLayout()
        update_text_box.setSpacing(2)
        self.update_title = QLabel('')
        self.update_title.setObjectName('UpdateTitle')
        update_text_box.addWidget(self.update_title)
        self.update_detail = QLabel('')
        self.update_detail.setObjectName('UpdateDetail')
        self.update_detail.setWordWrap(True)
        update_text_box.addWidget(self.update_detail)
        update_top_row.addLayout(update_text_box, 1)

        self.update_notes_btn = QPushButton('')
        self.update_notes_btn.setObjectName('UpdateGhost')
        self.update_notes_btn.clicked.connect(self._open_update_notes)
        update_top_row.addWidget(self.update_notes_btn)

        self.update_skip_btn = QPushButton('')
        self.update_skip_btn.setObjectName('UpdateGhost')
        self.update_skip_btn.clicked.connect(self._skip_update_version)
        update_top_row.addWidget(self.update_skip_btn)

        self.update_later_btn = QPushButton('')
        self.update_later_btn.setObjectName('UpdateGhost')
        self.update_later_btn.clicked.connect(self._hide_update_banner)
        update_top_row.addWidget(self.update_later_btn)

        self.update_install_btn = QPushButton('')
        self.update_install_btn.setObjectName('PrimaryButton')
        self.update_install_btn.clicked.connect(self._on_update_install_clicked)
        update_top_row.addWidget(self.update_install_btn)

        update_layout.addLayout(update_top_row)

        update_progress_row = QHBoxLayout()
        update_progress_row.setSpacing(8)
        self.update_progress = QProgressBar()
        self.update_progress.setObjectName('UpdateProgress')
        self.update_progress.setRange(0, 100)
        self.update_progress.setValue(0)
        update_progress_row.addWidget(self.update_progress, 1)
        self.update_cancel_btn = QPushButton('')
        self.update_cancel_btn.setObjectName('UpdateGhost')
        self.update_cancel_btn.clicked.connect(self._cancel_update_download)
        update_progress_row.addWidget(self.update_cancel_btn)
        update_layout.addLayout(update_progress_row)

        self.update_banner.setVisible(False)
        root_layout.addWidget(self.update_banner)

    def _build_stepper(self, root_layout: QVBoxLayout) -> None:
        """Thin guided-flow indicator: 1 link · 2 ajustes · 3 download."""
        self.stepper_row = QWidget()
        row = QHBoxLayout(self.stepper_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.step_dots: list[QLabel] = []
        self.step_texts: list[QLabel] = []
        for index in range(3):
            dot = QLabel('○')
            dot.setObjectName('StepDot')
            text = QLabel('')
            text.setObjectName('StepText')
            self.step_dots.append(dot)
            self.step_texts.append(text)
            row.addWidget(dot)
            row.addWidget(text)
            if index < 2:
                line = QFrame()
                line.setObjectName('StepLine')
                line.setFixedSize(26, 1)
                row.addWidget(line)

        row.addStretch(1)
        row.insertStretch(0, 1)
        self.stepper_row.setVisible(False)
        root_layout.addWidget(self.stepper_row)

    def _build_stack(self, root_layout: QVBoxLayout) -> None:
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_home_page())       # PHASE_HOME
        self.stack.addWidget(self._build_configure_page())  # PHASE_CONFIGURE
        self.stack.addWidget(self._build_progress_page())   # PHASE_PROGRESS
        root_layout.addWidget(self.stack, 1)

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName('PageHome')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 20, 28, 16)
        layout.setSpacing(10)

        layout.addStretch(2)

        # Hero brand block
        hero_box = QVBoxLayout()
        hero_box.setSpacing(4)
        hero_logo = QLabel()
        hero_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self.logo_path and self.logo_path.exists():
            hero_logo.setPixmap(QPixmap(str(self.logo_path)).scaled(
                48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))
        else:
            hero_logo.setText('▶')
            hero_logo.setStyleSheet('font-size: 26px; color: #34d399;')
        hero_box.addWidget(hero_logo)

        self.hero_title_label = QLabel('')
        self.hero_title_label.setObjectName('HeroTitle')
        self.hero_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_box.addWidget(self.hero_title_label)

        self.app_subtitle_label = QLabel('')
        self.app_subtitle_label.setObjectName('AppSubtitle')
        self.app_subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_box.addWidget(self.app_subtitle_label)
        layout.addLayout(hero_box)

        layout.addSpacing(14)

        # One big paste button + one text box: the entire home screen.
        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setObjectName('UrlInput')
        self.url_input.setPlaceholderText('🔗 ' + self.i18n('url_placeholder').lower())
        self.url_input.setClearButtonEnabled(True)
        self.url_input.textChanged.connect(self._on_url_text_changed)
        self.url_input.returnPressed.connect(self._fetch_metadata_now)
        url_row.addWidget(self.url_input, 1)

        self.btn_paste = QPushButton(self.i18n('paste_button').lower())
        self.btn_paste.setObjectName('PrimaryButton')
        self.btn_paste.setProperty('big', True)
        self.btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_paste.clicked.connect(self._paste_clipboard)
        url_row.addWidget(self.btn_paste)
        layout.addLayout(url_row)

        self.hero_hint_label = QLabel('')
        self.hero_hint_label.setObjectName('HeroHint')
        self.hero_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hero_hint_label)

        layout.addStretch(3)

        # Discrete destination footer
        footer_row = QHBoxLayout()
        footer_row.addStretch(1)
        self.btn_save_to = QPushButton('')
        self.btn_save_to.setObjectName('SaveToButton')
        self.btn_save_to.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_to.clicked.connect(self._choose_output_dir)
        footer_row.addWidget(self.btn_save_to)
        footer_row.addStretch(1)
        layout.addLayout(footer_row)

        return page

    def _build_configure_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName('PageConfigure')
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_content.setObjectName('ScrollContent')
        body = QVBoxLayout(scroll_content)
        body.setContentsMargins(14, 10, 14, 10)
        body.setSpacing(8)

        # --- media preview card (compact horizontal header) ---
        preview_card = QFrame()
        preview_card.setProperty('class', 'Card')
        preview_layout = QHBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        preview_layout.setSpacing(12)

        self.thumb_label = QLabel()
        self.thumb_label.setObjectName('ThumbBox')
        self.thumb_label.setFixedSize(128, 72)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setText('preview')
        preview_layout.addWidget(self.thumb_label)

        preview_info = QVBoxLayout()
        preview_info.setSpacing(3)
        self.preview_title = QLabel(self.i18n('preview_empty').lower())
        self.preview_title.setObjectName('PreviewTitle')
        self.preview_title.setWordWrap(True)
        preview_info.addWidget(self.preview_title)

        meta_info_row = QHBoxLayout()
        meta_info_row.setSpacing(14)
        self.preview_channel = QLabel('')
        self.preview_channel.setObjectName('SecondaryText')
        meta_info_row.addWidget(self.preview_channel)

        self.preview_duration = QLabel('')
        self.preview_duration.setObjectName('SecondaryText')
        meta_info_row.addWidget(self.preview_duration)

        self.preview_playlist_badge = QLabel('')
        self.preview_playlist_badge.setStyleSheet('color: #34d399; font-weight: 600;')
        meta_info_row.addWidget(self.preview_playlist_badge)
        meta_info_row.addStretch(1)
        preview_info.addLayout(meta_info_row)
        preview_info.addStretch(1)

        preview_layout.addLayout(preview_info, 1)
        body.addWidget(preview_card)

        # segmented mode selector (always visible: the primary download decision)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        mode_row.setContentsMargins(0, 2, 0, 0)

        self.radio_video = QRadioButton(self.i18n('mode_video').lower())
        self.radio_video.setChecked(True)
        self.mode_group.addButton(self.radio_video, 0)
        mode_row.addWidget(self.radio_video)

        self.radio_audio = QRadioButton(self.i18n('mode_audio').lower())
        self.mode_group.addButton(self.radio_audio, 1)
        mode_row.addWidget(self.radio_audio)

        self.radio_split = QRadioButton(self.i18n('mode_split').lower())
        self.mode_group.addButton(self.radio_split, 2)
        mode_row.addWidget(self.radio_split)

        self.radio_thumbnail = QRadioButton(self.i18n('mode_thumbnail').lower())
        self.mode_group.addButton(self.radio_thumbnail, 3)
        mode_row.addWidget(self.radio_thumbnail)
        mode_row.addStretch(1)
        body.addLayout(mode_row)
        self.mode_group.idToggled.connect(self._on_mode_changed)

        # notice for thumbnail mode
        self.thumb_mode_notice = QLabel(self.i18n('notice_thumbnail_mode').lower())
        self.thumb_mode_notice.setObjectName('SecondaryText')
        self.thumb_mode_notice.setVisible(False)
        body.addWidget(self.thumb_mode_notice)

        # --- option widgets (created first, assembled into sections after) ---
        self.quality_label = QLabel(self.i18n('quality_label').lower())
        self.quality_label.setObjectName('SecondaryText')
        self.quality_combo = QComboBox()
        self.quality_combo.addItem(self.i18n('quality_best').lower(), 'best')
        self.quality_combo.addItem(self.i18n('quality_2160p').lower(), '2160p')
        self.quality_combo.addItem(self.i18n('quality_1440p').lower(), '1440p')
        self.quality_combo.addItem(self.i18n('quality_1080p').lower(), '1080p')
        self.quality_combo.addItem(self.i18n('quality_720p').lower(), '720p')
        self.quality_combo.addItem(self.i18n('quality_480p').lower(), '480p')
        self.quality_combo.addItem(self.i18n('quality_360p').lower(), '360p')

        self.format_label = QLabel(self.i18n('format_label').lower())
        self.format_label.setObjectName('SecondaryText')
        self.format_combo = QComboBox()
        self.format_combo.addItem('mp4', 'mp4')
        self.format_combo.addItem('mkv', 'mkv')

        self.audio_format_label = QLabel(self.i18n('audio_format_label').lower())
        self.audio_format_label.setObjectName('SecondaryText')
        self.audio_format_combo = QComboBox()
        self.audio_format_combo.addItem('mp3', 'mp3')
        self.audio_format_combo.addItem('m4a', 'm4a')
        self.audio_format_combo.addItem('flac', 'flac')
        self.audio_format_combo.addItem('wav', 'wav')
        self.audio_format_combo.addItem('opus', 'opus')
        self.audio_format_combo.currentIndexChanged.connect(self._on_audio_format_changed)

        self.audio_quality_label = QLabel(self.i18n('audio_quality_label').lower())
        self.audio_quality_label.setObjectName('SecondaryText')
        self.audio_quality_combo = QComboBox()
        self.audio_quality_combo.addItem(self.i18n('audio_quality_best').lower(), 'best')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_320').lower(), '320')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_256').lower(), '256')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_192').lower(), '192')
        self.audio_quality_combo.addItem(self.i18n('audio_quality_128').lower(), '128')

        self.chk_embed_thumb = QCheckBox(self.i18n('opt_embed_thumbnail').lower())
        self.chk_embed_thumb.setChecked(True)

        self.chk_embed_meta = QCheckBox(self.i18n('opt_embed_metadata').lower())
        self.chk_embed_meta.setChecked(True)

        self.chk_subtitles = QCheckBox(self.i18n('opt_subtitles').lower())
        self.chk_subtitles.setChecked(False)
        self.chk_subtitles.toggled.connect(self._on_subtitles_toggled)

        self.sub_lang_label = QLabel(self.i18n('sub_lang_label').lower())
        self.sub_lang_label.setObjectName('SecondaryText')

        self.sub_lang_combo = QComboBox()
        self.sub_lang_combo.addItem(self.i18n('sub_lang_pt').lower(), 'pt')
        self.sub_lang_combo.addItem(self.i18n('sub_lang_en').lower(), 'en')
        self.sub_lang_combo.addItem(self.i18n('sub_lang_all').lower(), 'all')
        self.sub_lang_combo.setEnabled(False)

        self.chk_video_muted = QCheckBox(self.i18n('opt_video_muted').lower())
        self.chk_video_muted.setChecked(False)
        self.chk_video_muted.setVisible(False)

        self.chk_playlist = QCheckBox(self.i18n('opt_playlist').lower())
        self.chk_playlist.setChecked(False)

        self.playlist_tip = QLabel(self.i18n('playlist_notice').lower())
        self.playlist_tip.setStyleSheet('color: #8b949e; font-size: 10px; margin-left: 8px;')

        # --- accordion sections (collapsed by default: smart defaults shown as summary) ---
        self.section_quality = CollapsibleSection(self.i18n('quality_label').rstrip(':').lower())
        if self.quality_combo.currentData() != 'best':
            self.quality_combo.setCurrentIndex(0)
        quality_grid = QGridLayout()
        quality_grid.setHorizontalSpacing(14)
        quality_grid.setVerticalSpacing(8)
        quality_grid.addWidget(self.quality_label, 0, 0)
        quality_grid.addWidget(self.quality_combo, 0, 1)
        quality_grid.addWidget(self.format_label, 0, 2)
        quality_grid.addWidget(self.format_combo, 0, 3)
        quality_grid.setColumnStretch(1, 1)
        quality_grid.setColumnStretch(3, 2)
        self.section_quality.content_layout.addLayout(quality_grid)
        body.addWidget(self.section_quality)

        self.section_audio = CollapsibleSection(self.i18n('audio_format_label').rstrip(':').lower())
        audio_grid = QGridLayout()
        audio_grid.setHorizontalSpacing(14)
        audio_grid.setVerticalSpacing(8)
        audio_grid.addWidget(self.audio_format_label, 0, 0)
        audio_grid.addWidget(self.audio_format_combo, 0, 1)
        audio_grid.addWidget(self.audio_quality_label, 0, 2)
        audio_grid.addWidget(self.audio_quality_combo, 0, 3)
        audio_grid.setColumnStretch(1, 1)
        audio_grid.setColumnStretch(3, 2)
        self.section_audio.content_layout.addLayout(audio_grid)
        body.addWidget(self.section_audio)

        self.section_playlist = CollapsibleSection(self.i18n('playlist_prefix').rstrip(':').lower())
        playlist_box = QVBoxLayout()
        playlist_box.setSpacing(2)
        playlist_box.addWidget(self.chk_playlist)
        playlist_box.addWidget(self.playlist_tip)
        self.section_playlist.content_layout.addLayout(playlist_box)
        body.addWidget(self.section_playlist)

        self.section_extras = CollapsibleSection(self.i18n('section_extras').lower())
        extras_grid = QGridLayout()
        extras_grid.setHorizontalSpacing(18)
        extras_grid.setVerticalSpacing(8)
        extras_grid.addWidget(self.chk_embed_thumb, 0, 0)
        extras_grid.addWidget(self.chk_embed_meta, 0, 1)
        sub_box = QHBoxLayout()
        sub_box.setSpacing(8)
        sub_box.addWidget(self.chk_subtitles)
        sub_box.addWidget(self.sub_lang_label)
        sub_box.addWidget(self.sub_lang_combo)
        sub_box.addStretch(1)
        extras_grid.addLayout(sub_box, 1, 0, 1, 2)
        extras_grid.addWidget(self.chk_video_muted, 2, 0)
        self.section_extras.content_layout.addLayout(extras_grid)
        body.addWidget(self.section_extras)

        body.addStretch(1)
        scroll_area.setWidget(scroll_content)
        page_layout.addWidget(scroll_area, 1)

        # --- fixed action bar ---
        action_bar = QFrame()
        action_bar.setObjectName('ActionBar')
        bar_layout = QHBoxLayout(action_bar)
        bar_layout.setContentsMargins(14, 10, 14, 10)
        bar_layout.setSpacing(10)

        self.btn_back = QPushButton(self.i18n('btn_back').lower())
        self.btn_back.setObjectName('GhostButton')
        self.btn_back.clicked.connect(self._go_home)
        bar_layout.addWidget(self.btn_back)
        bar_layout.addStretch(1)

        self.btn_download = QPushButton(self.i18n('btn_download_now').lower())
        self.btn_download.setObjectName('PrimaryButton')
        self.btn_download.setProperty('big', True)
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self._start_download)
        bar_layout.addWidget(self.btn_download)
        page_layout.addWidget(action_bar)

        # --- wiring for live summaries ---
        self.quality_combo.currentIndexChanged.connect(self._render_summaries)
        self.format_combo.currentIndexChanged.connect(self._render_summaries)
        self.chk_playlist.toggled.connect(self._render_summaries)
        self.chk_embed_thumb.toggled.connect(self._render_summaries)
        self.chk_embed_meta.toggled.connect(self._render_summaries)
        self.chk_video_muted.toggled.connect(self._render_summaries)
        return page

    def _build_progress_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName('PageProgress')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(10)

        layout.addStretch(2)

        progress_card = QFrame()
        progress_card.setProperty('class', 'Card')
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(14, 12, 14, 12)
        progress_layout.setSpacing(10)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.status_dot = QLabel('●')
        self.status_dot.setStyleSheet('color: #34d399; font-size: 13px;')
        action_row.addWidget(self.status_dot)

        self.status_label = QLabel(self.i18n('status_ready').lower())
        self.status_label.setStyleSheet('font-size: 12px; font-weight: 600; color: #f0f6fc;')
        action_row.addWidget(self.status_label)
        action_row.addStretch(1)

        self.btn_open_file = QPushButton(self.i18n('open_file').lower())
        self.btn_open_file.setVisible(False)
        self.btn_open_file.clicked.connect(self._open_downloaded_file)
        action_row.addWidget(self.btn_open_file)
        progress_layout.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName('MainProgress')
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)
        self.pct_box = self._create_metric_widget(self.i18n('progress_label'), '0%')
        metrics_row.addWidget(self.pct_box, 1)
        self.speed_box = self._create_metric_widget(self.i18n('speed_label'), '--')
        metrics_row.addWidget(self.speed_box, 1)
        self.eta_box = self._create_metric_widget(self.i18n('eta_label'), '--:--')
        metrics_row.addWidget(self.eta_box, 1)
        self.size_box = self._create_metric_widget(self.i18n('size_label'), '0 mb / 0 mb', is_last=True)
        metrics_row.addWidget(self.size_box, 1)
        progress_layout.addLayout(metrics_row)

        layout.addWidget(progress_card)

        # Buttons row below the card
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        self.btn_back_settings = QPushButton(self.i18n('btn_back_to_settings').lower())
        self.btn_back_settings.setObjectName('GhostButton')
        self.btn_back_settings.clicked.connect(self._back_to_settings)
        buttons_row.addWidget(self.btn_back_settings)

        buttons_row.addStretch(1)

        self.btn_open_folder = QPushButton(f"📁 {self.i18n('open_folder').lower()}")
        self.btn_open_folder.clicked.connect(self._open_output_dir)
        buttons_row.addWidget(self.btn_open_folder)

        self.btn_cancel = QPushButton(self.i18n('btn_cancel').lower())
        self.btn_cancel.setObjectName('CancelButton')
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_download)
        buttons_row.addWidget(self.btn_cancel)

        self.btn_new_download = QPushButton(self.i18n('btn_new_download').lower())
        self.btn_new_download.setObjectName('PrimaryButton')
        self.btn_new_download.setVisible(False)
        self.btn_new_download.clicked.connect(self._start_new_download_flow)
        buttons_row.addWidget(self.btn_new_download)
        layout.addLayout(buttons_row)

        # Collapsible activity log
        log_header_layout = QHBoxLayout()
        self.btn_toggle_logs = QPushButton(self.i18n('toggle_logs_show').lower())
        self.btn_toggle_logs.setStyleSheet('border: none; background: transparent; color: #34d399; text-align: left; font-size: 11px;')
        self.btn_toggle_logs.clicked.connect(self._toggle_logs)
        log_header_layout.addWidget(self.btn_toggle_logs)
        log_header_layout.addStretch(1)
        layout.addLayout(log_header_layout)

        self.log_view = QTextEdit()
        self.log_view.setObjectName('LogView')
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        self.log_view.setVisible(False)
        layout.addWidget(self.log_view)

        layout.addStretch(3)
        return page

    def _build_drawer(self) -> None:
        """Hamburger sidebar: actions, preferences and system entries."""
        self.drawer_overlay = _DrawerOverlay(self)
        self.drawer_overlay.setObjectName('DrawerOverlay')
        self.drawer_overlay.setVisible(False)
        self.drawer_overlay.clicked.connect(self._close_drawer)

        self.drawer = QFrame(self)
        self.drawer.setObjectName('DrawerFrame')
        self.drawer.setFixedWidth(264)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setXOffset(6)
        shadow.setColor(QColor(0, 0, 0, 170))
        self.drawer.setGraphicsEffect(shadow)

        drawer_layout = QVBoxLayout(self.drawer)
        drawer_layout.setContentsMargins(10, 14, 10, 10)
        drawer_layout.setSpacing(2)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        drawer_logo = QLabel()
        if self.logo_path and self.logo_path.exists():
            drawer_logo.setPixmap(QPixmap(str(self.logo_path)).scaled(
                22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))
        else:
            drawer_logo.setText('▶')
            drawer_logo.setStyleSheet('font-size: 14px; color: #34d399;')
        brand_row.addWidget(drawer_logo)
        self.drawer_brand = QLabel(self.i18n('app_title').lower())
        self.drawer_brand.setObjectName('DrawerBrand')
        brand_row.addWidget(self.drawer_brand)
        brand_row.addStretch(1)
        drawer_layout.addLayout(brand_row)

        self.drawer_group_downloads = QLabel(self.i18n('drawer_downloads').lower())
        self.drawer_group_downloads.setObjectName('DrawerGroup')
        drawer_layout.addWidget(self.drawer_group_downloads)

        self.btn_drawer_new = QPushButton(self.i18n('drawer_new_download').lower())
        self.btn_drawer_new.setObjectName('DrawerItem')
        self.btn_drawer_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_drawer_new.clicked.connect(self._on_drawer_new_download)
        drawer_layout.addWidget(self.btn_drawer_new)

        self.btn_drawer_folder = QPushButton(f"📁 {self.i18n('open_folder').lower()}")
        self.btn_drawer_folder.setObjectName('DrawerItem')
        self.btn_drawer_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_drawer_folder.clicked.connect(self._open_output_dir)
        drawer_layout.addWidget(self.btn_drawer_folder)

        self.drawer_group_preferences = QLabel(self.i18n('drawer_preferences').lower())
        self.drawer_group_preferences.setObjectName('DrawerGroup')
        drawer_layout.addWidget(self.drawer_group_preferences)

        self.btn_drawer_save = QPushButton('')
        self.btn_drawer_save.setObjectName('DrawerItem')
        self.btn_drawer_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_drawer_save.clicked.connect(self._choose_output_dir)
        drawer_layout.addWidget(self.btn_drawer_save)

        lang_row = QHBoxLayout()
        lang_row.setContentsMargins(6, 4, 6, 4)
        self.lang_label = QLabel('')
        self.lang_label.setVisible(False)
        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName('LangCombo')
        self.lang_combo.addItem('🌐 pt-br', 'pt_BR')
        self.lang_combo.addItem('🌐 en-us', 'en_US')
        lang_idx = 0 if self.i18n.current_lang == 'pt_BR' else 1
        self.lang_combo.setCurrentIndex(lang_idx)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch(1)
        drawer_layout.addLayout(lang_row)

        auto_update_row = QHBoxLayout()
        auto_update_row.setContentsMargins(6, 2, 6, 2)
        self.chk_auto_update = QCheckBox('')
        self.chk_auto_update.setChecked(self.update_settings.auto_check_updates)
        self.chk_auto_update.toggled.connect(self._on_auto_update_toggled)
        auto_update_row.addWidget(self.chk_auto_update)
        auto_update_row.addStretch(1)
        drawer_layout.addLayout(auto_update_row)

        self.drawer_group_system = QLabel(self.i18n('drawer_system').lower())
        self.drawer_group_system.setObjectName('DrawerGroup')
        drawer_layout.addWidget(self.drawer_group_system)

        self.btn_drawer_updates = QPushButton(self.i18n('drawer_check_updates').lower())
        self.btn_drawer_updates.setObjectName('DrawerItem')
        self.btn_drawer_updates.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_drawer_updates.clicked.connect(self._manual_update_check)
        drawer_layout.addWidget(self.btn_drawer_updates)

        self.btn_drawer_logs = QPushButton(self.i18n('drawer_show_logs').lower())
        self.btn_drawer_logs.setObjectName('DrawerItem')
        self.btn_drawer_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_drawer_logs.clicked.connect(self._open_logs)
        drawer_layout.addWidget(self.btn_drawer_logs)

        drawer_layout.addStretch(1)
        self.drawer_version = QLabel(f'v{__version__}')
        self.drawer_version.setObjectName('DrawerVersion')
        drawer_layout.addWidget(self.drawer_version)

        self._drawer_animation = QPropertyAnimation(self.drawer, b'pos', self)
        self._drawer_animation.setDuration(190)
        self._drawer_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._drawer_animation.finished.connect(self._on_drawer_animation_finished)

    def _create_metric_widget(self, label_text: str, default_val: str, is_last: bool = False) -> QFrame:
        frame = QFrame()
        frame.setProperty('class', 'MetricBoxLast' if is_last else 'MetricBox')
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(2)

        lbl = QLabel(label_text.lower())
        lbl.setObjectName('MetricLabel')
        layout.addWidget(lbl)

        val = QLabel(default_val.lower())
        val.setObjectName('MetricValue')
        layout.addWidget(val)

        frame.label_widget = lbl
        frame.val_widget = val
        return frame

    # ------------------------------------------------------------------
    # drawer behaviour
    # ------------------------------------------------------------------
    def _toggle_drawer(self) -> None:
        if not self.drawer.isHidden():
            self._close_drawer()
        else:
            self._open_drawer()

    def _open_drawer(self) -> None:
        self.drawer_overlay.setGeometry(0, 0, self.width(), self.height())
        self.drawer.setGeometry(-self.drawer.width(), 0, self.drawer.width(), self.height())
        self.drawer_overlay.setVisible(True)
        self.drawer_overlay.raise_()
        self.drawer.setVisible(True)
        self.drawer.raise_()
        self._drawer_animation.stop()
        self._drawer_animation.setStartValue(QPoint(-self.drawer.width(), 0))
        self._drawer_animation.setEndValue(QPoint(0, 0))
        self._drawer_animation.start()

    def _close_drawer(self) -> None:
        if self.drawer.isHidden():
            return
        self._drawer_animation.stop()
        self._drawer_animation.setStartValue(self.drawer.pos())
        self._drawer_animation.setEndValue(QPoint(-self.drawer.width(), 0))
        self._drawer_animation.start()

    def _on_drawer_animation_finished(self) -> None:
        if self.drawer.x() < 0:
            self.drawer.setVisible(False)
            self.drawer_overlay.setVisible(False)

    def _on_drawer_new_download(self) -> None:
        self._close_drawer()
        self._start_new_download_flow()

    def _open_logs(self) -> None:
        self._close_drawer()
        self._set_phase(PHASE_PROGRESS)
        if not self.log_view.isVisible():
            self._toggle_logs()

    # ------------------------------------------------------------------
    # guided-flow phases & summaries
    # ------------------------------------------------------------------
    def _set_phase(self, phase: int) -> None:
        self._phase = phase
        self.stack.setCurrentIndex(phase)
        self.stepper_row.setVisible(phase != PHASE_HOME)
        self._render_stepper()

    def _render_stepper(self) -> None:
        if not hasattr(self, 'step_dots'):
            return
        step_keys = ('step_link', 'step_settings', 'step_download')
        for index in range(3):
            done = index < self._phase
            active = index == self._phase

            dot = self.step_dots[index]
            dot.setText('●' if (done or active) else '○')
            dot.setObjectName('StepDotActive' if active else ('StepDotDone' if done else 'StepDot'))

            text = self.step_texts[index]
            text.setText(self.i18n(step_keys[index]).lower())
            text.setObjectName('StepTextActive' if active else 'StepText')

            _repolish(dot)
            _repolish(text)

    def _render_save_to(self) -> None:
        prefix = self.i18n('destination_folder').lower()
        full_text = f'{prefix} {self.output_dir}'
        metrics = QFontMetrics(self.btn_save_to.font())
        elided = metrics.elidedText(full_text, Qt.TextElideMode.ElideMiddle, 460)
        self.btn_save_to.setText(elided)
        self.btn_save_to.setToolTip(full_text)
        if hasattr(self, 'btn_drawer_save'):
            drawer_metrics = QFontMetrics(self.btn_drawer_save.font())
            drawer_elided = drawer_metrics.elidedText(full_text, Qt.TextElideMode.ElideMiddle, 200)
            self.btn_drawer_save.setText(drawer_elided)
            self.btn_drawer_save.setToolTip(full_text)

    def _render_summaries(self) -> None:
        """Refreshes the collapsed accordion summary values (compact mode)."""
        if not hasattr(self, 'section_quality'):
            return

        quality = self.quality_combo.currentData()
        if quality:
            quality_short = self.i18n(f'quality_short_{quality}').lower()
            container = self.format_combo.currentData() or ''
            self.section_quality.set_summary(f'{quality_short} · {container}')

        codec = self.audio_format_combo.currentData() or ''
        bitrate = self.audio_quality_combo.currentData() or ''
        if bitrate == '0':
            bitrate_short = self.i18n('audio_quality_wav').lower()
        else:
            bitrate_short = self.i18n(f'audio_quality_short_{bitrate}').lower()
        if codec and bitrate:
            self.section_audio.set_summary(f'{codec} · {bitrate_short}')

        if self.chk_playlist.isChecked():
            if self._playlist_count:
                self.section_playlist.set_summary(
                    self.i18n('summary_playlist_all', count=self._playlist_count).lower()
                )
            else:
                self.section_playlist.set_summary(self.i18n('opt_playlist').lower())
        else:
            self.section_playlist.set_summary(self.i18n('summary_single_video').lower())

        extras: list[str] = []
        if self.chk_embed_thumb.isChecked():
            extras.append(self.i18n('summary_extras_cover').lower())
        if self.chk_embed_meta.isChecked():
            extras.append(self.i18n('summary_extras_metadata').lower())
        if self.chk_subtitles.isChecked() and self.chk_subtitles.isVisible():
            extras.append(self.i18n('summary_extras_subs').lower())
        if self.chk_video_muted.isVisible() and self.chk_video_muted.isChecked():
            extras.append(self.i18n('summary_extras_muted').lower())
        self.section_extras.set_summary(' · '.join(extras) if extras else self.i18n('summary_extras_none').lower())

    # ------------------------------------------------------------------
    # translations
    # ------------------------------------------------------------------
    def apply_translations(self) -> None:
        """Updates all strings according to current language (all lowercase)."""
        self.setWindowTitle(self.i18n('app_title').lower())
        self.app_title_label.setText(self.i18n('app_title').lower())
        self.version_badge.setText(f'v{__version__}')
        self.version_badge.setToolTip(self.i18n('update_check_tooltip').lower())

        # hero (home phase)
        self.hero_title_label.setText(self.i18n('hero_title').lower())
        self.app_subtitle_label.setText(self.i18n('app_subtitle').lower())
        self.url_input.setPlaceholderText('🔗 ' + self.i18n('url_placeholder').lower())
        self.btn_paste.setText(self.i18n('paste_button').lower())
        self.hero_hint_label.setText(self.i18n('hero_hint').lower())
        self._render_save_to()
        self._render_stepper()

        # preview
        if not self.last_fetched_url:
            self.preview_title.setText(self.i18n('preview_empty').lower())

        # configure page
        self.radio_video.setText(self.i18n('mode_video').lower())
        self.radio_audio.setText(self.i18n('mode_audio').lower())
        self.radio_split.setText(self.i18n('mode_split').lower())
        self.radio_thumbnail.setText(self.i18n('mode_thumbnail').lower())
        self.thumb_mode_notice.setText(self.i18n('notice_thumbnail_mode').lower())
        self.chk_video_muted.setText(self.i18n('opt_video_muted').lower())

        self.section_quality.set_title(self.i18n('quality_label').rstrip(':').lower())
        self.section_audio.set_title(self.i18n('audio_format_label').rstrip(':').lower())
        self.section_playlist.set_title(self.i18n('playlist_prefix').rstrip(':').lower())
        self.section_extras.set_title(self.i18n('section_extras').lower())

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

        # action buttons
        self.btn_back.setText(self.i18n('btn_back').lower())
        self.btn_back_settings.setText(self.i18n('btn_back_to_settings').lower())
        self.btn_new_download.setText(self.i18n('btn_new_download').lower())
        self.btn_cancel.setText(self.i18n('btn_cancel').lower())
        self.btn_open_file.setText(self.i18n('open_file').lower())
        self.btn_open_folder.setText(f"📁 {self.i18n('open_folder').lower()}")

        if self.download_thread and self.download_thread.isRunning():
            self.btn_download.setText(self.i18n('btn_downloading').lower())
        else:
            self.btn_download.setText(self.i18n('btn_download_now').lower())

        if not self.download_thread or not self.download_thread.isRunning():
            if self.last_downloaded_file:
                self.status_label.setText(self.i18n('status_finished').lower())
            elif self.last_fetched_url:
                self.status_label.setText(self.i18n('preview_ready').lower())
            else:
                self.status_label.setText(self.i18n('status_ready').lower())

        self.pct_box.label_widget.setText(self.i18n('progress_label').lower())
        self.speed_box.label_widget.setText(self.i18n('speed_label').lower())
        self.eta_box.label_widget.setText(self.i18n('eta_label').lower())
        self.size_box.label_widget.setText(self.i18n('size_label').lower())
        self.chk_auto_update.setText(self.i18n('opt_auto_check_updates').lower())

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

        # Update audio quality combo according to format
        self._update_wav_state()

        # Update subtitle lang combo text
        cur_sl = self.sub_lang_combo.currentData()
        self.sub_lang_combo.clear()
        self.sub_lang_combo.addItem(self.i18n('sub_lang_pt').lower(), 'pt')
        self.sub_lang_combo.addItem(self.i18n('sub_lang_en').lower(), 'en')
        self.sub_lang_combo.addItem(self.i18n('sub_lang_all').lower(), 'all')
        idx = self.sub_lang_combo.findData(cur_sl)
        if idx >= 0:
            self.sub_lang_combo.setCurrentIndex(idx)

        # drawer
        self.drawer_brand.setText(self.i18n('app_title').lower())
        self.drawer_group_downloads.setText(self.i18n('drawer_downloads').lower())
        self.drawer_group_preferences.setText(self.i18n('drawer_preferences').lower())
        self.drawer_group_system.setText(self.i18n('drawer_system').lower())
        self.btn_drawer_new.setText(self.i18n('drawer_new_download').lower())
        self.btn_drawer_folder.setText(f"📁 {self.i18n('open_folder').lower()}")
        self.btn_drawer_updates.setText(self.i18n('drawer_check_updates').lower())
        self.btn_drawer_logs.setText(self.i18n('drawer_show_logs').lower())
        self.drawer_version.setText(f'v{__version__}')

        self._render_summaries()
        self._render_update_state()

    # ------------------------------------------------------------------
    # mode-dependent controls visibility & summary refresh
    # ------------------------------------------------------------------
    def _on_audio_format_changed(self) -> None:
        self._update_wav_state()

    def _update_wav_state(self) -> None:
        is_wav = self.audio_format_combo.currentData() == 'wav'
        cur_aq = self.audio_quality_combo.currentData()

        self.audio_quality_combo.blockSignals(True)
        self.audio_quality_combo.clear()
        if is_wav:
            self.audio_quality_combo.addItem(self.i18n('audio_quality_wav').lower(), '0')
            self.audio_quality_combo.setEnabled(False)
        else:
            self.audio_quality_combo.addItem(self.i18n('audio_quality_best').lower(), 'best')
            self.audio_quality_combo.addItem(self.i18n('audio_quality_320').lower(), '320')
            self.audio_quality_combo.addItem(self.i18n('audio_quality_256').lower(), '256')
            self.audio_quality_combo.addItem(self.i18n('audio_quality_192').lower(), '192')
            self.audio_quality_combo.addItem(self.i18n('audio_quality_128').lower(), '128')
            self.audio_quality_combo.setEnabled(True)
            idx = self.audio_quality_combo.findData(cur_aq)
            if idx >= 0:
                self.audio_quality_combo.setCurrentIndex(idx)
        self.audio_quality_combo.blockSignals(False)

        if is_wav and self.radio_audio.isChecked():
            self.chk_embed_thumb.setEnabled(False)
            self.chk_embed_thumb.setToolTip(self.i18n('notice_wav_thumbnail').lower())
        else:
            self.chk_embed_thumb.setEnabled(True)
            self.chk_embed_thumb.setToolTip('')

        self._render_summaries()

    # ------------------------------------------------------------------
    # update flow
    # ------------------------------------------------------------------
    def _set_update_state(self, state: str, *, info=None, error_code: str | None = None) -> None:
        if info is not None:
            self._update_info = info
        self._update_state = state
        self._update_error_code = error_code
        self._render_update_state()

    def _update_install_available(self) -> bool:
        if not self._update_info or not is_frozen():
            return False
        try:
            asset = self._update_info.asset_for(installed=is_running_installed())
        except Exception:
            return False
        return bool(asset and asset.has_checksum)

    def _render_update_state(self) -> None:
        if not hasattr(self, 'update_banner'):
            return

        state = self._update_state
        info = self._update_info
        self.update_banner.setVisible(state != 'hidden')
        if state == 'hidden':
            return

        self.update_notes_btn.setVisible(False)
        self.update_skip_btn.setVisible(False)
        self.update_later_btn.setVisible(False)
        self.update_install_btn.setVisible(False)
        self.update_cancel_btn.setVisible(False)
        self.update_progress.setVisible(False)
        self.update_progress.setValue(int(self._update_progress_value))
        self.update_progress.setRange(0, 100)

        if state == 'checking':
            self.update_title.setText(self.i18n('update_checking').lower())
            self.update_detail.setText(self.i18n('update_checking_detail').lower())
            return

        if state == 'up_to_date':
            version = info.version if info else __version__
            self.update_title.setText(self.i18n('update_up_to_date_title').lower())
            self.update_detail.setText(
                self.i18n('update_up_to_date_detail', version=version).lower()
            )
            self.update_later_btn.setText(self.i18n('update_close').lower())
            self.update_later_btn.setVisible(True)
            return

        if state in {'error', 'source'}:
            if state == 'source':
                self.update_title.setText(
                    self.i18n('update_available_title', version=info.version).lower()
                    if info else self.i18n('update_available_title_generic').lower()
                )
                self.update_detail.setText(self.i18n('update_source_mode').lower())
            else:
                self.update_title.setText(self.i18n('update_error_title').lower())
                code = self._update_error_code or 'unknown'
                key = f'update_error_{code}'
                message = self.i18n(key)
                if message == key:
                    message = self.i18n('update_error_unknown')
                self.update_detail.setText(message.lower())

            self.update_notes_btn.setText(self.i18n('update_releases').lower())
            self.update_notes_btn.setVisible(True)
            self.update_later_btn.setText(self.i18n('update_close').lower())
            self.update_later_btn.setVisible(True)
            if (
                state == 'error'
                and self._update_info is not None
                and self._update_install_available()
                and self._update_error_code in {'download', 'checksum', 'install'}
            ):
                self.update_install_btn.setText(self.i18n('update_retry').lower())
                self.update_install_btn.setVisible(True)
            return

        if info is None:
            self.update_banner.setVisible(False)
            return

        if state == 'available':
            self.update_title.setText(
                self.i18n('update_available_title', version=info.version).lower()
            )
            installable = self._update_install_available()
            if not is_frozen():
                self.update_detail.setText(self.i18n('update_source_mode').lower())
            elif not installable:
                self.update_detail.setText(self.i18n('update_no_asset').lower())
            else:
                self.update_detail.setText(
                    self.i18n(
                        'update_available_detail',
                        current=__version__,
                        latest=info.version,
                    ).lower()
                )
            self.update_notes_btn.setText(self.i18n('update_notes').lower())
            self.update_notes_btn.setVisible(True)
            self.update_skip_btn.setText(self.i18n('update_skip').lower())
            self.update_skip_btn.setVisible(True)
            self.update_later_btn.setText(self.i18n('update_later').lower())
            self.update_later_btn.setVisible(True)
            if installable:
                self.update_install_btn.setText(self.i18n('update_download_install').lower())
                self.update_install_btn.setVisible(True)
            else:
                self.update_notes_btn.setText(self.i18n('update_releases').lower())
            return

        if state == 'downloading':
            self.update_title.setText(
                self.i18n('update_downloading_title', version=info.version).lower()
            )
            detail = self._update_progress_text or self.i18n('update_downloading_detail', percent=0, done='0 b', total='0 b')
            self.update_detail.setText(detail.lower())
            self.update_progress.setVisible(True)
            self.update_cancel_btn.setText(self.i18n('update_cancel').lower())
            self.update_cancel_btn.setVisible(True)
            return

        if state == 'ready':
            self.update_title.setText(self.i18n('update_ready_title').lower())
            self.update_detail.setText(
                self.i18n('update_ready_detail', version=info.version).lower()
            )
            self.update_progress.setValue(100)
            self.update_progress.setVisible(True)
            self.update_notes_btn.setText(self.i18n('update_notes').lower())
            self.update_notes_btn.setVisible(True)
            self.update_later_btn.setText(self.i18n('update_later').lower())
            self.update_later_btn.setVisible(True)
            self.update_install_btn.setText(self.i18n('update_install_now').lower())
            self.update_install_btn.setVisible(True)
            return

    def _manual_update_check(self) -> None:
        self._update_manual_check = True
        self._start_update_check()

    def _maybe_auto_update_check(self) -> None:
        if not self._allow_update_check or not self.update_settings.auto_check_updates:
            return
        if self.download_thread and self.download_thread.isRunning():
            return
        if self.update_check_thread and self.update_check_thread.isRunning():
            return
        if self.update_download_thread and self.update_download_thread.isRunning():
            return
        if not self.update_settings.should_check():
            return
        self._update_manual_check = False
        self._start_update_check()

    def _start_update_check(self) -> None:
        if self.update_check_thread and self.update_check_thread.isRunning():
            return
        if self._update_manual_check:
            self._set_update_state('checking')
            self.log(f'> {self.i18n("log_update_checking").lower()}')
        self.version_badge.setEnabled(False)
        thread = UpdateCheckWorker(__version__)
        self.update_check_thread = thread
        thread.checked.connect(self._on_update_check_finished)
        thread.finished.connect(lambda t=thread: self._on_update_check_thread_finished(t))
        thread.start()

    def _on_update_check_thread_finished(self, thread: UpdateCheckWorker) -> None:
        if self.update_check_thread is thread:
            self.update_check_thread = None
        self.version_badge.setEnabled(True)
        thread.deleteLater()

    @Slot(object)
    def _on_update_check_finished(self, result: CheckResult) -> None:
        manual = self._update_manual_check
        self._update_manual_check = False

        if result.is_error:
            self.log(
                f'> {self.i18n("log_update_check_failed", error=result.error or result.error_code or "unknown").lower()}'
            )
            if manual:
                self._set_update_state('error', error_code=result.error_code or 'unknown')
            elif self._update_state == 'checking':
                self._hide_update_banner()
            return

        self.update_settings.mark_checked()
        self.update_settings.save()

        if result.update_available and result.info:
            self._update_info = result.info
            if manual or self.update_settings.should_show_version(result.info.version):
                self._update_path = None
                self._update_asset = None
                self._update_error_code = None
                self._update_progress_value = 0
                self._update_progress_text = ''
                self._set_update_state('available')
                self.log(f'> {self.i18n("log_update_available", version=result.info.version).lower()}')
            elif self._update_state == 'checking':
                self._hide_update_banner()
            return

        if manual:
            self._set_update_state('up_to_date', info=result.info)
            QTimer.singleShot(8000, self._hide_up_to_date_banner)
        elif self._update_state == 'checking':
            self._hide_update_banner()

    def _hide_up_to_date_banner(self) -> None:
        if self._update_state == 'up_to_date':
            self._hide_update_banner()

    def _hide_update_banner(self) -> None:
        self._update_state = 'hidden'
        self._render_update_state()

    def _open_update_notes(self) -> None:
        url = self._update_info.notes_url if self._update_info else RELEASES_URL
        if not url:
            url = RELEASES_URL
        QDesktopServices.openUrl(QUrl(url))

    def _skip_update_version(self) -> None:
        if not self._update_info:
            return
        self.update_settings.skipped_version = self._update_info.version
        self.update_settings.save()
        self.log(f'> {self.i18n("log_update_skipped", version=self._update_info.version).lower()}')
        self._hide_update_banner()

    def _on_auto_update_toggled(self, checked: bool) -> None:
        self.update_settings.auto_check_updates = bool(checked)
        self.update_settings.save()
        if checked and self._allow_update_check:
            QTimer.singleShot(1000, self._maybe_auto_update_check)

    def _on_update_install_clicked(self) -> None:
        if self._update_state in {'ready', 'error'} and self._update_path:
            self._install_update()
            return
        self._download_update()

    def _download_update(self) -> None:
        info = self._update_info
        if info is None:
            return
        if self.download_thread and self.download_thread.isRunning():
            self.status_label.setText(self.i18n('update_busy').lower())
            self.status_dot.setStyleSheet('color: #F59E0B; font-size: 13px;')
            return
        if not is_frozen():
            self._set_update_state('source')
            return
        if self.update_download_thread and self.update_download_thread.isRunning():
            return

        try:
            asset = info.asset_for(installed=is_running_installed())
        except Exception:
            asset = None
        if asset is None:
            self._set_update_state('error', error_code='no_asset')
            return
        if not asset.has_checksum:
            self._set_update_state('error', error_code='checksum_missing')
            return

        self._update_asset = asset
        self._update_path = None
        self._update_error_code = None
        self._update_progress_value = 0
        self._update_progress_text = ''
        self._set_update_state('downloading')
        self.log(f'> {self.i18n("log_update_downloading", version=info.version).lower()}')

        thread = UpdateDownloadWorker(asset)
        self.update_download_thread = thread
        thread.progress.connect(self._on_update_download_progress)
        thread.downloaded.connect(self._on_update_download_finished)
        thread.failed.connect(self._on_update_download_failed)
        thread.cancelled.connect(self._on_update_download_cancelled)
        thread.finished.connect(lambda t=thread: self._on_update_download_thread_finished(t))
        thread.start()

    def _on_update_download_progress(self, downloaded: int, total: int) -> None:
        percent = int(downloaded * 100 / total) if total else 0
        percent = max(0, min(100, percent))
        self._update_progress_value = percent
        done_text = self._format_bytes(downloaded)
        if total:
            self._update_progress_text = self.i18n(
                'update_downloading_detail',
                percent=percent,
                done=done_text,
                total=self._format_bytes(total),
            )
        else:
            self._update_progress_text = self.i18n(
                'update_downloading_detail_unknown',
                done=done_text,
            )
        if self._update_state == 'downloading':
            self.update_progress.setValue(percent)
            self.update_detail.setText(self._update_progress_text.lower())

    @Slot(str)
    def _on_update_download_finished(self, path: str) -> None:
        self._update_path = Path(path)
        self._update_progress_value = 100
        self._set_update_state('ready')
        self.log(f'> {self.i18n("log_update_downloaded", name=self._update_path.name).lower()}')

    @Slot(str)
    def _on_update_download_failed(self, error: str) -> None:
        self._update_asset = None
        self._update_path = None
        lowered = error.lower()
        code = 'checksum' if ('checksum' in lowered or 'sha256' in lowered or 'integrity' in lowered) else 'download'
        self.log(f'> {self.i18n("log_update_download_failed", error=error).lower()}')
        self._set_update_state('error', error_code=code)

    def _on_update_download_cancelled(self) -> None:
        self._update_asset = None
        self._update_path = None
        self.log(f'> {self.i18n("log_update_cancelled").lower()}')
        self._set_update_state('available')

    def _on_update_download_thread_finished(self, thread: UpdateDownloadWorker) -> None:
        if self.update_download_thread is thread:
            self.update_download_thread = None
        thread.deleteLater()

    def _cancel_update_download(self) -> None:
        if self.update_download_thread and self.update_download_thread.isRunning():
            self.update_download_thread.cancel()
            self.update_cancel_btn.setEnabled(False)
            self.update_detail.setText(self.i18n('update_cancelling').lower())

    def _install_update(self) -> None:
        info = self._update_info
        path = self._update_path
        if info is None or path is None or not path.is_file():
            self._set_update_state('available')
            return
        if self.download_thread and self.download_thread.isRunning():
            self.status_label.setText(self.i18n('update_busy').lower())
            self.status_dot.setStyleSheet('color: #F59E0B; font-size: 13px;')
            return
        if not is_frozen():
            self._set_update_state('source')
            return

        try:
            apply_update(info, path, installed=is_running_installed())
        except UpdateError as exc:
            self.log(f'> {self.i18n("log_update_install_failed", error=str(exc)).lower()}')
            self._set_update_state('error', error_code='install')
            return
        except Exception as exc:
            logger.debug('unexpected update failure', exc_info=True)
            self.log(f'> {self.i18n("log_update_install_failed", error=str(exc)).lower()}')
            self._set_update_state('error', error_code='install')
            return

        self.status_label.setText(self.i18n('update_restarting').lower())
        self.status_dot.setStyleSheet('color: #34d399; font-size: 13px;')
        self.log(f'> {self.i18n("log_update_restarting").lower()}')
        QTimer.singleShot(250, self.close)

    @staticmethod
    def _format_bytes(value: int) -> str:
        size = float(max(0, value))
        units = ('b', 'kb', 'mb', 'gb', 'tb')
        index = 0
        while size >= 1024 and index < len(units) - 1:
            size /= 1024
            index += 1
        if index == 0:
            return f'{int(size)} {units[index]}'
        return f'{size:.1f} {units[index]}'

    def _on_language_changed(self, index: int) -> None:
        lang_code = self.lang_combo.itemData(index)
        self.i18n.set_language(lang_code)
        self.apply_translations()

    def _on_mode_changed(self) -> None:
        self._update_controls_visibility()

    def _update_controls_visibility(self) -> None:
        is_video = self.radio_video.isChecked()
        is_audio = self.radio_audio.isChecked()
        is_split = self.radio_split.isChecked()
        is_thumb = self.radio_thumbnail.isChecked()

        show_video_opts = is_video or is_split
        show_audio_opts = is_audio or is_split

        # leaf-level visibility (kept for tests and precise state handling)
        self.quality_label.setVisible(show_video_opts)
        self.quality_combo.setVisible(show_video_opts)
        self.format_label.setVisible(show_video_opts)
        self.format_combo.setVisible(show_video_opts)

        self.audio_format_label.setVisible(show_audio_opts)
        self.audio_format_combo.setVisible(show_audio_opts)
        self.audio_quality_label.setVisible(show_audio_opts)
        self.audio_quality_combo.setVisible(show_audio_opts)

        self.thumb_mode_notice.setVisible(is_thumb)

        self.chk_video_muted.setVisible(is_split)
        self.chk_embed_thumb.setVisible(not is_thumb)
        self.chk_embed_meta.setVisible(not is_thumb)
        self.chk_subtitles.setVisible(show_video_opts)
        self.sub_lang_label.setVisible(show_video_opts)
        self.sub_lang_combo.setVisible(show_video_opts)

        # section-level visibility (accordion collapsed/hidden per mode)
        self.section_quality.setVisible(show_video_opts)
        self.section_audio.setVisible(show_audio_opts)
        self.section_playlist.setVisible(not is_thumb)
        self.section_extras.setVisible(not is_thumb)

        self._update_wav_state()
        self._render_summaries()

    def _on_subtitles_toggled(self, checked: bool) -> None:
        self.sub_lang_combo.setEnabled(checked)
        self._render_summaries()

    # ------------------------------------------------------------------
    # url & metadata flow
    # ------------------------------------------------------------------
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

    def _fetch_metadata_now(self) -> None:
        """Enter key on the url field: skip the debounce and fetch immediately."""
        self.debounce_timer.stop()
        url = self.url_input.text().strip()
        if url:
            self._fetch_metadata()

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
            prefix = self.i18n('channel_prefix').lower()
            self.preview_channel.setText(f'{prefix} {uploader}')

        dur = info.get('duration_str', '')
        if dur and dur != '--:--':
            prefix = self.i18n('duration_prefix').lower()
            self.preview_duration.setText(f'{prefix} {dur}')

        if info.get('is_playlist'):
            count = info.get('playlist_count', 0)
            self._playlist_count = count or 0
            prefix = self.i18n('playlist_prefix').lower()
            suffix = self.i18n('items_suffix').lower()
            self.preview_playlist_badge.setText(f'{prefix} {count} {suffix}' if count else f'{prefix}')
            self.chk_playlist.setChecked(True)
        else:
            self._playlist_count = 0
            self.preview_playlist_badge.setText('')

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                128, 72, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
            self.thumb_label.setPixmap(scaled)
            self.thumb_label.setText('')
        else:
            self.thumb_label.setPixmap(QPixmap())
            self.thumb_label.setText('preview')

        self.status_label.setText(self.i18n('preview_ready').lower())
        self.status_dot.setStyleSheet('color: #10b981; font-size: 13px;')

        # smart defaults are enough: the flow advances automatically
        self._render_summaries()
        self._set_phase(PHASE_CONFIGURE)

    @Slot(str)
    def _on_metadata_failed(self, error: str) -> None:
        self.preview_title.setText(self.i18n('preview_error').lower())
        self.log(f'[aviso preview] {clean_ansi(error)}')
        # keep the flow forgiving: the direct download may still work
        self._set_phase(PHASE_CONFIGURE)

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if text:
            self.url_input.setText(text.strip())

    def _prefill_from_clipboard(self) -> None:
        """Prefills the url field with a link found on the clipboard at startup."""
        if not self.isVisible() or self.url_input.text().strip():
            return
        try:
            text = (QApplication.clipboard().text() or '').strip()
        except Exception:
            return
        if (
            text.startswith(('http://', 'https://'))
            and len(text) <= 2048
            and '\n' not in text
            and ' ' not in text
        ):
            self.url_input.setText(text)

    def _clear_url(self) -> None:
        self.url_input.clear()
        self.last_fetched_url = ''
        self._playlist_count = 0
        self.preview_title.setText(self.i18n('preview_empty').lower())
        self.preview_channel.setText('')
        self.preview_duration.setText('')
        self.preview_playlist_badge.setText('')
        self.thumb_label.setPixmap(QPixmap())
        self.thumb_label.setText('preview')

    # ------------------------------------------------------------------
    # navigation between phases
    # ------------------------------------------------------------------
    def _go_home(self) -> None:
        if self.download_thread and self.download_thread.isRunning():
            return
        self._set_phase(PHASE_HOME)

    def _back_to_settings(self) -> None:
        if self.download_thread and self.download_thread.isRunning():
            return
        self.btn_download.setEnabled(True)
        self.btn_download.setText(self.i18n('btn_download_now').lower())
        self._set_phase(PHASE_CONFIGURE)

    def _start_new_download_flow(self) -> None:
        if self.download_thread and self.download_thread.isRunning():
            self.status_label.setText(self.i18n('alert_already_running').lower())
            return
        if self.update_download_thread and self.update_download_thread.isRunning():
            self.status_label.setText(self.i18n('update_busy').lower())
            self.status_dot.setStyleSheet('color: #f59e0b; font-size: 13px;')
            return
        self._reset_for_new_download()
        self._set_phase(PHASE_HOME)

    def _reset_for_new_download(self) -> None:
        self.last_downloaded_file = ''
        self._clear_url()
        self.progress_bar.setValue(0)
        self.pct_box.val_widget.setText('0%')
        self.speed_box.val_widget.setText('--')
        self.eta_box.val_widget.setText('--:--')
        self.size_box.val_widget.setText('0 mb / 0 mb')
        self.btn_open_file.setVisible(False)
        self.btn_new_download.setVisible(False)
        self.btn_back_settings.setVisible(True)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(False)
        if not self.download_thread or not self.download_thread.isRunning():
            self.status_label.setText(self.i18n('status_ready').lower())
            self.status_dot.setStyleSheet('color: #34d399; font-size: 13px;')

    # ------------------------------------------------------------------
    # destination folder
    # ------------------------------------------------------------------
    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, self.i18n('browse_folder').lower(), self.output_dir)
        if directory:
            self.output_dir = directory
            self._render_save_to()
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

    # ------------------------------------------------------------------
    # download flow
    # ------------------------------------------------------------------
    def _start_download(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText(self.i18n('alert_no_url').lower())
            self.status_dot.setStyleSheet('color: #EF4444; font-size: 13px;')
            self.log(f'> {self.i18n("alert_no_url").lower()}')
            return

        if self.download_thread and self.download_thread.isRunning():
            self.status_label.setText(self.i18n('alert_already_running').lower())
            return

        if self.update_download_thread and self.update_download_thread.isRunning():
            self.status_label.setText(self.i18n('update_busy').lower())
            self.status_dot.setStyleSheet('color: #F59E0B; font-size: 13px;')
            return

        # Prepare Options
        options = DownloadOptions()
        options.output_dir = self.output_dir

        if self.radio_audio.isChecked():
            options.mode = 'audio'
            options.audio_format = self.audio_format_combo.currentData()
            options.audio_quality = self.audio_quality_combo.currentData()
        elif self.radio_split.isChecked():
            options.mode = 'split'
            options.video_quality = self.quality_combo.currentData()
            options.video_format = self.format_combo.currentData()
            options.audio_format = self.audio_format_combo.currentData()
            options.audio_quality = self.audio_quality_combo.currentData()
            options.video_muted = self.chk_video_muted.isChecked()
            options.download_subs = self.chk_subtitles.isChecked()
            options.sub_lang = self.sub_lang_combo.currentData()
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
        self.btn_cancel.setVisible(True)
        self.btn_cancel.setEnabled(True)
        self.btn_open_file.setVisible(False)
        self.btn_new_download.setVisible(False)
        self.btn_back_settings.setVisible(False)
        self.progress_bar.setValue(0)
        if options.mode == 'split':
            self.status_label.setText(self.i18n('status_downloading_split').lower())
        else:
            self.status_label.setText(self.i18n('status_connecting').lower())
        self.status_dot.setStyleSheet('color: #10B981; font-size: 13px;')

        self.pct_box.val_widget.setText('0%')
        self.speed_box.val_widget.setText('--')
        self.eta_box.val_widget.setText('--:--')
        self.size_box.val_widget.setText('0 mb / 0 mb')

        self._set_phase(PHASE_PROGRESS)

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
            self.btn_download.setText(self.i18n('btn_download_now').lower())

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
        self.btn_download.setText(self.i18n('btn_download_now').lower())
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(False)
        self.btn_new_download.setVisible(True)
        self.btn_back_settings.setVisible(True)
        self.progress_bar.setValue(100)
        self.pct_box.val_widget.setText('100%')
        if info.get('video_path') and info.get('audio_path'):
            self.status_label.setText(self.i18n('status_finished_split').lower())
        else:
            self.status_label.setText(self.i18n('status_finished').lower())
        self.status_dot.setStyleSheet('color: #10B981; font-size: 13px;')

        filename = info.get('_filename') or info.get('filename') or info.get('video_path') or info.get('audio_path')
        if filename and Path(filename).exists():
            self.last_downloaded_file = str(filename)
            self.btn_open_file.setVisible(True)

        title = info.get('title', 'arquivo')
        self.log(f'✔ concluído com sucesso: {title}')

    @Slot(str)
    def _on_download_failed(self, error: str) -> None:
        self.btn_download.setEnabled(True)
        self.btn_download.setText(self.i18n('btn_download_now').lower())
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(False)
        self.btn_new_download.setVisible(True)
        self.btn_back_settings.setVisible(True)
        self.status_label.setText(self.i18n('status_failed').lower())
        self.status_dot.setStyleSheet('color: #EF4444; font-size: 13px;')
        self.log(f'✖ erro: {error}')

    # ------------------------------------------------------------------
    # drag & drop and key handling
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        mime = event.mimeData()
        text = mime.text().strip() if mime.hasText() else ''
        if mime.hasUrls() or text.startswith(('http://', 'https://')):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        mime = event.mimeData()
        url = ''
        if mime.hasUrls() and mime.urls():
            url = mime.urls()[0].toString()
        elif mime.hasText():
            url = mime.text().strip()
        if url.startswith(('http://', 'https://')):
            self._set_phase(PHASE_HOME)
            self.url_input.setText(url)
            event.acceptProposedAction()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.key() == Qt.Key.Key_Escape:
            if self.drawer.isVisible():
                self._close_drawer()
                return
            if self._phase == PHASE_CONFIGURE:
                self._go_home()
                return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        if getattr(self, 'drawer_overlay', None) is not None and self.drawer_overlay.isVisible():
            self.drawer_overlay.setGeometry(0, 0, self.width(), self.height())
            self.drawer.resize(self.drawer.width(), self.height())

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self.update_download_thread and self.update_download_thread.isRunning():
            self.update_download_thread.cancel()
            self.update_download_thread.wait(3000)
        if self.metadata_thread and self.metadata_thread.isRunning():
            self.metadata_thread.cancel()
            self.metadata_thread.wait(1000)
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.cancel()
            self.download_thread.wait(3000)
        super().closeEvent(event)


def run_gui(*, allow_update_check: bool = True, allow_multiple: bool = False) -> int:
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ytrivo.desktop.gui.1.2')
        except Exception:
            pass

    app = QApplication([])
    guard = None
    if not allow_multiple:
        guard = SingleInstanceGuard()
        if not guard.acquired:
            i18n = I18nManager()
            QMessageBox.information(
                None,
                i18n('app_title'),
                i18n('single_instance_message').lower(),
            )
            guard.release()
            return 0

    try:
        cleanup_update_cache()
        window = MainWindow(allow_update_check=allow_update_check)
        window.show()
        return app.exec()
    finally:
        if guard is not None:
            guard.release()
