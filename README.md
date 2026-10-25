<p align="center">
  <img src="app/assets/Yt-RivoGUI-Logo.png" width="160" alt="Yt-RivoGUI logo" />
</p>

<h1 align="center">yt-rivogui</h1>

<p align="center">
  <b>a feature-rich tool for downloading video and audio from any platform, featuring a graphical interface and powered by yt-dlp technology.</b><br>
  built with obsidian dark aesthetics, monospaced typography, and automatic youtube challenge solving.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.0.4.0-10B981?style=flat-square" alt="Version 0.0.4.0" />
  <img src="https://img.shields.io/badge/python-3.10%2B-22C55E?style=flat-square" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/framework-pyside6-34D399?style=flat-square" alt="PySide6" />
  <img src="https://img.shields.io/badge/platform-windows%20(10%20%2F%2011%20x64)-10B981?style=flat-square" alt="Platform" />
  <img src="https://img.shields.io/badge/license-unlicense-10B981?style=flat-square" alt="License" />
</p>

---

## overview

`yt-rivogui` is a standalone desktop media downloader embodying a full graphical edition of `yt-dlp` with the engine built directly into the application (no external `yt-dlp` installation or command-line setup required). designed exclusively for microsoft windows (windows 10 / 11 64-bit), it features a retro-minimalist dark slate interface, monospaced typography, segmented card navigation, and complete lowercase interface styling, delivering full control over downloads while keeping the interface distraction-free, elegant, and lightweight.

---

## key features

- **retro-minimalist dark design**: clean dark slate palette (`#0d1117`) with elevated card panels (`#161b22`), subtle borders (`#21262d`), and emerald green accents (`#238636`, `#34d399`).
- **100% lowercase & monospaced typography**: uniform lowercase visual aesthetic across all buttons, labels, and badges, paired with clean technical monospace fonts (`cascadia code`, `jetbrains mono`, `consolas`).
- **structured 3-zone card navigation**:
  - **source & destination**: glowing url bar with one-click paste/clear buttons and folder destination picker.
  - **detected media card**: centered preview with high-definition 16:9 thumbnail and metadata chips (channel, duration, playlist info).
  - **mode & settings deck**: segmented radio pills to switch between `vídeo`, `áudio`, `vídeo + áudio (separados)`, and `capa` (thumbnail only).
- **flexible media presets & codecs**:
  - **video**: `best`, `4k (2160p)`, `1440p`, `1080p`, `720p`, `480p`, `360p` (`mp4`, `mkv`, `webm`).
  - **audio**: `mp3`, `flac`, `m4a`, `wav`, `opus`, `aac`, `vorbis` with selectable quality bitrates (`best`, `320k`, `256k`, `192k`, `128k`).
  - **split download**: simultaneously extract high-definition video and separate audio track.
- **bilingual auto-detection**: automatically adapts to your system language:
  - brazilian portuguese (`pt_BR`) on portuguese environments.
  - american english (`en_US`) on all other system locales.
  - real-time live language switcher directly in the interface header.
- **branded windows installer**: per-user installation with no uac prompt, custom dark emerald artwork, start menu integration and a clean uninstaller.
- **verified automatic updates**: stable-channel update checks with sha-256 verification, a one-click update banner, and safe installed/portable update paths.
- **youtube js challenge solving**: built-in integration with `yt-dlp-ejs` to overcome recent youtube sabr/n-challenge restrictions and prevent connection timeouts (error -138).
- **automatic post-processing**:
  - thumbnail embedding into media files.
  - rich metadata and tag embedding (title, artist, album, upload date).
  - subtitle embedding with target language selection.
  - format conversion and remuxing via ffmpeg.
- **playlist intelligence**:
  - dedicated subfolder creation for playlists automatically named after playlist title.
- **real-time telemetry & collapsible logs**:
  - 4-column telemetry grid (progress %, speed, eta, file size).
  - collapsible detailed terminal logs with sanitized ansi formatting.

---

## installation & quickstart

### option a: windows installer (recommended for end users)

