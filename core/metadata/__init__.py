"""Metadata service for TMDB and Trakt with local caching."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, Optional

import xbmc

import script.module.requests as requests

from platformcode import config


class MetadataService:
    """Centralizes TMDB and Trakt data retrieval with local caching."""

    _tmdb_api_key: str = ""
    _trakt_client_id: str = ""
    _cache_path: str = ""
    _cache_ttl: int = 86400

    def __init__(self, cache_ttl: int = 86400, cache_path: Optional[str] = None) -> None:
        self._cache_ttl = cache_ttl
        self._cache_path = cache_path or os.path.join(config.get_data_path(), "metadata_cache.sqlite")
        self._tmdb_api_key = os.environ.get("TMDB_API_KEY", config.get_setting("tmdb_api_key", default=""))
        self._trakt_client_id = os.environ.get("TRAKT_CLIENT_ID", config.get_setting("trakt_client_id", default=""))
        self._init_db()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self._cache_path) or ".", exist_ok=True)
        with sqlite3.connect(self._cache_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_expires_at ON cache(expires_at)"
            )
            connection.commit()

    def _cache_key(self, kind: str, params: Dict[str, Any]) -> str:
        item = json.dumps(params, sort_keys=True, separators=(",", ":"))
        return f"{kind}:{item}"

    def _read_cache(self, key: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self._cache_path) as connection:
            row = connection.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        value_json, expires_at = row
        if expires_at <= int(time.time()):
            self._delete_cache(key)
            return None
        try:
            return json.loads(value_json)
        except (TypeError, ValueError) as exc:
            xbmc.log(f"Metadata cache parse error: {exc}", xbmc.LOGERROR)
            self._delete_cache(key)
            return None

    def _write_cache(self, key: str, payload: Dict[str, Any]) -> None:
        expires_at = int(time.time()) + self._cache_ttl
        value = json.dumps(payload, sort_keys=True)
        with sqlite3.connect(self._cache_path) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO cache(key, value, expires_at, updated_at) VALUES (?, ?, ?, ?)",
                (key, value, expires_at, int(time.time())),
            )
            connection.commit()

    def _delete_cache(self, key: str) -> None:
        with sqlite3.connect(self._cache_path) as connection:
            connection.execute("DELETE FROM cache WHERE key = ?", (key,))
            connection.commit()

    def _request_json(self, url: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=20)
            response.raise_for_status()
            content = response.json()
            if not isinstance(content, dict):
                return {"results": content}
            return content
        except requests.RequestException as exc:
            xbmc.log(f"Metadata request failed: {url} :: {exc}", xbmc.LOGERROR)
            raise

    def fetch_tmdb(self, media_type: str, query: Optional[str] = None, *, tmdb_id: Optional[str] = None, imdb_id: Optional[str] = None, language: str = "it-IT") -> Dict[str, Any]:
        if not self._tmdb_api_key:
            return {}

        if tmdb_id:
            url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
            params = {"api_key": self._tmdb_api_key, "language": language, "append_to_response": "images,external_ids"}
        elif imdb_id:
            url = f"https://api.themoviedb.org/3/find/{imdb_id}"
            params = {"api_key": self._tmdb_api_key, "language": language, "external_source": "imdb_id"}
        elif query:
            url = f"https://api.themoviedb.org/3/search/{media_type}"
            params = {"api_key": self._tmdb_api_key, "query": query, "language": language}
        else:
            raise ValueError("TMDB fetch requires query, tmdb_id or imdb_id")

        cache_key = self._cache_key("tmdb", {"url": url, "params": params})
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        payload = self._request_json(url, params=params)
        self._write_cache(cache_key, payload)
        return payload

    def fetch_trakt(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._trakt_client_id:
            return {}
        headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": self._trakt_client_id,
        }
        cache_key = self._cache_key("trakt", {"endpoint": endpoint, "params": params or {}})
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        payload = self._request_json(f"https://api.trakt.tv/{endpoint.lstrip('/')}", headers=headers, params={k: str(v) for k, v in (params or {}).items()})
        self._write_cache(cache_key, payload)
        return payload

    def get_poster(self, poster_path: Optional[str], size: str = "w500") -> Optional[str]:
        if not poster_path:
            return None
        return f"https://image.tmdb.org/t/p/{size}{poster_path}"

    def get_fanart(self, backdrops: Any, size: str = "original") -> Optional[str]:
        if not isinstance(backdrops, dict):
            return None
        results = backdrops.get("backdrops") or []
        if not results:
            return None
        first = results[0]
        file_path = first.get("file_path")
        if not file_path:
            return None
        return f"https://image.tmdb.org/t/p/{size}{file_path}"

    def get_media_details(self, media_type: str, *, query: Optional[str] = None, tmdb_id: Optional[str] = None, imdb_id: Optional[str] = None, language: str = "it-IT") -> Dict[str, Any]:
        payload = self.fetch_tmdb(media_type, query=query, tmdb_id=tmdb_id, imdb_id=imdb_id, language=language)
        if not payload and not query and not tmdb_id and not imdb_id:
            return {}
        if not payload:
            return payload

        if imdb_id and isinstance(payload, dict) and "results" in payload and payload["results"]:
            return payload["results"][0]
        if tmdb_id and isinstance(payload, dict):
            return payload
        if query and isinstance(payload, dict) and "results" in payload and payload["results"]:
            return payload["results"][0]
        return payload


__all__ = ["MetadataService"]
