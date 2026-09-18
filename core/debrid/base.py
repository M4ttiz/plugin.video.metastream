from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import xbmc
import xbmcgui

import script.module.requests as requests


class DebridClientError(RuntimeError):
    def __init__(self, message: str, *, endpoint: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.endpoint = endpoint
        self.payload = payload or {}


class DebridClient(ABC):
    """Base interface shared by debrid providers."""

    name: str = "debrid"
    base_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    access_token: str = ""
    refresh_token: str = ""

    def __init__(self, client_id: str = "", client_secret: str = "", access_token: str = "", refresh_token: str = "") -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token

    def _log(self, message: str, level: int = xbmc.LOGINFO) -> None:
        xbmc.log(f"[{self.name}] {message}", level)

    def _notify(self, message: str) -> None:
        try:
            xbmcgui.Dialog().notification("Debrid", message, xbmcgui.NOTIFICATION_INFO, 4000)
        except AttributeError:
            pass

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: int = 20,
    ) -> Dict[str, Any]:
        try:
            response = requests.request(method.upper(), url, headers=headers, params=params, data=data, timeout=timeout)
            xbmc.log(f"[METASTREAM-DEBUG] DEBRID RAW RESPONSE: {response.text}", xbmc.LOGINFO)
            response.raise_for_status()
            payload = response.json() if response.content else {}
            if isinstance(payload, dict):
                return payload
            raise DebridClientError(f"Unexpected non-dict payload for {url}", endpoint=url, payload={"raw": payload})
        except requests.RequestException as exc:
            self._log(f"HTTP error: {url} :: {exc}", xbmc.LOGERROR)
            raise DebridClientError(f"Network error: {exc}", endpoint=url) from exc
        except ValueError as exc:
            self._log(f"JSON parse error: {url} :: {exc}", xbmc.LOGERROR)
            raise DebridClientError(f"JSON parse error: {exc}", endpoint=url) from exc

    @abstractmethod
    def authenticate(self) -> str:
        """Perform OAuth2 authentication and return access_token."""

    @abstractmethod
    def add_magnet(self, magnet: str) -> Dict[str, Any]:
        """Submit a magnet to the provider and return the provider response."""

    @abstractmethod
    def resolve_url(self, url: str) -> str:
        """Resolve an HTTP URL to an unrestricted direct download link."""

    def resolve_magnet(self, magnet: str) -> str:
        response = self.add_magnet(magnet)
        if isinstance(response, dict):
            if response.get("download"):
                return response["download"]
            if response.get("link"):
                return response["link"]
            if response.get("files") and isinstance(response["files"], list):
                for item in response["files"]:
                    if item.get("link"):
                        return item["link"]
        raise DebridClientError(f"No unrestricted link available for magnet {magnet}")

    def _token_headers(self) -> Dict[str, str]:
        if not self.access_token:
            raise DebridClientError(f"{self.name} client is not authenticated.")
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}

    def refresh_access_token(self) -> str:
        if not self.refresh_token:
            raise DebridClientError(f"Refresh token missing for {self.name}.")
        return self.access_token
