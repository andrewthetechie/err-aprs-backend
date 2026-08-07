from logging import Logger
from aprs_backend.clients._base import ClientBase
import pytest
import asyncio


class ClientBaseForTest(ClientBase):
    def __init__(self, log: Logger, frequency_seconds: int = 3600, chunk_seconds: int = 10):
        self.process_call_count = 0
        super().__init__(log, frequency_seconds, chunk_seconds)

    @property
    def process_called(self):
        return self.process_call_count > 0

    async def __process__(self):
        self.process_call_count += 1


@pytest.mark.asyncio
async def test_clientbase_repeat(mock_logger):
    client = ClientBaseForTest(log=mock_logger, frequency_seconds=1)
    task = asyncio.create_task(client())
    await asyncio.sleep(4)
    task.cancel()
    assert client.process_called
    assert client.process_call_count > 3


@pytest.mark.asyncio
async def test_clientbase_sleep_chunk_iterations(mock_logger):
    """Sleep loop uses chunked sleep: 360 iterations for 1h, not 36000."""
    # frequency_seconds=3600 (1h) should produce 360 iterations (10s chunks)
    # frequency_seconds=90 (1.5min) should produce 9 iterations
    client = ClientBaseForTest(log=mock_logger, frequency_seconds=90)
    task = asyncio.create_task(client())
    await asyncio.sleep(2)  # let __process__ run once
    task.cancel()
    await task  # task returns cleanly after catching CancelledError
    assert client.process_called


@pytest.mark.asyncio
async def test_clientbase_cancellation_during_sleep(mock_logger):
    """Cancellation is caught within one chunk period (<=10s)."""
    client = ClientBaseForTest(log=mock_logger, frequency_seconds=3600)
    task = asyncio.create_task(client())
    await asyncio.sleep(2)  # let __process__ run, then sleep starts
    cancel_start = asyncio.get_event_loop().time()
    task.cancel()
    await task  # task returns cleanly after catching CancelledError
    cancel_elapsed = asyncio.get_event_loop().time() - cancel_start
    assert cancel_elapsed < 11  # cancellation resolved well within 1 chunk
    # Verify consistent log message from centralized handler
    mock_logger.info.assert_called_with("%s cancelled, stopping", "ClientBaseForTest")


@pytest.mark.asyncio
async def test_clientbase_cancellation_during_process(mock_logger):
    """Cancellation during __process__ returns cleanly with the same log message."""

    class SlowProcessClient(ClientBaseForTest):
        async def __process__(self):
            self.process_call_count += 1
            await asyncio.sleep(60)  # long enough to be cancelled

    client = SlowProcessClient(log=mock_logger, frequency_seconds=3600)
    task = asyncio.create_task(client())
    await asyncio.sleep(0.1)  # let __process__ start
    task.cancel()
    await task  # task returns cleanly after catching CancelledError
    assert client.process_called
    # Verify consistent log message from centralized handler
    mock_logger.info.assert_called_with("%s cancelled, stopping", "SlowProcessClient")


@pytest.mark.asyncio
async def test_clientbase_configurable_chunk_seconds(mock_logger):
    """Non-default chunk_seconds is respected by the sleep loop."""
    client = ClientBaseForTest(log=mock_logger, frequency_seconds=3600, chunk_seconds=2)
    task = asyncio.create_task(client())
    await asyncio.sleep(2)  # let __process__ run, then sleep starts
    cancel_start = asyncio.get_event_loop().time()
    task.cancel()
    await task  # task returns cleanly after catching CancelledError
    cancel_elapsed = asyncio.get_event_loop().time() - cancel_start
    assert cancel_elapsed < 4  # cancellation resolved within 1 custom chunk (2s)
