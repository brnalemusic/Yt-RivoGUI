# Maintainers & Project Credits

## Lead Maintainer & Creator

### [Breno Alexandrē](https://github.com/brnalemusic)
* **Role**: Creator & Lead Maintainer of **Yt-RivoGUI**
* **Email**: `brenoalexandre.music@gmail.com`
* **Repository**: [https://github.com/brnalemusic/Yt-RivoGUI](https://github.com/brnalemusic/Yt-RivoGUI)
* **Contributions**:
  * Designed and developed the minimalist obsidian-and-emerald PySide6 graphical user interface.
  * Implemented 100% lowercase monospaced visual hierarchy, custom styling, and live terminal stream.
  * Added intelligent bilingual system locale detection (`pt_BR` / `en_US`) with runtime switcher.
  * Integrated automated YouTube JS challenge solving via `yt-dlp-ejs` and robust retry engine.
  * Created automated PyInstaller standalone single-file builds, SHA256 checksum generation, and test suites.

### Support & Sponsorship
If you find Yt-RivoGUI helpful and want to support its ongoing development:
* **Monthly Support (Brasil)**: [Apoiar no Brasil via InfinitePay (R$ 14,99/mês)](https://invoice.infinitepay.io/plans/brnale_music/bjLluwct3L)
* **GitHub Sponsors**: [github.com/sponsors/brnalemusic](https://github.com/sponsors/brnalemusic)

---

## Upstream Project & Credits

Yt-RivoGUI is powered by the open-source technologies of **[yt-dlp](https://github.com/yt-dlp/yt-dlp)**. We are immensely grateful to the `yt-dlp` maintainers, contributors, and the broader open-source community for their engineering excellence.

### Core Maintainers of yt-dlp

#### [coletdjnz](https://github.com/coletdjnz)
* Overhauled the networking stack and implemented support for `requests` and `curl_cffi` HTTP clients
* Reworked the plugin architecture across yt-dlp distributions
* Implemented support for external JavaScript runtimes/engines
* Maintains support for YouTube and various sites

#### [bashonly](https://github.com/bashonly)
* Rewrote and maintains build/release workflows and self-updater
* Overhauled external downloader cookie handling
* Co-implemented support for external JavaScript runtimes/engines
* Maintains support for YouTube, Vimeo, Twitter, TikTok, and other platforms

#### [Grub4K](https://github.com/Grub4K)
* Self-updater rewrite, release automation, core refactors
* Implemented proper progress reporting for parallel downloads
* Support for external JavaScript runtimes/engines

### yt-dlp Founders & Inactive Maintainers
* **[pukkandan](https://github.com/pukkandan)**: Founder of the yt-dlp fork, Lead Maintainer from 2021 to 2024.
* **[shirt](https://github.com/shirt-dev)**: Multithreading (`-N`) and aria2c fragment downloads.
* **[Ashish0804](https://github.com/Ashish0804)**: Broad site extractor support.
* **[sepro](https://github.com/seproDev)**: UX improvements and engine maintenance.

---

For full historical details and full list of upstream contributors, see the original [yt-dlp repository](https://github.com/yt-dlp/yt-dlp).
