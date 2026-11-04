from __future__ import annotations

import json
from pathlib import Path
from app.history import DownloadHistoryManager, MAX_HISTORY_ITEMS
from app.i18n import TRANSLATIONS


def test_history_manager_crud(tmp_path: Path):
    history_file = tmp_path / 'history.json'
    manager = DownloadHistoryManager(history_file)

    # Initial state should be empty
    assert manager.load() == []

    # Add entry
    e1 = manager.add_entry(
        title='Test Video 1',
        url='https://example.com/v1',
        file_path=str(tmp_path / 'v1.mp4'),
        mode='video',
        file_size='12.5 mb',
    )

    assert e1['title'] == 'Test Video 1'
    assert e1['url'] == 'https://example.com/v1'
    assert e1['file_path'] == str(tmp_path / 'v1.mp4')
    assert e1['mode'] == 'video'
    assert e1['file_size'] == '12.5 mb'
    assert 'id' in e1
    assert 'timestamp' in e1

    items = manager.load()
    assert len(items) == 1
    assert items[0]['id'] == e1['id']

    # Add second entry (should be top)
    e2 = manager.add_entry(
        title='Test Video 2',
        url='https://example.com/v2',
        file_path=str(tmp_path / 'v2.mp4'),
        mode='audio',
        file_size='3.2 mb',
    )
    items = manager.load()
    assert len(items) == 2
    assert items[0]['id'] == e2['id']

    # Remove item
    removed = manager.remove_entry(e1['id'])
    assert removed is True
    items = manager.load()
    assert len(items) == 1
    assert items[0]['id'] == e2['id']

    # Remove invalid item
    assert manager.remove_entry('non-existent-id') is False

    # Clear all
    manager.clear_all()
    assert manager.load() == []


def test_history_manager_truncation(tmp_path: Path):
    history_file = tmp_path / 'history.json'
    manager = DownloadHistoryManager(history_file)

    for i in range(MAX_HISTORY_ITEMS + 50):
        manager.add_entry(
            title=f'Video {i}',
            url=f'https://example.com/{i}',
            file_path=str(tmp_path / f'{i}.mp4'),
            mode='video',
        )

    items = manager.load()
    assert len(items) == MAX_HISTORY_ITEMS
    assert items[0]['title'] == f'Video {MAX_HISTORY_ITEMS + 49}'


def test_history_i18n_key_parity():
    required_keys = [
        'drawer_history',
        'history_empty',
        'history_open_file',
        'history_open_folder',
        'history_redownload',
        'history_remove',
        'history_clear_all',
    ]

    pt_keys = set(TRANSLATIONS['pt_BR'].keys())
    en_keys = set(TRANSLATIONS['en_US'].keys())

    for key in required_keys:
        assert key in pt_keys, f'Missing key {key} in pt_BR'
        assert key in en_keys, f'Missing key {key} in en_US'
        assert TRANSLATIONS['pt_BR'][key] == TRANSLATIONS['pt_BR'][key].lower()
        assert TRANSLATIONS['en_US'][key] == TRANSLATIONS['en_US'][key].lower()

    # Full parity check across all translations
    assert pt_keys == en_keys
