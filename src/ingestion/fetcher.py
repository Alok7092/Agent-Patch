import asyncio
import httpx
from src.ingestion.parser import parse_note, ParsedNote


class SAPNoteFetcher:
    def __init__(
        self,
        api_base_url: str,
        api_key: str,
        retry_attempts: int = 3,
        retry_backoff_seconds: int = 5,
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key
        self.retry_attempts = retry_attempts
        self.retry_backoff_seconds = retry_backoff_seconds

    async def fetch_latest(self) -> list[ParsedNote]:
        return await self._request("/api/v1/security-notes/latest")

    async def fetch_by_number(self, note_number: str) -> ParsedNote:
        results = await self._request(f"/api/v1/security-notes/{note_number}")
        if not results:
            raise ValueError(f"Note {note_number} not found")
        return results[0]

    async def _request(self, path: str) -> list[ParsedNote]:
        last_error = None
        for attempt in range(self.retry_attempts):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.api_base_url}{path}",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    raw_notes = data.get("results", [])
                    return [parse_note(raw) for raw in raw_notes]
            except Exception as e:
                last_error = e
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_backoff_seconds)
        raise last_error
