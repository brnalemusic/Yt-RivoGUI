# Instructions for AI Agents & Assistants (AGENTS.md)

This repository contains **Yt-RivoGUI**, a minimalist, dark-themed desktop media downloader built with Python, PySide6 (Qt for Python), FFmpeg, and yt-dlp technology.

Any AI assistant or autonomous agent working on this codebase **must strictly comply** with the following rules:

---

## 1. Absolute Prohibition: NEVER Commit Changes

- **DO NOT run `git commit` or `git push` under any circumstance.**
- You may inspect git status (`git status`, `git diff`, `git log`), but you must never stage or commit changes to git.
- Committing and pushing changes is reserved exclusively for the human maintainer.

---

## 2. Mandatory Implementation Plan Before Action

- **Always formulate and present a clear Implementation Plan before making modifications.**
- Before editing or writing code for non-trivial tasks:
  1. Inspect and research the affected modules.
  2. Clearly outline the proposed approach, file modifications, architecture impacts, and edge cases.
  3. Detail the verification/testing steps.
  4. Obtain the user's approval before modifying files.

---

## 3. Strict Bilingual UI/UX Support (pt_BR and en_US)

- Every user-facing string added or modified in the application **must be translated into both supported languages**:
  - **Portuguese (`pt_BR`)**
  - **English (`en_US`)**
- Location: [`app/i18n.py`](file:///c:/Users/Breno/Documents/Code/Yt-RivoGUI/app/i18n.py) in the `TRANSLATIONS` dictionary.
- **Key Parity**: Both language dictionaries must retain 100% key parity at all times (every key present in `pt_BR` must exist in `en_US` and vice-versa).
- Automated tests in `test/test_formats_and_split.py` enforce this key parity—never break this test.

---

## 4. Mandatory Lowercase UI Aesthetic

- The application uses a minimalist, modern monospace design system.
- **All UI text, button labels, combobox items, placeholders, tooltips, and status messages MUST be in lowercase.**
  - Examples: `iniciar download`, `save to:`, `vídeo`, `audio codec:`, `baixando arquivo...`, `ready to download`.
  - **Do NOT** use Title Case, PascalCase, or sentence-initial capital letters in user-facing UI text unless referring to proper technical acronyms (e.g., `4k`, `1080p`, `mp4`, `mkv`, `wav`, `pcm`, `ffmpeg`, `v0.0.1.0`).
  - In `app/gui.py`, all dynamically rendered texts should call `.lower()` on translated strings (e.g., `self.i18n('key').lower()`).

---

## 5. Mandatory Documentation Synchronization (README.md, Guides & Docstrings)

- **Always inspect and update project documentation whenever making code, architecture, or feature changes.**
- Whenever an AI assistant or agent:
  - Modifies, adds, or refactors features, UI options, CLI flags, or application behavior;
  - Updates, embeds, removes, or replaces libraries, technologies, or dependencies;
  - Changes versioning patterns, packaging workflows, build scripts, or GitHub Actions pipelines;
- The agent **MUST proactively review and update all relevant documentation**:
  - **`README.md`**: Ensure descriptions, feature lists, quickstart guides, installation steps, build instructions, and versioning guides faithfully match the current code state.
  - **No Obsolete Information**: Never leave stale or conflicting text describing old technologies, outdated command syntax, or removed dependencies that the AI has changed or replaced.
  - **Docstrings & Comments**: Update function/class docstrings and architectural notes to accurately reflect any new mechanisms or behavior.
  - **Mandatory Final Review**: Before declaring any task complete, perform a targeted check across documentation files to guarantee 100% synchronization.

---

## 6. Codebase Architecture Overview

- **`app/backend.py`**:
  - Core embedded media downloader backend running yt-dlp technology natively in-process (not an external CLI wrapper; no separate yt-dlp installation needed).
  - Houses `DownloadOptions`, `ProgressInfo`, and `YtDLBackend`.
  - Configures download pipelines, format selection, output templates, and FFmpeg postprocessors (`FFmpegExtractAudio`, `FFmpegMetadata`, `FFmpegEmbedSubtitle`, `EmbedThumbnail`).
  - Implements modes: `video`, `audio`, `split` (video + audio separated), and `thumbnail_only`.
- **`app/gui.py`**:
  - PySide6 desktop interface.
  - Uses `MINIMAL_MONO_STYLESHEET` for consistent dark monospace styling.
  - Multi-threaded background execution via `MetadataWorker` and `DownloadWorker`.
  - Reactive language switching with `apply_translations()`.
- **`app/i18n.py`**:
  - `I18nManager` class and `TRANSLATIONS` mapping.
  - OS-level language detection (`detect_system_language()`).
- **`test/`**:
  - Automated test suite covering versioning, backend options, media stream processing, and translation parity.

---

## 7. Verification & Testing Protocol

Before finishing any task, run the test suites to ensure zero regressions:

```powershell
# 1. Run unit tests
pytest test/test_formats_and_split.py test/test_gui_versioning.py -v

# 2. Verify application import and startup check
python -m app --test-startup
```

