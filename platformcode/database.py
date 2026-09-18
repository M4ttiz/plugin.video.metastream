from __future__ import annotations

import os
import sqlite3
import threading
from typing import Iterable, List, Optional, Sequence, Tuple

import xbmc


class DatabaseManager:
    """SQLite wrapper with indexes and background bulk writes."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or os.path.join(xbmc.translatePath('special://profile/addon_data/plugin.video.s4me'), 'metastream.db')
        self._write_lock = threading.Lock()
        self._ensure_parent()
        self._initialize()

    def _ensure_parent(self) -> None:
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def _initialize(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS media_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imdb_id TEXT,
                    tmdb_id TEXT,
                    title TEXT,
                    payload TEXT,
                    timestamp_added TEXT DEFAULT (date('now'))
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS watch_progress (
                    media_key TEXT PRIMARY KEY,
                    resume_point REAL DEFAULT 0,
                    watched INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT (datetime('now'))
                )
                """
            )
            columns = [row[1] for row in connection.execute("PRAGMA table_info(media_cache)").fetchall()]
            if 'timestamp_added' not in columns:
                connection.execute("ALTER TABLE media_cache ADD COLUMN timestamp_added TEXT DEFAULT (date('now'))")
            connection.execute(self.index_sql())
            connection.commit()

            self.purge_stale_cache()
            threading.Thread(target=self.purge_stale_cache, daemon=True).start()

    def index_sql(self) -> str:
        return """
CREATE INDEX IF NOT EXISTS idx_media_cache_imdb_id ON media_cache(imdb_id);
CREATE INDEX IF NOT EXISTS idx_media_cache_tmdb_id ON media_cache(tmdb_id);
CREATE INDEX IF NOT EXISTS idx_media_cache_timestamp_added ON media_cache(timestamp_added);
"""

    def purge_stale_cache(self) -> int:
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM media_cache WHERE timestamp_added < date('now', '-7 days')"
            )
            connection.commit()
        return int(cursor.rowcount or 0)

    def save_watch_progress(self, media_key: str, resume_point: float, watched: bool = False) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS watch_progress (
                    media_key TEXT PRIMARY KEY,
                    resume_point REAL DEFAULT 0,
                    watched INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT (datetime('now'))
                )
                """,
            )
            connection.execute(
                "INSERT OR REPLACE INTO watch_progress(media_key, resume_point, watched, updated_at) VALUES (?, ?, ?, datetime('now'))",
                (media_key, float(resume_point), 1 if watched else 0),
            )
            connection.commit()

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def bulk_insert(self, rows: Sequence[Tuple[str, str, str, str]]) -> None:
        def _worker() -> None:
            try:
                with self._write_lock:
                    with sqlite3.connect(self.db_path, check_same_thread=False) as connection:
                        connection.executemany(
                            "INSERT OR REPLACE INTO media_cache(imdb_id, tmdb_id, title, payload, timestamp_added) VALUES (?, ?, ?, ?, date('now'))",
                            rows,
                        )
                        connection.commit()
            except sqlite3.Error as exc:
                xbmc.log(f"Database bulk insert failed: {exc}", xbmc.LOGERROR)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def bulk_update(self, rows: Sequence[Tuple[str, str, str, str]]) -> None:
        self.bulk_insert(rows)

    def fetch_by_imdb(self, imdb_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT payload FROM media_cache WHERE imdb_id = ? ORDER BY id DESC LIMIT 1",
                (imdb_id,),
            ).fetchone()
        if row is None:
            return None
        import json
        try:
            return json.loads(row[0])
        except (TypeError, ValueError) as exc:
            xbmc.log(f"Database row parse failed: {exc}", xbmc.LOGERROR)
            return None

    def fetch_by_tmdb(self, tmdb_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT payload FROM media_cache WHERE tmdb_id = ? ORDER BY id DESC LIMIT 1",
                (tmdb_id,),
            ).fetchone()
        if row is None:
            return None
        import json
        try:
            return json.loads(row[0])
        except (TypeError, ValueError) as exc:
            xbmc.log(f"Database row parse failed: {exc}", xbmc.LOGERROR)
            return None
