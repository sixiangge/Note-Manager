"""SQLite storage for the local note catalog and GUI search history."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 3


def _connect(database_path: Path) -> sqlite3.Connection:
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def _database_connection(database_path: Path) -> Iterator[sqlite3.Connection]:
    connection = _connect(database_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(database_path: Path) -> None:
    """Create the SQLite database and required tables when absent.

    Args:
        database_path: Path to ``njucskeeper.db``.
    """
    with _database_connection(database_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS notes (
                path TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                chapter TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                note_type TEXT NOT NULL,
                exam_freq INTEGER NOT NULL DEFAULT 0,
                modified_time_ns INTEGER NOT NULL DEFAULT 0,
                content_hash TEXT NOT NULL DEFAULT '',
                synced_at_ns INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_notes_subject
                ON notes(subject);
            CREATE INDEX IF NOT EXISTS idx_notes_type
                ON notes(note_type);

            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                subject TEXT NOT NULL DEFAULT '',
                note_type TEXT NOT NULL DEFAULT '',
                exclude_tag TEXT NOT NULL DEFAULT '',
                searched_at_ns INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_search_history_time
                ON search_history(searched_at_ns DESC, id DESC);

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at_ns INTEGER NOT NULL
            );
            """
        )
        history_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(search_history)")
        }
        if "exclude_tag" not in history_columns:
            connection.execute(
                "ALTER TABLE search_history "
                "ADD COLUMN exclude_tag TEXT NOT NULL DEFAULT ''"
            )
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _file_fingerprint(file_path: Path) -> tuple[int, str]:
    if not file_path.is_file():
        return 0, ""
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return file_path.stat().st_mtime_ns, digest.hexdigest()


