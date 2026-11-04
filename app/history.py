from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_NAME = 'Yt-RivoGUI'
MAX_HISTORY_ITEMS = 500


def get_app_data_dir(override: str | Path | None = None) -> Path:
    """Returns directory for app settings/data (guaranteed to exist)."""
    if override:
        path = Path(override).expanduser()
    elif sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
        path = Path(base) / APP_NAME
    else:
        base = os.environ.get('XDG_DATA_HOME') or str(Path.home() / '.local' / 'share')
        path = Path(base) / 'yt-rivogui'
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_history_file_path(override_dir: str | Path | None = None) -> Path:
    """Returns path to history.json."""
    if override_dir and Path(override_dir).name.endswith('.json'):
        return Path(override_dir)
    return get_app_data_dir(override_dir) / 'history.json'


class DownloadHistoryManager:
    """Manages persistent download history in %LOCALAPPDATA%\\Yt-RivoGUI\\history.json."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.file_path = get_history_file_path(data_dir)

    def load(self) -> list[dict[str, Any]]:
        """Loads and returns history items from JSON. Safe fallback on errors."""
        if not self.file_path.exists():
            return []
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def _save_atomic(self, items: list[dict[str, Any]]) -> None:
        """Atomically saves items to history.json."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.file_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            temp_path.replace(self.file_path)
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def add_entry(
        self,
        title: str,
        url: str,
        file_path: str,
        mode: str,
        file_size: str = '',
    ) -> dict[str, Any]:
        """
        Adds a new completed download record at top of history.
        Truncates to MAX_HISTORY_ITEMS (500) and saves atomically.
        """
        entry: dict[str, Any] = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'title': title or 'unnamed media',
            'url': url or '',
            'file_path': file_path or '',
            'mode': mode or 'video',
            'file_size': file_size or '',
        }

        history = self.load()
        history.insert(0, entry)
        if len(history) > MAX_HISTORY_ITEMS:
            history = history[:MAX_HISTORY_ITEMS]

        self._save_atomic(history)
        return entry

    def remove_entry(self, entry_id: str) -> bool:
        """Removes an item by id from history.json."""
        history = self.load()
        initial_len = len(history)
        history = [item for item in history if item.get('id') != entry_id]
        if len(history) < initial_len:
            self._save_atomic(history)
            return True
        return False

    def clear_all(self) -> None:
        """Clears all history records."""
        self._save_atomic([])
