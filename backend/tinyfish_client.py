import os
import time
import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from backend.config import TINYFISH_API_KEY, is_tinyfish_configured

logger = logging.getLogger(__name__)

SEARCH_API_ENDPOINT = "https://api.search.tinyfish.ai"

class TinyFishClient:
    """
    Client for TinyFish Search API and TinyFish Fetch SDK.
    Strictly adheres to LIVE MODE requirements:
    - Never uses hardcoded keys
    - Reads TINYFISH_API_KEY from environment
    - Reports clear errors when credentials or network requests fail
    - Implements deduplication, caching, timeouts, and content validation
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or TINYFISH_API_KEY
        self._cache_search: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_fetch: Dict[str, Dict[str, Any]] = {}

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    def search(self, query: str, recency_minutes: Optional[int] = None, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Executes TinyFish Search API to discover live humanitarian/crisis web pages.
        Raises ValueError or requests.RequestException on failure.
        """
        if not self.is_configured():
            raise ValueError(
                "TinyFish API key is not configured. "
                "Please set TINYFISH_API_KEY in your local .env file to run in LIVE MODE."
            )

        cache_key = query.strip().lower()
        if cache_key in self._cache_search:
            logger.info(f"Returning cached search results for: '{query}'")
            return self._cache_search[cache_key]

        headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json"
        }
        params: Dict[str, Any] = {"query": query}
        if recency_minutes:
            params["recency_minutes"] = recency_minutes

        # Basic retry logic for transient errors
        last_error = None
        for attempt in range(2):
            try:
                response = requests.get(
                    SEARCH_API_ENDPOINT,
                    headers=headers,
                    params=params,
                    timeout=30
                )
                if response.status_code == 401 or response.status_code == 403:
                    raise PermissionError(
                        f"TinyFish API Authentication Failed (HTTP {response.status_code}). "
                        "Check that your TINYFISH_API_KEY is valid and active."
                    )
                response.raise_for_status()
                data = response.json()

                raw_results = data.get("results", [])
                deduped = []
                seen_urls = set()

                for item in raw_results[:max_results]:
                    url = item.get("url")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        deduped.append({
                            "url": url,
                            "title": item.get("title") or "Untitled Source",
                            "snippet": item.get("snippet") or "",
                            "published_date": item.get("date") or None,
                            "site_name": item.get("site_name") or ""
                        })

                self._cache_search[cache_key] = deduped
                return deduped

            except requests.RequestException as e:
                last_error = e
                time.sleep(1)

        raise RuntimeError(f"TinyFish Search API request failed after retries: {str(last_error)}")

    def fetch_url(self, url: str) -> Dict[str, Any]:
        """
        Fetches a URL using the TinyFish Python SDK fetch interface.
        Validates content and detects blocked or empty responses.
        """
        if not self.is_configured():
            raise ValueError(
                "TinyFish API key is not configured. "
                "Please set TINYFISH_API_KEY in your local .env file to run in LIVE MODE."
            )

        if url in self._cache_fetch:
            return self._cache_fetch[url]

        from tinyfish import TinyFish

        try:
            client = TinyFish(api_key=self.api_key)
            result = client.fetch.get_contents(urls=[url])
            
            pages = getattr(result, "results", [])
            if not pages:
                return {
                    "url": url,
                    "title": "Fetch Failed",
                    "text": "",
                    "fetch_status": "EMPTY",
                    "error_msg": "No content pages returned by TinyFish Fetch SDK."
                }

            page = pages[0]
            text = getattr(page, "text", "") or ""
            title = getattr(page, "title", "") or "Untitled Source"

            # Check for blocked or challenge pages
            blocked_keywords = ["captcha", "access denied", "403 forbidden", "cloudflare ray id", "robot check"]
            is_blocked = any(kw in text.lower() for kw in blocked_keywords) and len(text) < 1000

            if is_blocked:
                fetch_status = "BLOCKED"
                error_msg = "Retrieved page appears to be a bot challenge or access block."
            elif not text.strip() or len(text.strip()) < 40:
                fetch_status = "EMPTY"
                error_msg = "Retrieved page contains negligible text content."
            else:
                fetch_status = "SUCCESS"
                error_msg = ""

            out = {
                "url": url,
                "title": title,
                "text": text,
                "fetch_status": fetch_status,
                "error_msg": error_msg,
                "fetched_at": datetime.now(timezone.utc).isoformat()
            }
            if fetch_status == "SUCCESS":
                self._cache_fetch[url] = out
            return out

        except Exception as e:
            logger.error(f"TinyFish Fetch SDK error on {url}: {e}")
            return {
                "url": url,
                "title": "Fetch Exception",
                "text": "",
                "fetch_status": "FAILED",
                "error_msg": str(e)
            }
