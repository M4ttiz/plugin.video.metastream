from __future__ import annotations

from typing import Any, Dict, List

from .base import BaseProvider, ProviderError

import script.module.requests as requests


class BitSearchProvider(BaseProvider):
    name = "bitsearch"
    base_url = "https://api.bitsearch.to/api/search"

    def search(self, query: str, *, limit: int = 25) -> List[Dict[str, Any]]:
        params = {"q": query, "limit": str(limit)}
        try:
            response = requests.get(self.base_url, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ProviderError(f"BitSearch request failed: {exc}", endpoint=self.base_url) from exc
        except ValueError as exc:
            raise ProviderError(f"BitSearch JSON parse failed: {exc}", endpoint=self.base_url) from exc

        results: List[Dict[str, Any]] = []
        for item in self._iter_results(payload):
            if not isinstance(item, dict):
                continue
            record = self._normalise(item)
            if record["magnet"]:
                results.append(record)
            if len(results) >= limit:
                break
        return results
