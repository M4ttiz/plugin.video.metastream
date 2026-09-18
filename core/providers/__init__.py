"""JSON provider layer for torrent/meta-scraper sources."""

from .torrentio import TorrentioProvider
from .bitsearch import BitSearchProvider

__all__ = ["TorrentioProvider", "BitSearchProvider"]
