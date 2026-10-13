import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.ingestion.fetcher import SAPNoteFetcher
from src.ingestion.parser import ParsedNote


@pytest.fixture
def fetcher():
    return SAPNoteFetcher(
        api_base_url="https://sap-api.example.com",
        api_key="test-key",
        retry_attempts=2,
        retry_backoff_seconds=0,
    )


@pytest.fixture
def mock_api_response():
    return {
        "results": [
            {
                "note_number": "3421384",
                "title": "RFC Vulnerability",
                "cvss_score": 8.5,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                "priority": "high",
                "components": ["SAP_BASIS"],
                "version_ranges_raw": ["7.50-7.89"],
                "release_date": "2026-06-10",
                "description": "Critical RFC vulnerability.",
                "solution_type": "patch",
                "related_notes": [],
            }
        ]
    }


@pytest.mark.asyncio
async def test_fetch_latest_success(fetcher, mock_api_response):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        results = await fetcher.fetch_latest()
        assert len(results) == 1
        assert isinstance(results[0], ParsedNote)
        assert results[0].note_number == "3421384"


@pytest.mark.asyncio
async def test_fetch_latest_retries_on_failure(fetcher):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [
            Exception("Connection refused"),
            Exception("Connection refused"),
        ]
        with pytest.raises(Exception, match="Connection refused"):
            await fetcher.fetch_latest()
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_fetch_latest_empty_response(fetcher):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        results = await fetcher.fetch_latest()
        assert results == []