1. download `Yt-RivoGUI-Setup-v0.0.4.0.exe` from the official [releases](https://github.com/brnalemusic/Yt-RivoGUI/releases).
2. run the installer. it installs per user into `%LOCALAPPDATA%\Programs\Yt-RivoGUI` and does **not** require administrator rights (no uac prompt).
3. launch `yt-rivogui` from the start menu. setup also offers an optional desktop shortcut.

the installer registers the app in windows settings, so it can be removed from there at any time. installed builds update themselves automatically from github releases.

### option b: portable release

1. download either:
   - `Yt-RivoGUI-v0.0.4.0-windows.zip` (recommended; avoids browser heuristic download warnings).
   - `Yt-RivoGUI.exe` (direct standalone executable).
   from the official [releases](https://github.com/brnalemusic/Yt-RivoGUI/releases).
2. extract the `.zip` (if downloaded) and run `Yt-RivoGUI.exe` directly. no python or installation required. portable builds also update themselves in place.

> **tip**: `ffmpeg` and `ffprobe` are not bundled. install [ffmpeg](https://ffmpeg.org/download.html) and add it to your system `PATH` for video remuxing, subtitle embedding, and audio extraction.

### option c: run from source

clone the repository and install with the `gui` extra dependencies:

```bash
git clone https://github.com/brnalemusic/Yt-RivoGUI.git
cd Yt-RivoGUI

# install app and gui dependencies
pip install -e ".[gui]"

# launch the app
python -m app
```

source checkouts never replace their own files. when a new release exists, the update banner links to the releases page instead.

---

## automatic updates

the app checks the stable github release channel on startup (at most once every 12 hours) and whenever the version badge in the header is clicked. when a newer release is available, a banner shows the version and a link to the release notes.

- **installed builds** download the installer, verify its sha-256 digest and size, then run it silently after the app closes. the updater helper restarts the app on the new version.
- **portable builds** download the new executable, verify it, replace the current file through a detached powershell helper (with backup and rollback), and relaunch.
- **source checkouts** never self-update; the banner points to the releases page.
- an update is only executed when its sha-256 digest matches `latest.json`. older releases without a manifest fall back to the github api plus `SHA256SUMS.txt`. assets without a valid checksum are blocked.
- update checks and installs are blocked while a media download is running.

automatic checks can be disabled with the `check for updates automatically` toggle in the log panel. command-line equivalents:

```bash
# check github and print the result without opening the gui
python -m app --check-updates

# download, verify and install the latest release (packaged builds only)
python -m app --update-now

# start the gui without automatic update checks
python -m app --no-update-check
```

---

## building the windows executable and installer

the release pipeline uses pyinstaller for `Yt-RivoGUI.exe` and inno setup 6.7+ for the branded per-user installer.

prerequisites:

- python 3.10+ with the `gui` extra dependencies (includes `pillow` for the installer artwork).
- inno setup 6.7 or newer. `build_gui.py` looks for `ISCC.exe` on `PATH`, then `INNO_SETUP_COMPILER` / `ISCC`, then the default installation folders.

### windows powershell

```powershell
./build-gui.ps1
```

### windows command prompt

```cmd
build-gui.bat
```

### cross-platform (linux, macos, windows)

```bash
python devscripts/build_gui.py --require-installer
```

the build writes the following release artifacts to `dist/gui/`:

- `Yt-RivoGUI.exe` - portable single-file executable.
- `Yt-RivoGUI-v<version>-windows.zip` - portable archive with the executable, readme and license.
- `Yt-RivoGUI-Setup-v<version>.exe` - branded per-user installer.
- `SHA256SUMS.txt` - sha-256 checksums for every top-level release file.
- `latest.json` - update manifest consumed by the app.

`--no-installer` skips inno setup, while `--require-installer` fails the build when the compiler is unavailable. `--version <version>` overrides the version baked into the executable and installer.

to regenerate the checksums and manifest after replacing artifacts manually:

```bash
python devscripts/make_update_manifest.py --dist dist/gui --version 0.0.4.0 --tag 0.0.4.0
```

to regenerate only the installer artwork:

```bash
python devscripts/make_installer_assets.py
```

---

## automated build verification

to verify that your build output is valid, has correct sha256 hashes, contains the installer and manifest, and boots successfully:

```powershell
# powershell
./test-build.ps1

# cmd / batch
test-build.bat

# cross-platform python
python devscripts/test_build.py
```

add `--install-smoke` to perform a real silent install and uninstall in a temporary folder:

```bash
python devscripts/test_build.py --install-smoke
```

to build and test in a single command:

```powershell
./test-build.ps1 -Build
```

---

## versioning

`yt-rivogui` uses a four-part versioning format:

$$\text{version} = W.X.Y.Z$$

where:
- `W`: major architecture version
- `X`: minor feature version
- `Y`: patch / stability version
- `Z`: build / revision increment

### updating the version

to update the application version, run:

```bash
# using python directly
python devscripts/update-version.py 0.0.4.0

# or using the root helper
python update-version.py 0.0.4.0

# on powershell
./update-version.ps1 0.0.4.0
```

this atomically updates `app/__init__.py`, `yt_dlp/version.py`, and `README.md`. the version is displayed in the application header badge and build metadata, ensuring the app always presents the true release version rather than build timestamps.

---

## automated github releases

releases are automated via github actions (`.github/workflows/release.yml` and `build.yml`):

1. update version:
   ```bash
   python update-version.py 0.0.4.0
   git commit -am "release: version 0.0.4.0"
   ```
2. tag and push. stable tags use the plain four-part version, without a `v` prefix, because the update manifest and asset urls are generated from the tag:
   ```bash
   git tag 0.0.4.0
   git push origin master --tags
   ```
3. github actions builds `Yt-RivoGUI.exe`, the portable zip and the branded installer, computes sha-256 checksums, regenerates `latest.json` from the merged artifacts, and publishes everything to a new github release.

release assets:

- `Yt-RivoGUI-Setup-v<version>.exe`
- `Yt-RivoGUI.exe`
- `Yt-RivoGUI-v<version>-windows.zip`
- `SHA256SUMS.txt`
- `latest.json`

> **upgrading from 0.0.3.0 or older**: those releases did not ship `latest.json`, so install `0.0.4.0` manually once. every later release updates automatically.

---
 
## author & support

developed and maintained by **[Breno Alexandrē](https://github.com/brnalemusic)**.

- **monthly support (brasil)**: [apoiar via infinitepay (r$ 14,99/mês)](https://invoice.infinitepay.io/plans/brnale_music/bjLluwct3L)
- **github sponsors**: [github.com/sponsors/brnalemusic](https://github.com/sponsors/brnalemusic)
- **maintainers & credits**: see [Maintainers.md](Maintainers.md) for full credits to the upstream yt-dlp project.

---

## license

this project is licensed under the [unlicense](LICENSE).
