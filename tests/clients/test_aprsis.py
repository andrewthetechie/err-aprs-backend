import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aprs_backend.clients import APRSISClient
from aprs_backend.exceptions.client.aprsis import APRSISConnnectError, APRSISLoginError


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


@pytest.mark.asyncio
async def test_disconnect_resets_state_when_wait_closed_raises(mock_logger):
    """When wait_closed() raises, disconnect() should still reset state."""
    client = APRSISClient(
        callsign="TEST-1",
        password="1234",
        logger=mock_logger,
    )
    mock_writer = MagicMock()
    mock_writer.wait_closed = AsyncMock(side_effect=ConnectionResetError("connection reset"))
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


def test_default_login_read_timeout(aprsis_client):
    """Default login read timeout should be 10 seconds."""
    assert aprsis_client._login_read_timeout == 10.0


def test_custom_login_read_timeout(mock_logger):
    """Custom login read timeout should be respected."""
    client = APRSISClient(
        callsign="TEST-1",
        password="1234",
        login_read_timeout=20.0,
        logger=mock_logger,
    )
    assert client._login_read_timeout == 20.0


@pytest.mark.asyncio
async def test_login_read_timeout_used_in_wait_for(mock_logger):
    """asyncio.wait_for should be called with the configured login_read_timeout."""
    client = APRSISClient(
        callsign="TEST-1",
        password="1234",
        host="test.aprs2.net",
        port=14580,
        login_read_timeout=15.0,
        logger=mock_logger,
    )

    wait_for_calls = []
    call_count = [0]

    async def mock_wait_for(coro, timeout=None):
        call_count[0] += 1
        wait_for_calls.append(timeout)
        if call_count[0] == 1:
            return b"APRS-IS Linux 3.0.19+gcc12.2.0"
        raise TimeoutError("mock timeout")

    mock_reader = MagicMock()
    mock_reader.readline = AsyncMock()
    client._reader = mock_reader
    mock_writer = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    client._writer = mock_writer
    client._writer.write = MagicMock()
    client._writer.drain = AsyncMock()

    with patch.object(asyncio, "wait_for", mock_wait_for):
        with pytest.raises(APRSISLoginError):
            await client._send_login()

    # Both readline calls should be wrapped with the configured timeout
    assert len(wait_for_calls) == 2
    assert wait_for_calls[0] == 15.0
    assert wait_for_calls[1] == 15.0


@pytest.mark.asyncio
async def test_login_read_timeout_raises_on_slow_server(mock_logger):
    """When readline times out, APRSISLoginError should be raised."""
    client = APRSISClient(
        callsign="TEST-1",
        password="1234",
        host="test.aprs2.net",
        port=14580,
        login_read_timeout=0.1,
        logger=mock_logger,
    )

    async def slow_readline():
        await asyncio.sleep(10)
        return b"version"

    mock_reader = MagicMock()
    mock_reader.readline = slow_readline
    client._reader = mock_reader
    mock_writer = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    client._writer = mock_writer
    client._writer.write = MagicMock()
    client._writer.drain = AsyncMock()

    with pytest.raises(APRSISLoginError, match="Timed out waiting for APRS-IS login response after 0.1s"):
        await client._send_login()
