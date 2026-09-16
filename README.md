<p align="center">
  <img src="app/assets/Yt-RivoGUI-Logo.png" width="160" alt="Yt-RivoGUI logo" />
</p>

<h1 align="center">yt-rivogui</h1>

<p align="center">
  <b>a feature-rich tool for downloading video and audio from any platform, featuring a graphical interface and powered by yt-dlp technology.</b><br>
  built with obsidian dark aesthetics, monospaced typography, and automatic youtube challenge solving.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.0.1.0-10B981?style=flat-square" alt="Version 0.0.1.0" />
  <img src="https://img.shields.io/badge/python-3.10%2B-22C55E?style=flat-square" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/framework-pyside6-34D399?style=flat-square" alt="PySide6" />
  <img src="https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macos-43F4B2?style=flat-square" alt="Platform" />
  <img src="https://img.shields.io/badge/license-unlicense-10B981?style=flat-square" alt="License" />
</p>

---

## overview

`yt-rivogui` is a standalone desktop application providing a streamlined graphical frontend for `yt-dlp`. designed around an obsidian-and-emerald minimalist theme, monospaced typography, and lowercase interface styling, it delivers full control over downloads while keeping the interface distraction-free and lightweight.

---

## key features

- **minimalist obsidian theme**: obsidian dark background (`#060809`) with lime and emerald green glowing accents (`#10B981`, `#22C55E`, `#43F4B2`).
- **100% monospaced typography**: clean technical font stack (`cascadia code`, `jetbrains mono`, `consolas`).
- **bilingual auto-detection**: automatically adapts to your system language:
  - brazilian portuguese (`pt_BR`) on portuguese environments.
  - american english (`en_US`) on all other system locales.
  - real-time live language switcher directly in the interface.
- **youtube js challenge solving**: built-in integration with `yt-dlp-ejs` to overcome recent youtube sabr/n-challenge restrictions and prevent connection timeouts (error -138).
- **flexible quality presets**:
  - `best` (highest available stream)
  - `4k (2160p)`, `1440p`, `1080p`, `720p`, `480p`
  - `audio only` (`mp3`, `flac`, `m4a`)
- **automatic post-processing**:
  - thumbnail embedding into video and audio files.
  - metadata and tag embedding (title, artist, album, upload date).
  - format conversion and remuxing via ffmpeg.
- **playlist intelligence**:
  - dedicated subfolder creation for playlists automatically named after playlist title.
- **live terminal output**:
  - real-time terminal display with sanitized ansi formatting.
  - download speed, estimated time remaining, and animated progress bar.

---

## installation & quickstart

### option a: standalone executable (recommended for end users)

1. download the latest `Yt-RivoGUI.exe` from [releases](https://github.com/brnalemusic/Yt-RivoGUI/releases).
2. run `Yt-RivoGUI.exe` directly. no python installation required.

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

this atomically updates `yt_dlp/version.py`, which is imported by `app` and displayed in the application header and build metadata.

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
3. github actions will automatically build `Yt-RivoGUI.exe` for windows and linux binaries, compute sha256 checksums, and publish them to a new github release.

---
 
## author & support

developed and maintained by **[Breno Alexandrē](https://github.com/brnalemusic)**.

- **monthly support (brasil)**: [apoiar via infinitepay (r$ 14,99/mês)](https://invoice.infinitepay.io/plans/brnale_music/bjLluwct3L)
- **github sponsors**: [github.com/sponsors/brnalemusic](https://github.com/sponsors/brnalemusic)
- **maintainers & credits**: see [Maintainers.md](Maintainers.md) for full credits to the upstream yt-dlp project.

---

## license

this project is licensed under the [unlicense](LICENSE).
