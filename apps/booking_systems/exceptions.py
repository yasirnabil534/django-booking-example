"""
Custom exceptions for the BookingSystemClient.

Hierarchy:
    BookingAPIError
    ├── AuthenticationError   (401)
    ├── RateLimitError        (429)
    ├── ClientError           (other 4xx)
    └── ServerError           (5xx)
"""


class BookingAPIError(Exception):
    """Base exception for all Easy!Appointments API errors."""

    def __init__(self, message: str, status_code: int | None = None, url: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.url = url

    def __str__(self):
        parts = [super().__str__()]
        if self.status_code:
            parts.append(f"[HTTP {self.status_code}]")
        if self.url:
            parts.append(f"URL: {self.url}")
        return " ".join(parts)


class AuthenticationError(BookingAPIError):
    """Raised when credentials are rejected (HTTP 401)."""


class RateLimitError(BookingAPIError):
    """Raised when the server throttles requests (HTTP 429)."""

    def __init__(self, message: str, retry_after: int = 30, url: str | None = None):
        super().__init__(message, status_code=429, url=url)
        self.retry_after = retry_after


class ClientError(BookingAPIError):
    """Raised for unexpected 4xx responses."""


class ServerError(BookingAPIError):
    """Raised when the server returns a 5xx after all retries are exhausted."""
