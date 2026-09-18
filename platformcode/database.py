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
                    payload TEXT
                )
                """
            )
            connection.execute(self.index_sql())
            connection.commit()

    def index_sql(self) -> str:
        return """
CREATE INDEX IF NOT EXISTS idx_media_cache_imdb_id ON media_cache(imdb_id);
CREATE INDEX IF NOT EXISTS idx_media_cache_tmdb_id ON media_cache(tmdb_id);
"""

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def bulk_insert(self, rows: Sequence[Tuple[str, str, str, str]]) -> None:
        def _worker() -> None:
            try:
                with self._write_lock:
                    with sqlite3.connect(self.db_path, check_same_thread=False) as connection:
                        connection.executemany(
                            "INSERT OR REPLACE INTO media_cache(imdb_id, tmdb_id, title, payload) VALUES (?, ?, ?, ?)",
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
