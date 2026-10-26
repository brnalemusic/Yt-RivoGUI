# Instructions for AI Agents & Assistants (AGENTS.md)

FIRST OF ALL:
If you are an AI agent about to make changes to the code, DO NOT MODIFY the rules in this `AGENTS.md` file. You are only permitted to edit section no. 6, provided it is relevant to your pre-coding context. You may modify the entire file—changing or removing existing rules—only when the user explicitly instructs you to alter the rules within this file. Never do so on your own initiative.

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
- **Logs are user-facing too**: `log_update_*` keys cover the updater log lines shown in the log panel; never leave a new log message hard-coded in only one language.
- Automated tests in `test/test_formats_and_split.py` enforce this key parity—never break this test. `test/test_update_ui.py` verifies the update banner in both languages.
- The Inno Setup script ([`installer/Yt-RivoGUI.iss`](file:///c:/Users/Breno/Documents/Code/Yt-RivoGUI/installer/Yt-RivoGUI.iss)) has its own bilingual `[Messages]` and `[CustomMessages]` sections; every added installer string must be lowercase and present for both `en` and `pt`.

---

## 4. Mandatory Lowercase UI Aesthetic

- The application uses a minimalist, modern monospace design system.
- **All UI text, button labels, combobox items, placeholders, tooltips, and status messages MUST be in lowercase.**
  - Examples: `iniciar download`, `save to:`, `vídeo`, `audio codec:`, `baixando arquivo...`, `ready to download`.
  - **Do NOT** use Title Case, PascalCase, or sentence-initial capital letters in user-facing UI text unless referring to proper technical acronyms (e.g., `4k`, `1080p`, `mp4`, `mkv`, `wav`, `pcm`, `ffmpeg`, `v0.0.4.0`).
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

- **`yt_dlp/`**:
  - Vendored upstream yt-dlp engine, currently synchronized with the stable `2026.10.21` release (see section 9).
  - Supplies extractors, networking, format selection, downloaders, and post-processors. Backend improvements from upstream are adopted here; GUI behavior belongs in `app/`.
- **`app/backend.py`**:
  - Core embedded media downloader backend running yt-dlp technology natively in-process (not an external CLI wrapper; no separate yt-dlp installation needed).
  - Houses `DownloadOptions`, `ProgressInfo`, and `YtDLBackend`.
  - Configures download pipelines, format selection, output templates, and FFmpeg postprocessors (`FFmpegExtractAudio`, `FFmpegMetadata`, `FFmpegEmbedSubtitle`, `EmbedThumbnail`).
  - Implements modes: `video`, `audio`, `split` (video + audio separated), and `thumbnail_only`.
- Derives the quality choices from the detected streams (`available_video_heights`, `available_video_fps`, `available_video_bitrates`, `available_audio_bitrates`, `available_audio_sample_rates`) and turns them into yt-dlp format filters (`build_video_format_expression`) for resolution, frame rate, `h.264`/`h.265` codec, video bitrate and the embedded audio bitrate/sample rate. No transcode: every choice selects or caps a stream the site already serves, with a fallback ladder.
  - Detects installer-provided media tools in `<exe dir>\bin` (or `<repo>\bin` for source checkouts), prepends that folder to `PATH`, passes it to yt-dlp as `ffmpeg_location`, and uses the local binary for `_strip_audio`.
- **`app/gui.py`**:
  - PySide6 desktop interface.
  - Uses `MINIMAL_MONO_STYLESHEET` for consistent dark monospace styling.
  - Multi-threaded background execution via `MetadataWorker`, `DownloadWorker`, `UpdateCheckWorker` and `UpdateDownloadWorker`.
  - Reactive language switching with `apply_translations()`.
  - Hosts the update banner, clickable version badge, `check for updates automatically` toggle, and the `SingleInstanceGuard` mutex in `run_gui()`.
- **`app/updater.py`**:
  - Qt-free update engine used by the GUI, `--check-updates`, `--update-now` and the tests.
  - Reads the stable GitHub release channel through `latest.json`; older releases fall back to the GitHub API plus `SHA256SUMS.txt`.
  - Verifies every download by size and SHA-256 before execution; missing checksums are a hard failure.
  - Installed builds run the downloaded Inno installer silently through a detached PowerShell helper. Portable builds replace their own `.exe` with backup/rollback and relaunch. Source checkouts never self-update.
  - Persists `UpdateSettings` in `%LOCALAPPDATA%\Yt-RivoGUI\settings.json` and update logs in `updater.log`.
- **`app/i18n.py`**:
  - `I18nManager` class and `TRANSLATIONS` mapping.
  - OS-level language detection (`detect_system_language()`).
- **`installer/`**:
  - `Yt-RivoGUI.iss` builds the branded per-user Inno Setup installer (`PrivilegesRequired=lowest`, fixed `AppId=Yt-RivoGUI`, uninstall key `Yt-RivoGUI_is1`).
  - When `ffmpeg.exe` and `ffprobe.exe` are absent from `{app}\bin` and `PATH`, the installer downloads the official gyan.dev ffmpeg essentials `.7z` during the download stage, fetches its SHA-256 sidecar, verifies the archive, extracts only both executables into `{app}\bin`, and removes that folder on uninstall. Failures, cancelled downloads and offline installs log and continue; installation never depends on the download.
  - The download honours `YTRIVO_FFMPEG_URL`, `YTRIVO_FFMPEG_CHECKSUM_URL`, `YTRIVO_FFMPEG_SHA256`, `YTRIVO_FFMPEG_FORCE=1` and `YTRIVO_SKIP_FFMPEG=1` for offline testing.
  - `assets/` holds generated wizard artwork; regenerate it with `devscripts/make_installer_assets.py`.
- **`devscripts/`**:
  - `build_gui.py` runs PyInstaller, creates the portable zip, compiles the installer, and writes `latest.json` plus `SHA256SUMS.txt`.
  - `make_update_manifest.py` and `generate_release_hashes.py` own the release checksum/manifest format.
  - `test_build.py` verifies the executable, zip, installer, manifest and (with `--install-smoke`) a real silent install/uninstall. The smoke test serves a synthetic `.7z` over loopback HTTP to verify download, SHA-256 checking, extraction, `{app}\bin` placement, reuse on a second run and uninstall cleanup offline.
- **`test/`**:
  - Automated test suite covering versioning, backend options, media stream processing, translation parity, the update engine, and the update UI.
- **`.github/workflows/`**:
  - `build.yml` builds and verifies the Windows GUI artifacts and requires Inno Setup 6.7+.
  - `release.yml` regenerates `latest.json` and `SHA256SUMS.txt` from the merged release artifacts before publishing.

---

## 7. Verification & Testing Protocol

Before finishing any task, run the test suites to ensure zero regressions:

```powershell
# 1. Run unit tests (including the updater and update UI suites)
pytest test/test_formats_and_split.py test/test_gui_versioning.py test/test_updater.py test/test_update_ui.py -v

# 2. Verify application import and startup check
python -m app --test-startup

# 3. Verify the live update channel responds (network required)
python -m app --check-updates
```

When changing packaging, installer artwork, the update manifest, or the release workflows, also run:

```powershell
# 4. Full Windows build, including the branded installer
python devscripts/build_gui.py --require-installer

# 5. Verify the exe, zip, installer and latest.json
python devscripts/test_build.py

# 6. Optional but recommended: real silent install/uninstall in a temp folder,
#    including a synthetic ffmpeg download/extraction check over loopback
python devscripts/test_build.py --install-smoke
```

Inno Setup 6.7+ is required for step 4. `build_gui.py` finds `ISCC.exe` on `PATH`, via `INNO_SETUP_COMPILER` / `ISCC`, or in the `Inno Setup 6` / `Inno Setup 7` folders under `Program Files`, `Program Files (x86)` and `%LOCALAPPDATA%\Programs`.

Install Inno Setup from the [jrsoftware GitHub releases](https://github.com/jrsoftware/issrc/releases): since March 2026 the `files.jrsoftware.org` installer links only serve `.issig` signatures, so the old `https://files.jrsoftware.org/is/6/innosetup-*.exe` URLs return 404. The Windows build job in `build.yml` installs the pinned 6.7.3 release asset only when no `ISCC.exe` exists, verifies its SHA-256 before running it, and falls back to the newest published release (verifying the checksum GitHub reports for that asset). Never reintroduce a hard-coded jrsoftware FTP/HTTPS installer URL.

To verify the real gyan.dev download manually, run the built installer silently with `YTRIVO_FFMPEG_FORCE=1` and confirm `{app}\bin\ffmpeg.exe` and `{app}\bin\ffprobe.exe` exist before uninstalling. Never treat the live download as a required CI step.

---

## 8. Release & Update Invariants

- **Distribution model**: keep the branded per-user installer (no UAC) and the portable `.exe` / `.zip` side by side. `ffmpeg` and `ffprobe` are never bundled in build artifacts. The installer may download the official gyan.dev build into `{app}\bin` at install time after verifying its SHA-256; skip when both tools already exist in `{app}\bin` or on `PATH`, and never abort the install when the download fails.
- **Release tags**: stable releases use the plain four-part version (`0.0.4.0`, no `v` prefix). `latest.json` asset URLs and the updater are generated from that tag.
- **Release trigger**: pushing a four-part numeric tag starts `.github/workflows/release.yml` (`on: push: tags`). The filter must stay on plain `*` wildcards — the documented `+`/`?` quantifiers are unreliable in tag filters. A `prepare` guard aborts the run when the tag does not match `__version__` in `app/__init__.py`, so the version bump must land before the tag. `workflow_dispatch` with `version` and `target` set to the tag remains the supported fallback (and is the only path when the tag already exists remotely).
- **Release assets**: `Yt-RivoGUI-Setup-v<version>.exe`, `Yt-RivoGUI.exe`, `Yt-RivoGUI-v<version>-windows.zip`, `SHA256SUMS.txt`, `latest.json`.
- **Checksum policy**: `SHA256SUMS.txt` excludes `latest.json` and itself. `latest.json` carries the checksum of `SHA256SUMS.txt` plus the size and SHA-256 of every installable asset. Never weaken the rule that an asset without a valid checksum must not be executed.
- **Installed vs portable**: installed builds update by running the downloaded installer silently; portable builds replace their own executable through the PowerShell helper. Source checkouts must never self-update.
- **Identity**: do not change `AppId=Yt-RivoGUI` or the uninstall registry key `Software\Microsoft\Windows\CurrentVersion\Uninstall\Yt-RivoGUI_is1`; the updater and the installer rely on them.
- **Single instance**: the GUI owns the `Yt-RivoGUI.SingleInstance` mutex. The Inno script uses the same `AppMutex`, and the silent updater passes `/CLOSEAPPLICATIONS`. Keep `--allow-multiple` available for development.
- **Updater logging and errors**: every new update state, error code, or log line must exist in both `pt_BR` and `en_US`, in lowercase, and be covered by `test/test_update_ui.py` or `test/test_updater.py`.

---

## 9. Upstream Synchronization Policy (yt-dlp → Yt-RivoGUI)

- **What upstream is**: Yt-RivoGUI embeds and extends the yt-dlp engine. yt-dlp is deliberately a command-line tool; Yt-RivoGUI is its graphical edition. Never reduce the GUI to a thin CLI wrapper or replace RivoGUI behavior with upstream CLI behavior.
- **What to adopt**: adopt only new technologies and real improvements involving yt-dlp (extractors, networking, download pipeline, post-processors, security/dependency fixes, and runtime compatibility). Avoid merges with extraordinary conflicts; prefer small, reviewable syncs.
- **Conflict priority**: RivoGUI technology always wins. When resolving a merge or loading the upstream, prioritize our improved or invented technologies. From upstream, keep only real improvements and new backend technology relevant to the dlp engine.
- **Interesting new technology**: if upstream adds a very interesting technology, adapt it from the CLI model to the GUI model, document it in `README.md`, and report it to the maintainer at the end of the task. This is explicitly encouraged.

### operational protocol

1. Run `git fetch upstream --tags --prune` and compare `HEAD...upstream/master`; record the upstream release or tag being adopted.
2. Inspect conflicts with `git merge-tree` or start a `git merge --no-commit --no-ff upstream/master`. Never commit or push (section 1).
3. Keep RivoGUI-owned files (`app/`, `installer/`, GUI workflows, `README.md`, `AGENTS.md`, translations, and the update engine) on our side. Take upstream for `yt_dlp/` and backend tooling unless it breaks the GUI.
4. Preserve the RivoGUI version in `yt_dlp/version.py`; never replace it with yt-dlp's date-based version.
5. Resolve every conflict by inspecting both sides; do not accept an upstream hunk blindly when it touches a RivoGUI-owned behavior.
6. Run the full verification protocol (section 7) plus `pytest devscripts/setup_variables_tests.py`.
7. Update the upstream synchronization section in `README.md` with the synced release and the adopted technology, then report the same summary to the maintainer.

