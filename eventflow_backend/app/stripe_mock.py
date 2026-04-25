class StripePaymentError(ValueError):
    """Raised when the mock Stripe charge is rejected."""

    pass


class StripeMock:
    """Minimal mock of Stripe payment confirmation."""

    allowed_card_number = "4242424242424242"

    def charge(self, card_number: str, amount_cents: int) -> str:
        """Charge a test card and return a payment identifier."""

        normalized = card_number.replace(" ", "").replace("-", "")
        if amount_cents <= 0:
            raise StripePaymentError("Payment amount must be positive")
        if normalized != self.allowed_card_number:
            raise StripePaymentError("Card declined")
        return f"mock_payment_{normalized[-4:]}"


stripe_client = StripeMock()
