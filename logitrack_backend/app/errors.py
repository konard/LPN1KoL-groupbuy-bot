class LogiTrackError(Exception):
    """Base domain error mapped to an HTTP response."""

    status_code = 400
    code = "logitrack_error"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class OrderNotFoundError(LogiTrackError):
    """Raised when an order cannot be found."""

    status_code = 404
    code = "order_not_found"


class RateLimitExceededError(LogiTrackError):
    """Raised when a caller exceeds the configured request limit."""

    status_code = 429
    code = "rate_limit_exceeded"
