import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BUILD_WORKFLOW = ROOT_DIR / '.github' / 'workflows' / 'build.yml'


def _ensure_inno_step() -> str:
    """Returns the text of the "Ensure Inno Setup" step of the windows build job."""
    text = BUILD_WORKFLOW.read_text(encoding='utf-8')
    match = re.search(r'^      - name: Ensure Inno Setup.*?(?=^      - name: )', text, re.MULTILINE | re.DOTALL)
    assert match, 'the windows build job must keep an "Ensure Inno Setup" step'
    return match.group(0)


def test_inno_setup_is_downloaded_from_github_releases():
    step = _ensure_inno_step()
    # jrsoftware retired the files.jrsoftware.org installer links in March 2026; only the
    # *.issig signatures remain there, so any such download URL returns 404.
    assert not re.search(r'https?://files\.jrsoftware\.org', step)
    assert 'github.com/jrsoftware/issrc/releases/download/' in step
    assert 'https://api.github.com/repos/jrsoftware/issrc/releases/latest' in step


def test_inno_setup_download_is_checksum_verified():
    step = _ensure_inno_step()
    assert 'Get-FileHash' in step
    assert re.search(r'\$pinnedSha256 = "[0-9a-f]{64}"', step)
    assert 'SHA-256 mismatch' in step
    # A missing checksum must fail the build instead of running an unverified installer.
    assert 'no SHA-256 checksum available' in step


def test_inno_setup_step_supports_both_compiler_majors():
    step = _ensure_inno_step()
    assert 'Inno Setup *' in step
    assert 'INNO_SETUP_COMPILER' in step
