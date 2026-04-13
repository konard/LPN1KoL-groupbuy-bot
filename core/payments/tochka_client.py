"""
Tochka Bank Cyclops API Client

Cyclops is Tochka Bank's service for nominal accounts used by online platforms.
This client handles payment operations through the Cyclops API.

Documentation: https://docs.tochka.com/cyclops
"""
import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict

import requests
from django.conf import settings
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class TochkaCyclopsError(Exception):
    """Exception for Tochka Cyclops API errors"""
    def __init__(self, message: str, code: str = None, details: Dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class TochkaCyclopsClient:
    """
    Client for Tochka Bank Cyclops API

    Cyclops is a service for online platforms that provides:
    - Nominal account management
    - Participant virtual accounts
    - Payment processing
    - Payouts to participants
    """

    def __init__(self):
        self.api_url = getattr(settings, 'TOCHKA_API_URL', 'https://pre.tochka.com/api/v1/cyclops')
        self.nominal_account = getattr(settings, 'TOCHKA_NOMINAL_ACCOUNT', '')
        self.platform_id = getattr(settings, 'TOCHKA_PLATFORM_ID', '')
        self.private_key_path = getattr(settings, 'TOCHKA_PRIVATE_KEY_PATH', '')
        self.timeout = 30
        self._private_key = None

    @property
    def is_configured(self) -> bool:
        """Check if Tochka Cyclops is properly configured"""
        return bool(
            self.nominal_account and
            self.platform_id and
            self.private_key_path
        )

    def _load_private_key(self):
        """Load private key for request signing"""
        if self._private_key is None:
            try:
                with open(self.private_key_path, 'rb') as key_file:
                    self._private_key = serialization.load_pem_private_key(
                        key_file.read(),
                        password=None,
                        backend=default_backend()
                    )
            except Exception as e:
                logger.error(f"Failed to load Tochka private key: {e}")
                raise TochkaCyclopsError(f"Failed to load private key: {e}")
        return self._private_key

    def _sign_request(self, body: str) -> str:
        """Sign request body with RSA private key"""
        private_key = self._load_private_key()
        signature = private_key.sign(
            body.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        import base64
        return base64.b64encode(signature).decode('utf-8')

    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        return str(uuid.uuid4())

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make authenticated request to Cyclops API"""
        if not self.is_configured:
            raise TochkaCyclopsError("Tochka Cyclops is not configured")

        url = f"{self.api_url}/{endpoint}"
        request_id = self._generate_request_id()

        headers = {
            'Content-Type': 'application/json',
            'X-Request-Id': request_id,
            'X-Platform-Id': self.platform_id,
        }

        body = json.dumps(data) if data else ''
        if body:
            headers['X-Signature'] = self._sign_request(body)

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=body if body else None,
                timeout=self.timeout
            )

            logger.info(f"Tochka API request: {method} {endpoint}, status: {response.status_code}")

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise TochkaCyclopsError(
                    message=error_data.get('message', 'API error'),
                    code=error_data.get('code'),
                    details=error_data
                )

            return response.json() if response.content else {}

        except requests.RequestException as e:
            logger.error(f"Tochka API request failed: {e}")
            raise TochkaCyclopsError(f"Request failed: {e}")

    # ==========================================
    # Virtual Account Operations
    # ==========================================

    def create_virtual_account(self, user_id: int, user_name: str) -> Dict:
        """
        Create a virtual account for a user on the platform

        In Cyclops, each participant has a virtual account within the nominal account.
        """
        data = {
            "nominalAccountNumber": self.nominal_account,
            "participant": {
                "externalId": str(user_id),
                "name": user_name,
                "type": "individual"
            }
        }

        result = self._make_request('POST', 'virtual-accounts', data)
        logger.info(f"Created virtual account for user {user_id}")
        return result

    def get_virtual_account(self, user_id: int) -> Optional[Dict]:
        """Get virtual account details by user ID"""
        try:
            result = self._make_request(
                'GET',
                f'virtual-accounts?externalId={user_id}&nominalAccount={self.nominal_account}'
            )
            return result.get('items', [None])[0]
        except TochkaCyclopsError:
            return None

    def get_virtual_account_balance(self, virtual_account_id: str) -> Decimal:
        """Get virtual account balance"""
        result = self._make_request('GET', f'virtual-accounts/{virtual_account_id}/balance')
        return Decimal(str(result.get('availableBalance', 0)))

    # ==========================================
    # Payment Operations
    # ==========================================

    def create_deposit_link(
        self,
        user_id: int,
        amount: Decimal,
        description: str = '',
        return_url: str = ''
    ) -> Dict:
        """
        Create a payment link for user to deposit funds

        Returns a URL where user can make the payment.
        """
        order_id = f"DEP-{user_id}-{int(datetime.now().timestamp())}"

        data = {
            "nominalAccountNumber": self.nominal_account,
            "amount": str(amount),
            "currency": "RUB",
            "orderId": order_id,
            "description": description or f"Deposit {amount} RUB",
            "participant": {
                "externalId": str(user_id)
            },
            "returnUrl": return_url or ""
        }

        result = self._make_request('POST', 'payments/deposits', data)

        return {
            'payment_id': result.get('paymentId'),
            'order_id': order_id,
            'confirmation_url': result.get('paymentUrl'),
            'status': 'pending'
        }

    def get_payment_status(self, payment_id: str) -> Dict:
        """Get payment status from Cyclops"""
        result = self._make_request('GET', f'payments/{payment_id}')

        # Map Cyclops status to our internal status
        cyclops_status = result.get('status', '').lower()
        status_map = {
            'pending': 'pending',
            'processing': 'pending',
            'succeeded': 'succeeded',
            'completed': 'succeeded',
            'failed': 'cancelled',
            'cancelled': 'cancelled',
            'refunded': 'refunded'
        }

        return {
            'payment_id': payment_id,
            'status': status_map.get(cyclops_status, 'pending'),
            'amount': Decimal(str(result.get('amount', 0))),
            'paid_at': result.get('completedAt'),
            'raw': result
        }

    # ==========================================
    # Payout Operations
    # ==========================================

    def create_payout(
        self,
        user_id: int,
        amount: Decimal,
        recipient_details: Dict,
        description: str = ''
    ) -> Dict:
        """
        Create a payout from user's virtual account to external bank account

        recipient_details should contain:
        - bankName: Bank name
        - bik: Bank BIK
        - accountNumber: Account number
        - recipientName: Recipient full name
        """
        order_id = f"PAY-{user_id}-{int(datetime.now().timestamp())}"

        data = {
            "nominalAccountNumber": self.nominal_account,
            "amount": str(amount),
            "currency": "RUB",
            "orderId": order_id,
            "description": description or f"Payout {amount} RUB",
            "participant": {
                "externalId": str(user_id)
            },
            "recipient": recipient_details
        }

        result = self._make_request('POST', 'payments/payouts', data)

        return {
            'payout_id': result.get('payoutId'),
            'order_id': order_id,
            'status': result.get('status', 'pending')
        }

    # ==========================================
    # Transfer Operations (between participants)
    # ==========================================

    def transfer_between_participants(
        self,
        from_user_id: int,
        to_user_id: int,
        amount: Decimal,
        description: str = ''
    ) -> Dict:
        """
        Transfer funds between two participants on the platform

        Used for procurement payments from buyers to organizers.
        """
        order_id = f"TRF-{from_user_id}-{to_user_id}-{int(datetime.now().timestamp())}"

        data = {
            "nominalAccountNumber": self.nominal_account,
            "amount": str(amount),
            "currency": "RUB",
            "orderId": order_id,
            "description": description or f"Transfer {amount} RUB",
            "fromParticipant": {
                "externalId": str(from_user_id)
            },
            "toParticipant": {
                "externalId": str(to_user_id)
            }
        }

        result = self._make_request('POST', 'payments/transfers', data)

        return {
            'transfer_id': result.get('transferId'),
            'order_id': order_id,
            'status': result.get('status', 'pending')
        }

    # ==========================================
    # Webhook Verification
    # ==========================================

    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        """
        Verify webhook signature from Tochka

        Tochka signs webhooks with their private key, we verify with their public key.
        """
        # In production, load Tochka's public key and verify
        # For now, return True in development mode
        if 'pre.tochka.com' in self.api_url:
            logger.warning("Webhook signature verification skipped in pre-production")
            return True

        # TODO: Implement actual signature verification with Tochka's public key
        return True


# Singleton instance
tochka_client = TochkaCyclopsClient()
