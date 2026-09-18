"""Debrid service layer for Real-Debrid, AllDebrid and Premiumize."""

from .base import DebridClient, DebridClientError
from .realdebrid import RealDebridClient
from .alldebrid import AllDebridClient
from .premiumize import PremiumizeClient

__all__ = [
    "DebridClient",
    "DebridClientError",
    "RealDebridClient",
    "AllDebridClient",
    "PremiumizeClient",
]
