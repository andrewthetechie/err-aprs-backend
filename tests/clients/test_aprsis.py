import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.mark.asyncio
async def test_disconnect_succeeds_when_writer_is_none(mock_logger):
    """disconnect() should succeed when called on a freshly-constructed client where _writer is None."""
    client = APRSISClient(
        callsign="TEST-1",
        password="1234",
        logger=mock_logger,
    )
    assert client._writer is None
    assert client._reader is None
    await client.disconnect()
    assert client._writer is None
    assert client._reader is None
    assert client.connected is False


@pytest.mark.asyncio
async def test_disconnect_is_idempotent(mock_logger):
    """Calling disconnect() twice in a row should not raise."""
    client = APRSISClient(
        callsign="TEST-1",
        password="1234",
        logger=mock_logger,
    )
    await client.disconnect()
    await client.disconnect()
    assert client.connected is False


@pytest.mark.asyncio
async def test_disconnect_closes_writer_and_resets_state(mock_logger):
    """When _writer is present, close() and wait_closed() should be called, and state reset."""
    client = APRSISClient(
        callsign="TEST-1",
        password="1234",
        logger=mock_logger,
    )
    mock_writer = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_reader = MagicMock()
    client._writer = mock_writer
    client._reader = mock_reader
    client.connected = True

    await client.disconnect()

    mock_writer.close.assert_called_once()
    mock_writer.wait_closed.assert_awaited_once()
    assert client._writer is None
    assert client._reader is None
    assert client.connected is False
