from __future__ import annotations

from typing import Any, Dict

from .base import DebridClient, DebridClientError


class PremiumizeClient(DebridClient):
    name = "premiumize"
    base_url = "https://www.premiumize.me/api"

    def authenticate(self) -> str:
        if not self.client_id or not self.client_secret:
            raise DebridClientError("Premiumize requires client_id and client_secret.")
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }
        response = self._request_json("POST", f"{self.base_url}/token", data=payload)
        token = response.get("access_token")
        if not token:
            raise DebridClientError("Premiumize OAuth2 flow did not return an access_token.")
        self.access_token = token
        self.refresh_token = response.get("refresh_token", self.refresh_token)
        return token

    def add_magnet(self, magnet: str) -> Dict[str, Any]:
        if not self.access_token:
            raise DebridClientError("Premiumize access token is missing.")
        response = self._request_json(
            "POST",
            f"{self.base_url}/transfer/create",
            headers=self._token_headers(),
            data={"src": magnet},
        )
        return response

    def resolve_url(self, url: str) -> str:
        if not self.access_token:
            raise DebridClientError("Premiumize access token is missing.")
        response = self._request_json(
            "POST",
            f"{self.base_url}/directdl/", 
            headers=self._token_headers(),
            data={"link": url},
        )
        direct_url = response.get("location") or response.get("download") or response.get("url")
        if not direct_url:
            raise DebridClientError(f"Premiumize did not return an unrestricted link for {url}")
        return direct_url
