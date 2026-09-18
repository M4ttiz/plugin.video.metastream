from __future__ import annotations

from typing import Any, Dict

from .base import DebridClient, DebridClientError


class AllDebridClient(DebridClient):
    name = "alldebrid"
    base_url = "https://api.alldebrid.com/v4"

    def authenticate(self) -> str:
        if not self.client_id or not self.client_secret:
            raise DebridClientError("AllDebrid requires client_id and client_secret.")
        payload = {
            "agent": "stream4me",
            "username": self.client_id,
            "password": self.client_secret,
        }
        response = self._request_json("POST", f"{self.base_url}/pin/get", data=payload)
        token = response.get("data", {}).get("token")
        if not token:
            raise DebridClientError("AllDebrid OAuth flow did not return a token.")
        self.access_token = token
        return token

    def add_magnet(self, magnet: str) -> Dict[str, Any]:
        if not self.access_token:
            raise DebridClientError("AllDebrid access token is missing.")
        response = self._request_json(
            "POST",
            f"{self.base_url}/magnet/instant",
            headers=self._token_headers(),
            data={"magnet": magnet},
        )
        return response.get("data", {})

    def resolve_url(self, url: str) -> str:
        if not self.access_token:
            raise DebridClientError("AllDebrid access token is missing.")
        response = self._request_json(
            "POST",
            f"{self.base_url}/link/unlock",
            headers=self._token_headers(),
            data={"link": url},
        )
        direct_url = response.get("data", {}).get("link") or response.get("data", {}).get("download")
        if not direct_url:
            raise DebridClientError(f"AllDebrid did not return an unrestricted link for {url}")
        return direct_url
