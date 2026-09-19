<p align="center">
  <img src="app/assets/Yt-RivoGUI-Logo.png" width="160" alt="Yt-RivoGUI logo" />
</p>

<h1 align="center">yt-rivogui</h1>

<p align="center">
  <b>a feature-rich tool for downloading video and audio from any platform, featuring a graphical interface and powered by yt-dlp technology.</b><br>
  built with obsidian dark aesthetics, monospaced typography, and automatic youtube challenge solving.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.0.3.0-10B981?style=flat-square" alt="Version 0.0.3.0" />
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

### option a: standalone release (recommended for end users)

1. download either:
   - `Yt-RivoGUI-v0.0.3.0-windows.zip` (recommended; avoids browser heuristic download warnings).
   - `Yt-RivoGUI.exe` (direct standalone executable).
   from the official [releases](https://github.com/brnalemusic/Yt-RivoGUI/releases).
2. extract the `.zip` (if downloaded) and run `Yt-RivoGUI.exe` directly. no python or installation required.

> **tip**: install [ffmpeg](https://ffmpeg.org/download.html) and add it to your system `PATH` for video remuxing and audio extraction.

### option b: run from source

clone the repository and install with the `gui` extra dependencies:

```bash
git clone https://github.com/brnalemusic/Yt-RivoGUI.git
cd Yt-RivoGUI

# install app and gui dependencies
pip install -e ".[gui]"

# launch the app
python -m app
```

---

## building standalone executables

`yt-rivogui` bundles into a standalone single-file binary using pyinstaller with all icons, assets, and solvers packaged inside.

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
python devscripts/build_gui.py
```

the built binary is generated under `dist/gui/` along with its `SHA256SUMS.txt` cryptographic verification file.

---

## automated build verification

to verify that your build output is valid, has correct sha256 hashes, and boots successfully:

```powershell
# powershell
./test-build.ps1

# cmd / batch
test-build.bat

# cross-platform python
python devscripts/test_build.py
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
python devscripts/update-version.py 0.0.1.0

# or using the root helper
python update-version.py 0.0.1.0

# on powershell
./update-version.ps1 0.0.1.0
```

this atomically updates `app/__init__.py`, `yt_dlp/version.py`, and `README.md`. the version is displayed in the application header badge and build metadata, ensuring the app always presents the true release version rather than build timestamps.

---

## automated github releases

releases are automated via github actions (`.github/workflows/release.yml` and `build.yml`):

1. update version:
   ```bash
   python update-version.py 0.0.1.0
   git commit -am "release: version 0.0.1.0"
   ```
2. tag and push:
   ```bash
   git tag v0.0.1.0
   git push origin master --tags
   ```
3. github actions will automatically build `Yt-RivoGUI.exe` for windows, compute sha256 checksums, and publish them to a new github release.

---
 
## author & support

developed and maintained by **[Breno Alexandrē](https://github.com/brnalemusic)**.

- **monthly support (brasil)**: [apoiar via infinitepay (r$ 14,99/mês)](https://invoice.infinitepay.io/plans/brnale_music/bjLluwct3L)
- **github sponsors**: [github.com/sponsors/brnalemusic](https://github.com/sponsors/brnalemusic)
- **maintainers & credits**: see [Maintainers.md](Maintainers.md) for full credits to the upstream yt-dlp project.

---

## license

this project is licensed under the [unlicense](LICENSE).
