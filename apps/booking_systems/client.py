"""
BookingSystemClient — a reusable HTTP client for Easy!Appointments v1 REST API.

Features
--------
- requests.Session for connection reuse and persistent Basic Auth
- Structured logging: method, URL, status code, response time
- 4xx  → raise immediately (no retry)
- 5xx  → exponential-backoff retry (max 3 attempts: 1s, 2s, 4s)
- 429  → respect Retry-After header (default 30s), then retry
- Timeout / ConnectionError → backoff retry (max 3 attempts)
"""

import logging
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import AuthenticationError, ClientError, RateLimitError, ServerError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_API_PATH = "/index.php/api/v1"
_DEFAULT_TIMEOUT = 10          # seconds per request
_MAX_RETRIES = 3               # max attempts for 5xx / network errors
_BACKOFF_BASE = 1              # seconds — doubles each retry (1 → 2 → 4)
_DEFAULT_RATE_LIMIT_WAIT = 30  # seconds to wait on 429 with no Retry-After
_PAGE_SIZE = 500               # Records per page (EA default is 20)
_INTER_PAGE_DELAY = 1.0        # Seconds to sleep between pages to avoid 429


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class BookingSystemClient:
    """
    Reusable client for the Easy!Appointments REST API.

    Usage
    -----
        client = BookingSystemClient(
            base_url="http://localhost:8888",
            username="admin",
            password="admin123",
        )
        if client.test_connection():
            providers = client.get_providers()
    """

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_base = f"{self.base_url}{_API_PATH}"

        # Session with persistent auth and a transport-level retry adapter
        # (handles low-level TCP failures only — application-level retries
        #  are handled manually so we can implement custom backoff / logging)
        self._session = requests.Session()
        self._session.auth = (username, password)
        self._session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        # Mount a minimal transport adapter (no automatic application retries)
        adapter = HTTPAdapter(max_retries=Retry(total=0))
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        """
        Verify credentials work by fetching providers.

        Returns True on success, False if authentication fails.
        Raises other exceptions for unexpected errors.
        """
        try:
            self._get("providers")
            return True
        except AuthenticationError:
            return False

    def get_providers(self) -> list[dict]:
        """Fetch all providers (staff members)."""
        return self._get("providers")

    def get_customers(self) -> list[dict]:
        """Fetch all customers."""
        return self._get("customers")

    def get_services(self) -> list[dict]:
        """Fetch all services."""
        return self._get("services")

    def get_appointments(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """
        Fetch appointments, optionally filtered by date range.

        Parameters
        ----------
        start_date : str, optional
            ISO date string ``YYYY-MM-DD``. Filters appointments with
            ``start >= start_date 00:00:00``.
        end_date : str, optional
            ISO date string ``YYYY-MM-DD``. Filters appointments with
            ``start <= end_date 23:59:59``.
        """
        params: dict = {}
        if start_date:
            params["start_datetime"] = f"{start_date} 00:00:00"
        if end_date:
            params["end_datetime"] = f"{end_date} 23:59:59"
        return self._get("appointments", params=params)

    # ------------------------------------------------------------------
    # Internal request machinery
    # ------------------------------------------------------------------

    def _get(self, resource: str, params: Optional[dict] = None) -> list[dict]:
        """
        Perform a paginated GET, fetching all records from the endpoint.

        Pagination logic:
          - Fetch page with `length=500&start=0`
          - If response has exactly 500 → fetch next page with `start=500`
          - If response has < 500 → last page, stop
        Returns the complete list of all records across all pages.
        """
        url = f"{self._api_base}/{resource}"
        all_records: list[dict] = []
        start = 0

        while True:
            page_params = {**(params or {}), "length": _PAGE_SIZE, "start": start}
            page = self._get_page(url, page_params)

            if not page:
                break

            all_records.extend(page)
            logger.debug("%s: fetched %d records (offset %d, total so far %d)", resource, len(page), start, len(all_records))

            if len(page) < _PAGE_SIZE:
                break  # last (partial) page — we're done

            start += _PAGE_SIZE
            time.sleep(_INTER_PAGE_DELAY)  # avoid rate-limiting on next page

        logger.info("%s: fetched %d total records", resource, len(all_records))
        return all_records

    def _get_page(self, url: str, params: dict) -> list[dict]:
        """
        Fetch one page with retry / rate-limit / error handling.
        Returns the parsed JSON list for this page.
        """
        attempt = 0

        while True:
            attempt += 1
            response = self._send_request("GET", url, params=params)

            if response is None:
                raise ServerError(
                    f"Request to {url} failed after {_MAX_RETRIES} attempts (network error).",
                    url=url,
                )

            status = response.status_code

            if status == 200:
                return response.json()

            if status == 401:
                raise AuthenticationError(
                    "Invalid credentials — check username and password.",
                    status_code=401, url=url,
                )

            if status == 429:
                wait = int(response.headers.get("Retry-After", _DEFAULT_RATE_LIMIT_WAIT))
                logger.warning("Rate limited by %s — waiting %ss (attempt %d/%d)", url, wait, attempt, _MAX_RETRIES)
                time.sleep(wait)
                continue

            if 400 <= status < 500:
                raise ClientError(f"Client error from {url}: {response.text[:200]}", status_code=status, url=url)

            if status >= 500:
                if attempt >= _MAX_RETRIES:
                    raise ServerError(f"Server error from {url} after {_MAX_RETRIES} attempts.", status_code=status, url=url)
                wait = _BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning("Server error %d from %s — retrying in %ss (attempt %d/%d)", status, url, wait, attempt, _MAX_RETRIES)
                time.sleep(wait)
                continue

    def _send_request(
        self, method: str, url: str, **kwargs
    ) -> Optional[requests.Response]:
        """
        Send an HTTP request, handling connection/timeout errors with backoff.
        Returns the Response object, or None if all retries are exhausted.
        """
        for attempt in range(1, _MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                response = self._session.request(
                    method, url, timeout=_DEFAULT_TIMEOUT, **kwargs
                )
                elapsed = (time.monotonic() - t0) * 1000
                logger.info(
                    "%s %s → %d (%.0fms)",
                    method, url, response.status_code, elapsed,
                )
                return response

            except requests.exceptions.Timeout:
                elapsed = (time.monotonic() - t0) * 1000
                logger.warning(
                    "%s %s timed out after %.0fms (attempt %d/%d)",
                    method, url, elapsed, attempt, _MAX_RETRIES,
                )
            except requests.exceptions.ConnectionError as exc:
                logger.warning(
                    "%s %s connection error (attempt %d/%d): %s",
                    method, url, attempt, _MAX_RETRIES, exc,
                )

            if attempt < _MAX_RETRIES:
                wait = _BACKOFF_BASE * (2 ** (attempt - 1))
                time.sleep(wait)

        return None  # all retries exhausted
