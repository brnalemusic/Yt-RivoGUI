"""Central stylesheet for the Yt-RivoGUI interface.

Holds the ``MINIMAL_MONO_STYLESHEET`` applied to the main window plus every
component class used by the guided-flow redesign (hero, stepper, accordion
sections, drawer).  Design tokens are documented below and must stay in sync
with the minimalist dark monospace identity:

    bg            #0d1117   surface         #161b22   surface-deep   #10161d
    border        #21262d   border-strong   #30363d
    text          #f0f6fc   text-secondary  #c9d1d9   text-muted     #8b949e
    accent        #34d399   accent-strong   #238636   accent-press   #19692c
    danger        #f85149   warning         #f59e0b
    radius-small  6px       radius-medium   8px       radius-pill    12px+
"""

MINIMAL_MONO_STYLESHEET = """
* {
    font-family: 'Cascadia Code', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
}

QMainWindow, QWidget#CentralWidget, QWidget#ScrollContent, QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: #0d1117;
}

QScrollArea {
    background-color: #0d1117;
    border: none;
}
QScrollBar:vertical {
    background-color: #0d1117;
    width: 6px;
    border-radius: 3px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #21262d;
    min-height: 24px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background-color: #34d399;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* CARDS */
QFrame.Card {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
}
QFrame.Card:hover {
    border-color: #30363d;
}

/* NESTED / INNER BOXES */
QFrame.InnerBox {
    background-color: #0d1117;
    border: 1px solid #21262d;
    border-radius: 6px;
}

/* INPUTS */
QLineEdit {
    background-color: #0d1117;
    color: #f0f6fc;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 7px 12px;
    selection-background-color: #238636;
    selection-color: #ffffff;
}
QLineEdit:focus {
    border: 1px solid #238636;
    background-color: #0f141c;
}
/* url shell: the input box frame, with a paste icon inside it */
QFrame#UrlShell {
    background-color: #0d1117;
    border: 1px solid #238636;
    border-radius: 8px;
}
QFrame#UrlShell[focused='true'] {
    border: 1px solid #34d399;
    background-color: #0f141c;
}
QLineEdit#UrlInput {
    background-color: transparent;
    color: #f0f6fc;
    border: none;
    border-radius: 0px;
    padding: 10px 4px 10px 10px;
    min-height: 22px;
    font-size: 13px;
}
QLineEdit#UrlInput:focus {
    border: none;
    background-color: transparent;
}
QPushButton#PasteIconButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 0px;
    font-size: 13px;
}
QPushButton#PasteIconButton:hover {
    background-color: #161b22;
}
QPushButton#PasteIconButton:pressed {
    background-color: #21262d;
}

/* COMBOBOX */
QComboBox {
    background-color: #0d1117;
    color: #f0f6fc;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 20px;
}
QComboBox:hover {
    border-color: #30363d;
}
QComboBox:focus {
    border-color: #238636;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
}
QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #f0f6fc;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #238636;
    selection-color: #ffffff;
}
QComboBox#LangCombo {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 3px 12px;
    font-size: 11px;
}
QComboBox#LangCombo:hover {
    border-color: #34d399;
}

/* BUTTONS */
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #30363d;
    border-color: #484f58;
    color: #ffffff;
}
QPushButton:pressed {
    background-color: #161b22;
}
QPushButton:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

/* PRIMARY BUTTON (MINT / EMERALD ACCENT) */
QPushButton#PrimaryButton {
    background-color: #238636;
    color: #040906;
    border: 1px solid #34d399;
    border-radius: 6px;
    padding: 7px 22px;
    font-weight: 700;
}
QPushButton#PrimaryButton:hover {
    background-color: #2ea043;
    border-color: #3fb950;
    color: #ffffff;
}
QPushButton#PrimaryButton:pressed {
    background-color: #19692c;
    color: #ffffff;
}
QPushButton#PrimaryButton:disabled {
    background-color: #13251a;
    border-color: #1a3c26;
    color: #234b32;
}
QPushButton#PrimaryButton[big='true'] {
    padding: 10px 26px;
    font-size: 13px;
}
QPushButton#PrimaryButton[loading='true'] {
    background-color: #13251a;
    border-color: #238636;
    color: #34d399;
}

/* CANCEL BUTTON */
QPushButton#CancelButton {
    background-color: #251216;
    color: #f85149;
    border: 1px solid #4a1d24;
    border-radius: 6px;
    padding: 7px 18px;
}
QPushButton#CancelButton:hover {
    background-color: #2f171c;
    border-color: #da3633;
    color: #ffffff;
}

/* GHOST BUTTON (subtle secondary actions) */
QPushButton#GhostButton {
    background-color: transparent;
    color: #8b949e;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton#GhostButton:hover {
    color: #ffffff;
    border-color: #34d399;
    background-color: #12301f;
}
QPushButton#GhostButton:disabled {
    color: #484f58;
    border-color: #21262d;
    background-color: transparent;
}

/* HAMBURGER / MENU BUTTON */
QPushButton#MenuButton {
    background-color: transparent;
    border: none;
    color: #c9d1d9;
    font-size: 15px;
    padding: 4px 8px;
}
QPushButton#MenuButton:hover {
    color: #34d399;
}

/* SEGMENTED TAB RADIO BUTTONS */
QRadioButton {
    color: #8b949e;
    spacing: 6px;
    padding: 6px 14px;
    background-color: #0d1117;
    border: 1px solid #21262d;
    border-radius: 6px;
    font-weight: 500;
}
QRadioButton:hover {
    color: #f0f6fc;
    border-color: #30363d;
    background-color: #161b22;
}
QRadioButton:checked {
    color: #34d399;
    background-color: #0e2a1d;
    border: 1px solid #238636;
    font-weight: 600;
}
QRadioButton::indicator {
    width: 8px;
    height: 8px;
    border-radius: 4px;
    border: 1px solid #30363d;
    background-color: #0d1117;
}
QRadioButton::indicator:checked {
    border-color: #34d399;
    background-color: #34d399;
}

/* CHECKBOX */
QCheckBox {
    color: #c9d1d9;
    spacing: 8px;
}
QCheckBox:hover {
    color: #f0f6fc;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid #30363d;
    background-color: #0d1117;
}
QCheckBox::indicator:hover {
    border-color: #34d399;
}
QCheckBox::indicator:checked {
    border-color: #34d399;
    background-color: #238636;
}

/* PROGRESS BAR */
QProgressBar {
    background-color: #0d1117;
    border: 1px solid #21262d;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #238636, stop:1 #34d399);
    border-radius: 2px;
}
QProgressBar#MainProgress {
    background-color: #0d1117;
    border: 1px solid #21262d;
    border-radius: 4px;
    min-height: 10px;
    max-height: 10px;
    text-align: center;
    color: transparent;
}
QProgressBar#MainProgress::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #238636, stop:1 #34d399);
    border-radius: 3px;
}

/* METRICS */
QFrame.MetricBox {
    background-color: transparent;
    border: none;
    border-right: 1px solid #21262d;
    padding-right: 12px;
}
QFrame.MetricBoxLast {
    background-color: transparent;
    border: none;
}

/* LOG VIEW */
QTextEdit#LogView {
    background-color: #07090c;
    color: #34d399;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 10px;
    font-size: 11px;
    line-height: 1.45;
}

/* LABELS & TYPOGRAPHY */
QLabel {
    color: #c9d1d9;
}
QLabel#AppTitle {
    color: #ffffff;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: -0.5px;
}
QLabel#AppSubtitle {
    color: #34d399;
    font-size: 11px;
}
QLabel#SecondaryText {
    color: #8b949e;
    font-size: 11px;
}
QLabel#SectionHeader {
    color: #34d399;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QLabel#MetricValue {
    color: #f0f6fc;
    font-size: 13px;
    font-weight: 600;
}
QLabel#MetricLabel {
    color: #8b949e;
    font-size: 10px;
}
QPushButton#VersionBadge {
    background-color: #0e2a1d;
    color: #34d399;
    border: 1px solid #238636;
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 10px;
    font-weight: 600;
}
QPushButton#VersionBadge:hover {
    background-color: #123d29;
    border-color: #34d399;
    color: #ffffff;
}
QPushButton#VersionBadge:pressed {
    background-color: #0b2016;
}
QPushButton#VersionBadge:disabled {
    color: #2f6b4c;
    border-color: #1a3c26;
}

/* HERO (HOME PHASE) */
QLabel#HeroTitle {
    color: #ffffff;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.5px;
}
QLabel#HeroHint {
    color: #8b949e;
    font-size: 11px;
}
QPushButton#SaveToButton {
    background-color: transparent;
    border: none;
    color: #8b949e;
    font-size: 11px;
    padding: 4px 8px;
}
QPushButton#SaveToButton:hover {
    color: #34d399;
}

/* STEPPER (GUIDED FLOW) */
QLabel#StepDot {
    color: #484f58;
    font-size: 11px;
}
QLabel#StepDotDone {
    color: #238636;
    font-size: 11px;
}
QLabel#StepDotActive {
    color: #34d399;
    font-size: 12px;
}
QLabel#StepText {
    color: #8b949e;
    font-size: 11px;
}
QLabel#StepTextActive {
    color: #f0f6fc;
    font-size: 11px;
    font-weight: 700;
}
QFrame#StepLine {
    background-color: #21262d;
    border: none;
}

/* ACCORDION SECTIONS (CONFIGURE PHASE) */
QFrame#SectionCard {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
}
QFrame#SectionCard:hover {
    border-color: #30363d;
}
QFrame#SectionHead {
    background-color: transparent;
    border: none;
}
QFrame#SectionHead:hover {
    background-color: rgba(48, 54, 61, 0.30);
    border-radius: 7px;
}
QLabel#SectionArrow {
    color: #484f58;
    font-size: 11px;
}
QLabel#SectionName {
    color: #8b949e;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QLabel#SectionValue {
    color: #34d399;
    font-size: 12px;
    font-weight: 600;
}
QWidget#SectionContent {
    background-color: transparent;
}

/* ACTION BAR (BOTTOM OF CONFIGURE PHASE) */
QFrame#ActionBar {
    background-color: transparent;
    border-top: 1px solid #21262d;
}

/* PREVIEW CARD PIECES */
QLabel#PreviewTitle {
    color: #f0f6fc;
    font-size: 13px;
    font-weight: 600;
}
QLabel#ThumbBox {
    background-color: #0d1117;
    border: 1px solid #21262d;
    border-radius: 6px;
    color: #484f58;
    font-size: 11px;
}

/* DRAWER (HAMBURGER SIDEBAR) */
QFrame#DrawerOverlay {
    background-color: rgba(1, 4, 9, 140);
}
QFrame#DrawerFrame {
    background-color: #10161d;
    border-right: 1px solid #21262d;
}
QLabel#DrawerBrand {
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: -0.3px;
}
QLabel#DrawerGroup {
    color: #34d399;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    padding: 12px 8px 3px 8px;
}
QPushButton#DrawerItem {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #c9d1d9;
    text-align: left;
    padding: 8px 10px;
    font-size: 12px;
}
QPushButton#DrawerItem:hover {
    background-color: #161b22;
    color: #ffffff;
}
QLabel#DrawerVersion {
    color: #484f58;
    font-size: 10px;
    padding: 6px 8px;
}

/* UPDATE BANNER */
QFrame#UpdateBanner {
    background-color: #0e2a1d;
    border: 1px solid #238636;
    border-radius: 8px;
}
QLabel#UpdateTitle {
    color: #f0f6fc;
    font-size: 13px;
    font-weight: 700;
}
QLabel#UpdateDetail {
    color: #8b949e;
    font-size: 11px;
}
QPushButton#UpdateGhost {
    background-color: transparent;
    color: #8b949e;
    border: 1px solid #30363d;
    border-radius: 5px;
    padding: 4px 10px;
    font-size: 11px;
}
QPushButton#UpdateGhost:hover {
    color: #ffffff;
    border-color: #34d399;
    background-color: #12301f;
}
QProgressBar#UpdateProgress {
    background-color: #07120c;
    border: 1px solid #1a3c26;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}
"""
