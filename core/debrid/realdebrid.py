from __future__ import annotations

from typing import Any, Dict

import xbmc

from .base import DebridClient, DebridClientError

import script.module.requests as requests


class RealDebridClient(DebridClient):
    name = "realdebrid"
    base_url = "https://api.real-debrid.com/rest/1.0"

    def authenticate(self) -> str:
        if not self.client_id or not self.client_secret:
            raise DebridClientError("Real-Debrid requires client_id and client_secret.")
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }
        response = self._request_json("POST", "https://api.real-debrid.com/oauth/v2/token", data=payload)
        token = response.get("access_token")
        if not token:
            raise DebridClientError("Real-Debrid OAuth2 flow did not return an access_token.")
        self.access_token = token
        self.refresh_token = response.get("refresh_token", self.refresh_token)
        return token

    def add_magnet(self, magnet: str) -> Dict[str, Any]:
        if not self.access_token:
            raise DebridClientError("Real-Debrid access token is missing.")
        response = self._request_json(
            "POST",
            f"{self.base_url}/torrents/addMagnet",
            headers=self._token_headers(),
            data={"magnet": magnet},
        )
        return response

    def resolve_url(self, url: str) -> str:
        if not self.access_token:
            raise DebridClientError("Real-Debrid access token is missing.")
        response = self._request_json(
            "POST",
            f"{self.base_url}/unrestrict/link",
            headers=self._token_headers(),
            data={"link": url},
        )
        direct_url = response.get("download") or response.get("link")
        if not direct_url:
            raise DebridClientError(f"Real-Debrid did not return an unrestricted link for {url}")
        return direct_url
