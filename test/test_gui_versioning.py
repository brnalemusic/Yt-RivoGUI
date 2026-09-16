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
