from aprs_backend.clients import RegistryAppConfig, APRSRegistryClient
import pytest

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


@pytest.mark.asyncio
async def test_APRSRegistryClient_oneshot(httpx_mock, registry_app_config):
    httpx_mock.add_response(method="POST")

    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com", log=getLogger(__name__), app_config=registry_app_config
    )
    await this_APRSRegistryClient.__process__()


@pytest.mark.asyncio
async def test_APRSRegistryClient_errors(httpx_mock, mock_logger, registry_app_config):
    httpx_mock.add_response(method="POST", status_code=422)

    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com",
        log=mock_logger,
        app_config=registry_app_config,
    )
    await this_APRSRegistryClient.__process__()
    assert mock_logger.error.called


@pytest.mark.asyncio
async def test_APRSRegistryClient_repeats_and_errors(httpx_mock, mock_logger, registry_app_config):
    httpx_mock.add_response(method="POST")
    httpx_mock.add_exception(httpx.ReadTimeout("Unable to read within timeout"))
    httpx_mock.add_response(method="POST")

    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com", log=mock_logger, app_config=registry_app_config, frequency_seconds=1
    )
    await this_APRSRegistryClient.__process__()
    await this_APRSRegistryClient.__process__()
    await this_APRSRegistryClient.__process__()
    assert mock_logger.error.called
