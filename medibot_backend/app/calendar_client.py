from datetime import datetime
from typing import Any


class GoogleCalendarMock:
    def __init__(self, calendar_id: str = "primary") -> None:
        self.calendar_id = calendar_id

    async def create_event(
        self,
        summary: str,
        start_at: datetime,
        end_at: datetime,
        attendees: list[str],
    ) -> dict[str, Any]:
        return {
            "id": f"mock-google-calendar-{int(start_at.timestamp())}",
            "calendarId": self.calendar_id,
            "summary": summary,
            "start": {"dateTime": start_at.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_at.isoformat(), "timeZone": "UTC"},
            "attendees": [{"email": email} for email in attendees],
            "status": "confirmed",
        }
