import re

from devscripts.utils import calculate_version


def test_calculate_version_accepts_four_part_numeric_versions():
    for version in ('1.0.354.2', '2025.09.15.42', '0.9.0.1'):
        assert calculate_version(version) == version
        assert re.fullmatch(r'\d+\.\d+\.\d+\.\d+', version)


def test_calculate_version_keeps_auto_generated_release_shape():
    version = calculate_version('2025.09.15.42')
    assert version == '2025.09.15.42'
    assert re.fullmatch(r'\d+\.\d+\.\d+\.\d+', version)


def test_calculate_version_strips_v_prefix():
    for raw, expected in (('v0.0.3.0', '0.0.3.0'), ('v0.0.4.0', '0.0.4.0'), ('V1.2.3.4', '1.2.3.4'), ('  v0.9.1.0  ', '0.9.1.0')):
        assert calculate_version(raw) == expected


def test_calculate_version_default_returns_real_app_version_not_date():
    from app import __version__
    assert calculate_version() == __version__
    assert calculate_version('') == __version__
    assert calculate_version(None) == __version__


def test_backend_uses_embedded_engine():
    import app.backend
    import yt_dlp
    assert hasattr(yt_dlp, 'YoutubeDL')
    backend = app.backend.YtDLBackend()
    assert backend is not None

