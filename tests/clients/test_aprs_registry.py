from aprs_backend.clients import RegistryAppConfig, APRSRegistryClient
import pytest
import asyncio
from unittest.mock import MagicMock

from logging import getLogger
import httpx


@pytest.fixture
def registry_app_config():
    return RegistryAppConfig(
        description="description", listening_callsigns=["TEST-1"], website="website", software="software"
    )


parameters = [
    ("testing", ["TEST-1"], "http://test.test", "testsoftware"),
    ("testing", ["TEST-1", "TEST-2"], "http://test.test", "testsoftware"),
    ("testing", ["TEST-1", "TEST-2", "EMLSRVR"], "https://test.test", "othersoftware"),
]


@pytest.mark.parametrize("description,listening_callsigns,website,software", parameters)
def test_RegistryAppConfig(description, listening_callsigns, website, software):
    this_RegistryAppConfig = RegistryAppConfig(
        description=description, listening_callsigns=listening_callsigns, website=website, software=software
    )

    assert len(this_RegistryAppConfig.post_jsons) == len(listening_callsigns)
    assert {post_json["callsign"] for post_json in this_RegistryAppConfig.post_jsons} == set(listening_callsigns)
    assert this_RegistryAppConfig.post_jsons[0]["description"] == description
    assert this_RegistryAppConfig.post_jsons[0]["service_website"] == website
    assert this_RegistryAppConfig.post_jsons[0]["software"] == software


class MockLogger:
    def __init__(self):
        self.debug = MagicMock()
        self.error = MagicMock()
        self.info = MagicMock()


@pytest.mark.asyncio
async def test_APRSRegistryClient_oneshot(httpx_mock, registry_app_config):
    httpx_mock.add_response(method="POST")

    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com", log=getLogger(__name__), app_config=registry_app_config
    )
    task = asyncio.create_task(this_APRSRegistryClient())
    # sleep to let the task run
    await asyncio.sleep(0.1)
    task.cancel()


@pytest.mark.asyncio
async def test_APRSRegistryClient_repeats(httpx_mock, registry_app_config):
    httpx_mock.add_response(method="POST")
    httpx_mock.add_response(method="POST")
    httpx_mock.add_response(method="POST")

    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com", log=getLogger(__name__), app_config=registry_app_config, frequency_seconds=1
    )
    task = asyncio.create_task(this_APRSRegistryClient())
    # sleep 4 seconds to let the task run and make multiple requests
    await asyncio.sleep(4)
    task.cancel()


@pytest.mark.asyncio
async def test_APRSRegistryClient_errors(httpx_mock, registry_app_config):
    httpx_mock.add_response(method="POST", status_code=422)

    log = MockLogger()
    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com",
        log=log,
        app_config=registry_app_config,
    )
    task = asyncio.create_task(this_APRSRegistryClient())
    # sleep to let the task run and make its failed request
    await asyncio.sleep(0.1)
    task.cancel()
    assert log.error.called


@pytest.mark.asyncio
async def test_APRSRegistryClient_repeats_and_errors(httpx_mock, registry_app_config):
    httpx_mock.add_response(method="POST")
    httpx_mock.add_exception(httpx.ReadTimeout("Unable to read within timeout"))
    httpx_mock.add_response(method="POST")

    log = MockLogger()
    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com", log=log, app_config=registry_app_config, frequency_seconds=1
    )
    task = asyncio.create_task(this_APRSRegistryClient())
    # sleep 4 seconds to let the task run and make multiple requests
    await asyncio.sleep(4)
    task.cancel()
    assert log.error.called
