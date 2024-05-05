from aprs_backend.clients.beacon import BeaconClient
from aprs_backend.clients.beacon import BeaconConfig
import pytest
import asyncio


@pytest.fixture
def beacon_config():
    return BeaconConfig(from_call="TEST-1", latitude=10.2, longitude=55.2, comment="test comment")


@pytest.mark.asyncio
async def test_beacon_client_process(beacon_config, mock_logger):
    queue = asyncio.Queue()

    this_client = BeaconClient(beacon_config, queue, mock_logger)
    await this_client.__process__()
    packet = await queue.get()
    assert packet.latitude == beacon_config.beacon_packet.latitude
    assert packet.comment == beacon_config.beacon_packet.comment
    assert this_client.last_sent


@pytest.mark.asyncio
async def test_beacon_client_process_full(beacon_config, mock_logger):
    queue = asyncio.Queue(maxsize=1)
    queue.put_nowait("test")
    this_client = BeaconClient(beacon_config, queue, mock_logger)
    await this_client.__process__()
    assert this_client.last_sent is None
    assert mock_logger.error.called