def sync_note_catalog(index: dict, base_dir: Path, database_path: Path) -> int:
    """Synchronize indexed note metadata into SQLite in one transaction.

    Markdown files remain authoritative. Rows missing from the latest index are
    deleted, so the table is a rebuildable catalog rather than a second source.

    Args:
        index: Inverted-index dictionary containing a ``documents`` mapping.
        base_dir: Project root used to resolve document paths.
        database_path: Path to ``njucskeeper.db``.

    Returns:
        Number of synchronized note rows.
    """
    initialize_database(database_path)
    base_dir = Path(base_dir).resolve()
    documents: dict[str, dict[str, Any]] = index.get("documents", {})
    synced_at = time.time_ns()
    rows: list[tuple[Any, ...]] = []

    for relative_path, document in documents.items():
        normalized_path = str(relative_path).replace("\\", "/")
        absolute_path = (base_dir / normalized_path).resolve()
        absolute_path.relative_to(base_dir)
        modified_time_ns, content_hash = _file_fingerprint(absolute_path)
        rows.append(
            (
                normalized_path,
                str(document.get("title", "")),
                str(document.get("subject", "")),
                str(document.get("chapter", "")),
                json.dumps(document.get("tags", []), ensure_ascii=False),
                str(document.get("note_type", "exam")),
                int(document.get("exam_freq", 0)),
                modified_time_ns,
                content_hash,
                synced_at,
            )
        )

    with _database_connection(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO notes (
                path, title, subject, chapter, tags_json, note_type,
                exam_freq, modified_time_ns, content_hash, synced_at_ns
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                title = excluded.title,
                subject = excluded.subject,
                chapter = excluded.chapter,
                tags_json = excluded.tags_json,
                note_type = excluded.note_type,
                exam_freq = excluded.exam_freq,
                modified_time_ns = excluded.modified_time_ns,
                content_hash = excluded.content_hash,
                synced_at_ns = excluded.synced_at_ns
            """,
            rows,
        )
        current_paths = {row[0] for row in rows}
        stored_paths = {
            row["path"] for row in connection.execute("SELECT path FROM notes")
        }
        connection.executemany(
            "DELETE FROM notes WHERE path = ?",
            [(path,) for path in stored_paths - current_paths],
        )
    return len(rows)


def load_note_catalog(database_path: Path) -> list[tuple[str, dict[str, Any]]]:
    """Load note metadata from SQLite in display order."""
    initialize_database(database_path)
    with _database_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT path, title, subject, chapter, tags_json, note_type,
                   exam_freq, modified_time_ns, content_hash
            FROM notes
            ORDER BY subject, chapter, title, path
            """
        ).fetchall()

    catalog: list[tuple[str, dict[str, Any]]] = []
    for row in rows:
        try:
            tags = json.loads(row["tags_json"])
        except (TypeError, json.JSONDecodeError):
            tags = []
        if not isinstance(tags, list):
            tags = []
        catalog.append(
            (
                row["path"],
                {
                    "title": row["title"],
                    "subject": row["subject"],
                    "chapter": row["chapter"],
                    "tags": tags,
                    "note_type": row["note_type"],
                    "exam_freq": row["exam_freq"],
                    "modified_time_ns": row["modified_time_ns"],
                    "content_hash": row["content_hash"],
                },
            )
        )
    return catalog


def _serialize_filter_values(
    value: str | list[str] | tuple[str, ...] | set[str] | None,
) -> str:
    if isinstance(value, str):
        values = [value.strip()] if value.strip() else []
    else:
        values = sorted({item.strip() for item in (value or []) if item.strip()})
    if len(values) == 1:
        return values[0]
    if values:
        return json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return ""


def _deserialize_filter_values(value: str | None) -> list[str]:
    stored = value or ""
    if not stored.startswith("["):
        return [stored] if stored else []
    try:
        parsed = json.loads(stored)
    except json.JSONDecodeError:
        return [stored]
    if not isinstance(parsed, list):
        return [stored]
    return [str(item) for item in parsed if str(item).strip()]


def record_search(
    database_path: Path,
    query: str,
    subject: str | list[str] | tuple[str, ...] | set[str] | None = None,
    note_type: str | None = None,
    exclude_tag: str | list[str] | tuple[str, ...] | set[str] | None = None,
    limit: int = 20,
) -> None:
    """Store a search and keep only the newest history rows."""
    query = query.strip()
    if not query:
        return
    initialize_database(database_path)
    normalized_subject = _serialize_filter_values(subject)
    normalized_type = note_type or ""
    normalized_exclude_tag = _serialize_filter_values(exclude_tag)
    with _database_connection(database_path) as connection:
        connection.execute(
            """
            DELETE FROM search_history
            WHERE query = ? AND subject = ? AND note_type = ? AND exclude_tag = ?
            """,
            (query, normalized_subject, normalized_type, normalized_exclude_tag),
        )
        connection.execute(
            """
            INSERT INTO search_history(
                query, subject, note_type, exclude_tag, searched_at_ns
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                query,
                normalized_subject,
                normalized_type,
                normalized_exclude_tag,
                time.time_ns(),
            ),
        )
        connection.execute(
            """
            DELETE FROM search_history
            WHERE id NOT IN (
                SELECT id FROM search_history
                ORDER BY searched_at_ns DESC, id DESC
                LIMIT ?
            )
            """,
            (max(limit, 1),),
        )


def load_search_history(database_path: Path, limit: int = 20) -> list[dict[str, Any]]:
    """Return the newest search history rows."""
    initialize_database(database_path)
    with _database_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT query, subject, note_type, exclude_tag, searched_at_ns
            FROM search_history
            ORDER BY searched_at_ns DESC, id DESC
            LIMIT ?
            """,
            (max(limit, 1),),
        ).fetchall()
    history: list[dict[str, Any]] = []
    for row in rows:
        subjects = _deserialize_filter_values(row["subject"])
        exclude_tags = _deserialize_filter_values(row["exclude_tag"])
        history.append(
            {
                "query": row["query"],
                "subject": subjects[0] if len(subjects) == 1 else None,
                "subjects": subjects,
                "note_type": row["note_type"] or None,
                "exclude_tag": exclude_tags[0] if len(exclude_tags) == 1 else None,
                "exclude_tags": exclude_tags,
                "searched_at_ns": row["searched_at_ns"],
            }
        )
    return history


def clear_search_history(database_path: Path) -> None:
    """Delete all persisted GUI search history."""
    initialize_database(database_path)
    with _database_connection(database_path) as connection:
        connection.execute("DELETE FROM search_history")


def trim_search_history(database_path: Path, limit: int) -> None:
    """Keep only the newest configured number of search-history rows."""
    initialize_database(database_path)
    with _database_connection(database_path) as connection:
        connection.execute(
            """
            DELETE FROM search_history
            WHERE id NOT IN (
                SELECT id FROM search_history
                ORDER BY searched_at_ns DESC, id DESC
                LIMIT ?
            )
            """,
            (max(1, min(int(limit), 100)),),
        )


def load_app_settings(database_path: Path) -> dict[str, Any]:
    """Load persisted non-sensitive application settings."""
    initialize_database(database_path)
    with _database_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT key, value_json FROM app_settings"
        ).fetchall()
    settings: dict[str, Any] = {}
    for row in rows:
        try:
            settings[row["key"]] = json.loads(row["value_json"])
        except (TypeError, json.JSONDecodeError):
            continue
    return settings


