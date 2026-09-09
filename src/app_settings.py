"""Validated application settings shared by storage and the GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from src.teaching_config import TEACHING_DEFAULTS


DEFAULT_APP_SETTINGS: dict[str, Any] = {
    **TEACHING_DEFAULTS,
    "theme": "light",
    "ui_scale": 100,
    "note_font_size": "standard",
    "code_font_size": "standard",
    "body_font": "system",
    "code_font": "system",
    "startup_page": "library",
    "restore_reading_state": False,
    "search_mode": "enter",
    "auto_generate_samples": True,
    "show_sample_notes": True,
    "notes_root": "",
    "index_strategy": "manual",
    "external_editor_mode": "system",
    "external_editor_path": "",
    "history_enabled": True,
    "history_limit": 20,
    "external_cache_policy": "discard",
    "last_note_path": "",
    "last_note_scroll": 0,
    "note_order": {},
}


_CHOICES = {
    "teach_provider": {"disabled", "local", "api"},
    "theme": {"light", "dark", "system"},
    "ui_scale": {90, 100, 110, 125},
    "note_font_size": {"small", "standard", "large"},
    "code_font_size": {"small", "standard", "large"},
    "startup_page": {"library", "search"},
    "search_mode": {"enter", "live"},
    "index_strategy": {"manual", "prompt"},
    "external_editor_mode": {"system", "custom"},
    "external_cache_policy": {"discard", "keep"},
}
_BOOL_KEYS = {
    "teach_external_first",
    "teach_include_samples",
    "restore_reading_state",
    "auto_generate_samples",
    "show_sample_notes",
    "history_enabled",
}
_STRING_KEYS = {
    "teach_model",
    "teach_allowed_types",
    "body_font",
    "code_font",
    "notes_root",
    "external_editor_path",
    "last_note_path",
}


def normalized_settings(
    values: dict[str, Any] | None,
    default_notes_root: Path,
) -> dict[str, Any]:
    """Merge stored values with defaults and reject invalid values."""
    settings = dict(DEFAULT_APP_SETTINGS)
    settings["notes_root"] = str(Path(default_notes_root).resolve())
    values = values or {}

    for key, choices in _CHOICES.items():
        if values.get(key) in choices:
            settings[key] = values[key]
    for key in _BOOL_KEYS:
        if isinstance(values.get(key), bool):
            settings[key] = values[key]
    for key in _STRING_KEYS:
        if isinstance(values.get(key), str):
            settings[key] = values[key]

    history_limit = values.get("history_limit")
    for key, lower, upper in (("teach_timeout", 5, 300), ("teach_top_k", 1, 20),
                              ("teach_chunk_size", 100, 2000), ("teach_max_file_mb", 1, 100)):
        value = values.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            settings[key] = max(lower, min(upper, value))
    base_url = values.get("teach_base_url")
    if isinstance(base_url, str):
        try:
            url = urlsplit(base_url.strip())
            if (url.scheme in {"http", "https"} and url.hostname and not
                    (url.username or url.password or url.query or url.fragment)):
                settings["teach_base_url"] = base_url.strip().rstrip("/")
        except ValueError:
            pass
    if isinstance(history_limit, int) and not isinstance(history_limit, bool):
        settings["history_limit"] = max(1, min(history_limit, 100))
    last_scroll = values.get("last_note_scroll")
    if isinstance(last_scroll, int) and not isinstance(last_scroll, bool):
        settings["last_note_scroll"] = max(0, last_scroll)

    note_order = values.get("note_order")
    if isinstance(note_order, dict):
        settings["note_order"] = {
            subject: [path for path in paths if isinstance(path, str)]
            for subject, paths in note_order.items()
            if isinstance(subject, str) and isinstance(paths, list)
        }

    notes_root = Path(settings["notes_root"]).expanduser()
    settings["notes_root"] = str(notes_root.resolve())
    return settings


__all__ = ["DEFAULT_APP_SETTINGS", "normalized_settings"]
