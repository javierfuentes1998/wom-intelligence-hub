"""Official Google Business Profile client used by the review pipeline.

Secrets are supplied by environment variables and are never logged or returned.
The small HTTP surface is intentionally injectable so the complete workflow can
be tested without Google credentials.
"""
from __future__ import annotations

import time
from typing import Callable

import httpx

from .config import settings

SCOPE = "https://www.googleapis.com/auth/business.manage"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ACCOUNT_URL = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
BUSINESS_INFO_URL = "https://mybusinessbusinessinformation.googleapis.com/v1"
REVIEWS_URL = "https://mybusiness.googleapis.com/v4"


class GoogleReviewError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def credentials_configured() -> bool:
    return bool(settings.google_business_access_token or (
        settings.google_business_client_id and settings.google_business_client_secret
        and settings.google_business_refresh_token
    ))


class OAuthTokenProvider:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=20)

    def __call__(self) -> str:
        if settings.google_business_access_token:
            return settings.google_business_access_token
        if not credentials_configured():
            raise GoogleReviewError("Google Business Profile pendiente de autorización")
        response = self.client.post(TOKEN_URL, data={
            "client_id": settings.google_business_client_id,
            "client_secret": settings.google_business_client_secret,
            "refresh_token": settings.google_business_refresh_token,
            "grant_type": "refresh_token",
        })
        if response.status_code >= 400:
            raise GoogleReviewError("No se pudo renovar la autorización de Google Business Profile", response.status_code)
        token = response.json().get("access_token")
        if not token:
            raise GoogleReviewError("Google no devolvió un access token")
        return token


class GoogleBusinessProfileClient:
    def __init__(self, client: httpx.Client | None = None, token_provider: Callable[[], str] | None = None,
                 max_attempts: int = 3):
        self.client = client or httpx.Client(timeout=25)
        self.token_provider = token_provider or OAuthTokenProvider(self.client)
        self.max_attempts = max_attempts

    def _get(self, url: str, params: dict | None = None) -> dict:
        for attempt in range(self.max_attempts):
            response = self.client.get(url, params=params, headers={"Authorization": f"Bearer {self.token_provider()}"})
            if response.status_code < 400:
                return response.json()
            if response.status_code not in {429, 500, 502, 503, 504} or attempt + 1 >= self.max_attempts:
                message = "Autorización insuficiente" if response.status_code in {401, 403} else "Error de Google Business Profile"
                raise GoogleReviewError(message, response.status_code)
            time.sleep(0.05 * (2 ** attempt))
        raise GoogleReviewError("Error de Google Business Profile")

    def list_accounts(self) -> list[dict]:
        return self._get(ACCOUNT_URL).get("accounts", [])

    def list_locations(self, account_name: str) -> list[dict]:
        rows, token = [], None
        while True:
            params = {"readMask": "name,title,storeCode,phoneNumbers,categories,storefrontAddress,websiteUri", "pageSize": 100}
            if token: params["pageToken"] = token
            data = self._get(f"{BUSINESS_INFO_URL}/{account_name}/locations", params)
            rows.extend(data.get("locations", [])); token = data.get("nextPageToken")
            if not token: return rows

    def list_reviews(self, location_name: str) -> list[dict]:
        rows, token = [], None
        while True:
            params = {"pageSize": 50, "orderBy": "updateTime desc"}
            if token: params["pageToken"] = token
            data = self._get(f"{REVIEWS_URL}/{location_name}/reviews", params)
            rows.extend(data.get("reviews", [])); token = data.get("nextPageToken")
            if not token: return rows