def save_app_setting(database_path: Path, key: str, value: Any) -> None:
    """Persist one application setting as JSON."""
    initialize_database(database_path)
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    with _database_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO app_settings(key, value_json, updated_at_ns)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at_ns = excluded.updated_at_ns
            """,
            (key, encoded, time.time_ns()),
        )


def save_app_settings(database_path: Path, settings: dict[str, Any]) -> None:
    """Persist several application settings in one transaction."""
    initialize_database(database_path)
    now = time.time_ns()
    rows = [
        (
            key,
            json.dumps(value, ensure_ascii=False, separators=(",", ":")),
            now,
        )
        for key, value in settings.items()
    ]
    with _database_connection(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO app_settings(key, value_json, updated_at_ns)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at_ns = excluded.updated_at_ns
            """,
            rows,
        )


def reset_app_settings(database_path: Path) -> None:
    """Remove application settings without deleting search history or notes."""
    initialize_database(database_path)
    with _database_connection(database_path) as connection:
        connection.execute("DELETE FROM app_settings")


def storage_summary(database_path: Path) -> dict[str, Any]:
    """Return read-only SQLite catalog information for the settings page."""
    initialize_database(database_path)
    with _database_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS note_count,
                   COALESCE(MAX(synced_at_ns), 0) AS last_sync_ns
            FROM notes
            """
        ).fetchone()
    return {
        "database_path": str(Path(database_path).resolve()),
        "database_size": Path(database_path).stat().st_size
        if Path(database_path).exists()
        else 0,
        "note_count": int(row["note_count"]),
        "last_sync_ns": int(row["last_sync_ns"]),
    }


def export_local_data(database_path: Path, output_path: Path) -> None:
    """Export settings and search history without exporting note content."""
    initialize_database(database_path)
    with _database_connection(database_path) as connection:
        setting_rows = connection.execute(
            "SELECT key, value_json FROM app_settings ORDER BY key"
        ).fetchall()
        history_rows = connection.execute(
            """
            SELECT query, subject, note_type, exclude_tag, searched_at_ns
            FROM search_history
            ORDER BY searched_at_ns DESC, id DESC
            """
        ).fetchall()
    settings: dict[str, Any] = {}
    for row in setting_rows:
        try:
            settings[row["key"]] = json.loads(row["value_json"])
        except (TypeError, json.JSONDecodeError):
            settings[row["key"]] = row["value_json"]
    payload = {
        "format": "NJUCSKeeper local data",
        "version": 1,
        "exported_at_ns": time.time_ns(),
        "settings": settings,
        "search_history": [dict(row) for row in history_rows],
    }
    Path(output_path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


__all__ = [
    "clear_search_history",
    "export_local_data",
    "initialize_database",
    "load_app_settings",
    "load_note_catalog",
    "load_search_history",
    "record_search",
    "reset_app_settings",
    "save_app_setting",
    "save_app_settings",
    "storage_summary",
    "sync_note_catalog",
    "trim_search_history",
]
