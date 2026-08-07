import asyncio
import pytest
from unittest.mock import patch

from aprs_backend.clients import APRSISClient
from aprs_backend.exceptions.client.aprsis import APRSISConnnectError


@pytest.fixture
def aprsis_client(mock_logger):
    return APRSISClient(
        callsign="TEST-1",
        password="1234",
        host="test.aprs2.net",
        port=14580,
        logger=mock_logger,
    )


def test_default_connect_timeout(aprsis_client):
    """Default connect timeout should be 30 seconds."""
    assert aprsis_client._connect_timeout == 30.0


def test_custom_connect_timeout(mock_logger):
    """Custom connect timeout should be respected."""
    client = APRSISClient(
        callsign="TEST-1",
        password="1234",
        connect_timeout=60.0,
        logger=mock_logger,
    )
    assert client._connect_timeout == 60.0


@pytest.mark.asyncio
async def test_connect_timeout_raises_on_unreachable(mock_logger):
    """Connection to an unreachable host should raise APRSISConnnectError after timeout."""
    client = APRSISClient(
        callsign="TEST-1",
        password="1234",
        host="192.0.2.1",  # TEST-NET address that should be unreachable
        port=14580,
        connect_timeout=0.5,
        logger=mock_logger,
    )
    with pytest.raises(APRSISConnnectError):
        await client.connect()


@pytest.mark.asyncio
async def test_connect_timeout_used_in_wait_for(mock_logger):
    """asyncio.wait_for should be called with the configured timeout."""
    client = APRSISClient(
        callsign="TEST-1",
        password="1234",
        host="test.aprs2.net",
        port=14580,
        connect_timeout=45.0,
        logger=mock_logger,
    )

    wait_for_called_with = {}

    async def mock_wait_for(coro, timeout=None):
        wait_for_called_with["timeout"] = timeout
        raise TimeoutError("mock timeout")

    with patch.object(asyncio, "wait_for", mock_wait_for):
        with pytest.raises(APRSISConnnectError):
            await client.connect()

    assert wait_for_called_with["timeout"] == 45.0
