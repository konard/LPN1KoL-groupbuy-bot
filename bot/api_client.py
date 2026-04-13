"""
API client for communicating with the Core API
"""

import aiohttp
import logging
from typing import Dict, Optional, List
from config import config

logger = logging.getLogger(__name__)


class APIClient:
    """Client for Core API communication"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.core_api_url
        self.timeout = aiohttp.ClientTimeout(total=config.core_api_timeout)
        # Persistent session reused across requests to avoid overhead of
        # creating/closing a TCP connection on every API call.
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the persistent session, creating it lazily if needed."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self, method: str, endpoint: str, data: Dict = None, params: Dict = None
    ) -> Optional[Dict]:
        """Make HTTP request to API"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            session = self._get_session()
            async with session.request(
                method=method, url=url, json=data, params=params
            ) as response:
                if response.status >= 400:
                    text = await response.text()
                    logger.error(f"API error {response.status}: {text}")
                    return None
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {e}")
            # Invalidate session so the next request opens a fresh connection
            self._session = None
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    # User methods
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        return await self._request("GET", f"/users/{user_id}/")

    async def get_user_by_platform(
        self, platform: str, platform_user_id: str
    ) -> Optional[Dict]:
        """Get user by platform and platform_user_id"""
        return await self._request(
            "GET",
            "/users/by_platform/",
            params={"platform": platform, "platform_user_id": platform_user_id},
        )

    async def check_user_exists(self, platform: str, platform_user_id: str) -> bool:
        """Check if user exists"""
        result = await self._request(
            "GET",
            "/users/check_exists/",
            params={"platform": platform, "platform_user_id": platform_user_id},
        )
        return result.get("exists", False) if result else False

    async def register_user(self, data: Dict) -> Optional[Dict]:
        """Register a new user"""
        return await self._request("POST", "/users/", data=data)

    async def update_user(self, user_id: int, data: Dict) -> Optional[Dict]:
        """Update user profile"""
        return await self._request("PATCH", f"/users/{user_id}/", data=data)

    async def get_user_balance(self, user_id: int) -> Optional[Dict]:
        """Get user balance"""
        return await self._request("GET", f"/users/{user_id}/balance/")

    async def get_user_role(
        self, platform: str, platform_user_id: str
    ) -> Optional[str]:
        """Get user role"""
        user = await self.get_user_by_platform(platform, platform_user_id)
        return user.get("role") if user else None

    # Session methods
    async def set_user_state(
        self,
        user_id: int,
        dialog_type: str,
        dialog_state: str,
        dialog_data: Dict = None,
    ) -> Optional[Dict]:
        """Set user dialog state"""
        return await self._request(
            "POST",
            "/users/sessions/set_state/",
            data={
                "user_id": user_id,
                "dialog_type": dialog_type,
                "dialog_state": dialog_state,
                "dialog_data": dialog_data or {},
            },
        )

    async def clear_user_state(self, user_id: int) -> Optional[Dict]:
        """Clear user dialog state"""
        return await self._request(
            "POST", "/users/sessions/clear_state/", data={"user_id": user_id}
        )

    # Procurement methods
    async def get_procurements(
        self,
        status: str = None,
        category: int = None,
        city: str = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Get list of procurements"""
        params = {}
        if status:
            params["status"] = status
        if category:
            params["category"] = category
        if city:
            params["city"] = city

        result = await self._request("GET", "/procurements/", params=params)
        if result and isinstance(result, dict) and "results" in result:
            return result["results"][:limit]
        elif result and isinstance(result, list):
            return result[:limit]
        return []

    async def get_procurement_details(
        self, procurement_id: int, user_id: int = None
    ) -> Optional[Dict]:
        """Get procurement details"""
        result = await self._request("GET", f"/procurements/{procurement_id}/")
        if result and user_id:
            # Add can_join based on user participation
            result["user_id"] = user_id
        return result

    async def get_user_procurements(self, user_id: int) -> Optional[Dict]:
        """Get user's procurements (organized and participating)"""
        return await self._request("GET", f"/procurements/user/{user_id}/")

    async def create_procurement(self, data: Dict) -> Optional[Dict]:
        """Create a new procurement"""
        return await self._request("POST", "/procurements/", data=data)

    async def join_procurement(
        self,
        procurement_id: int,
        user_id: int,
        quantity: float,
        amount: float,
        notes: str = "",
    ) -> Optional[Dict]:
        """Join a procurement"""
        return await self._request(
            "POST",
            f"/procurements/{procurement_id}/join/",
            data={
                "user_id": user_id,
                "quantity": quantity,
                "amount": amount,
                "notes": notes,
            },
        )

    async def leave_procurement(
        self, procurement_id: int, user_id: int
    ) -> Optional[Dict]:
        """Leave a procurement"""
        return await self._request(
            "POST", f"/procurements/{procurement_id}/leave/", data={"user_id": user_id}
        )

    async def get_categories(self) -> List[Dict]:
        """Get list of categories"""
        result = await self._request("GET", "/procurements/categories/")
        if result and isinstance(result, dict) and "results" in result:
            return result["results"]
        elif result and isinstance(result, list):
            return result
        return []

    async def check_procurement_access(self, procurement_id: int, user_id: int) -> bool:
        """Check if user has access to procurement chat"""
        result = await self._request(
            "POST",
            f"/procurements/{procurement_id}/check_access/",
            data={"user_id": user_id},
        )
        return result.get("access", False) if result else False

    # Payment methods
    async def create_payment(
        self, user_id: int, amount: float, description: str = ""
    ) -> Optional[Dict]:
        """Create a payment for deposit"""
        return await self._request(
            "POST",
            "/payments/",
            data={"user_id": user_id, "amount": amount, "description": description},
        )

    async def get_payment_status(self, payment_id: int) -> Optional[Dict]:
        """Get payment status"""
        return await self._request("GET", f"/payments/{payment_id}/status/")

    async def get_payment_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's payment history"""
        result = await self._request("GET", "/payments/", params={"user_id": user_id})
        if result and isinstance(result, dict) and "results" in result:
            return result["results"][:limit]
        elif result and isinstance(result, list):
            return result[:limit]
        return []

    # Chat methods
    async def get_unread_count(self, user_id: int, procurement_id: int) -> int:
        """Get unread message count"""
        result = await self._request(
            "GET",
            "/chat/messages/unread_count/",
            params={"user_id": user_id, "procurement_id": procurement_id},
        )
        return result.get("unread_count", 0) if result else 0

    async def get_notifications(
        self, user_id: int, unread_only: bool = True
    ) -> List[Dict]:
        """Get user notifications"""
        params = {"user_id": user_id}
        if unread_only:
            params["unread_only"] = "true"

        result = await self._request("GET", "/chat/notifications/", params=params)
        if result and isinstance(result, dict) and "results" in result:
            return result["results"]
        elif result and isinstance(result, list):
            return result
        return []


# Singleton instance
api_client = APIClient()
