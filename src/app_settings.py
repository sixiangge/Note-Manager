"""Validated application settings shared by storage and the GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_APP_SETTINGS: dict[str, Any] = {
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
    "restore_reading_state",
    "auto_generate_samples",
    "show_sample_notes",
    "history_enabled",
}
_STRING_KEYS = {
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
