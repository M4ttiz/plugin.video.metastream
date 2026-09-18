from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional

import xbmc


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, endpoint: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.endpoint = endpoint


class BaseProvider(ABC):
    """Base class for JSON-only torrent/meta-scraper providers."""

    name: str = "provider"
    base_url: str = ""

    def _log(self, message: str, level: int = xbmc.LOGINFO) -> None:
        xbmc.log(f"[{self.name}] {message}", level)

    def _normalise(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": item.get("title") or item.get("name") or item.get("filename") or "Unknown",
            "quality": item.get("quality") or item.get("video_quality") or "unknown",
            "size": item.get("size") or item.get("size_bytes") or item.get("length") or 0,
            "seeders": item.get("seeders") or item.get("seeds") or 0,
            "magnet": item.get("magnet") or item.get("link") or item.get("download") or "",
        }

    @abstractmethod
    def search(self, query: str, *, limit: int = 25) -> List[Dict[str, Any]]:
        """Return a list of normalized records."""

    def _iter_results(self, payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        for key in ("results", "movies", "torrents", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []
