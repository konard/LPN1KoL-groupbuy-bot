class EventFlowError(Exception):
    """Base domain error mapped to an HTTP response."""

    status_code = 400
    code = "eventflow_error"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class EventNotFoundError(EventFlowError):
    """Raised when an event cannot be found."""

    status_code = 404
    code = "event_not_found"


class TicketNotFoundError(EventFlowError):
    """Raised when a ticket cannot be found."""

    status_code = 404
    code = "ticket_not_found"


class SoldOutError(EventFlowError):
    """Raised when an event has no available tickets."""

    status_code = 409
    code = "sold_out"


class PaymentRejectedError(EventFlowError):
    """Raised when the mock payment provider rejects a charge."""

    status_code = 402
    code = "payment_rejected"


class RateLimitExceededError(EventFlowError):
    """Raised when a caller exceeds the configured request limit."""

    status_code = 429
    code = "rate_limit_exceeded"


class ForbiddenTicketError(EventFlowError):
    """Raised when a caller cannot mutate a ticket."""

    status_code = 403
    code = "forbidden_ticket"
