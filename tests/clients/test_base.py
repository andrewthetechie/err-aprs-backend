from logging import Logger
from aprs_backend.clients._base import ClientBase
import pytest
import asyncio


class TestClient(ClientBase):
    def __init__(self, log: Logger, frequency_seconds: int = 3600):
        self.process_call_count = 0
        super().__init__(log, frequency_seconds)

    @property
    def process_called(self):
        return self.process_call_count > 0

    async def __process__(self):
        self.process_call_count += 1


@pytest.mark.asyncio
async def test_clientbase_repeat(mock_logger):
    client = TestClient(log=mock_logger, frequency_seconds=1)
    task = asyncio.create_task(client())
    await asyncio.sleep(4)
    task.cancel()
    assert client.process_called
    assert client.process_call_count > 3
